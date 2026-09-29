"""JSON export is Littera's archival format: export -> import -> export loses nothing.

Snapshots are built on this export and are offered as the safety net before
destructive edits, so anything it drops is silently destroyed on restore.
"Metadata is hidden, not destroyed."

Two real works on embedded Postgres, CLI wherever the CLI can express the
state. No mocks.
"""

from __future__ import annotations

import json
import re

from test_invariants import init_work, run

from littera.db.workdb import open_work_db

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _cli(cmd: str, workdir) -> str:
    res = run(cmd, cwd=workdir)
    assert res.returncode == 0, f"{cmd}\n{res.stdout}\n{res.stderr}"
    return res.stdout


def _export(workdir) -> dict:
    out = _cli("littera export json", workdir)
    return json.loads(out[out.index("{"):])


def _normalise(export: dict) -> dict:
    """Replace ids with stable tokens so two works can be compared."""
    tokens: dict[str, str] = {}

    def walk(value):
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str) and UUID_RE.match(value):
            return tokens.setdefault(value, f"id{len(tokens)}")
        return value

    work = walk(export["work"])
    # Order is carried by list position. The raw column may be NULL ("by
    # creation time") in the source and explicit after import; same order.
    for d_pos, doc in enumerate(work["documents"], 1):
        doc["order_index"] = d_pos
        for s_pos, sec in enumerate(doc["sections"], 1):
            sec["order_index"] = s_pos
            for b_pos, blk in enumerate(sec["blocks"], 1):
                blk["order_index"] = b_pos
    # Which work you import into decides these, not the archive.
    for key in ("title", "description", "default_language"):
        work.pop(key, None)
    # Mentions are listed in storage order; compare them as a set.
    work["mentions"] = sorted(work["mentions"], key=json.dumps)
    return work


def test_export_import_export_is_lossless(tmp_path):
    with init_work(tmp_path / "a") as src:
        _cli("littera doc add 'Chapter'", src)
        _cli("littera section add 1 'Scene'", src)
        _cli("littera block add 1 'Alice waits.' --lang en", src)
        _cli("littera block add 1 'Alicja czeka.' --lang pl", src)
        _cli("littera entity add person Alice", src)
        _cli("littera entity label-add Alice pl Alicja", src)
        _cli("littera entity property-set Alice gender=f", src)
        _cli("littera entity note-set person Alice 'Only in this work.'", src)
        _cli("littera mention add 1 person Alice", src)
        _cli("littera alignment add 1 2", src)

        block_id = _export(src)["work"]["documents"][0]["sections"][0]["blocks"][0]["id"]
        _cli(
            f"littera review add 'Check tense' --scope block --scope-id {block_id}"
            " --metadata '{\"source\": \"test\"}'",
            src,
        )

        # No CLI command sets these yet; they must still survive the archive.
        with open_work_db(src) as db:
            db.conn.execute(
                "UPDATE entity_labels SET aliases = '[\"Ala\"]' WHERE base_form = 'Alicja'"
            )
            db.conn.execute("UPDATE documents SET metadata = '{\"pov\": \"Alice\"}'")
            db.conn.execute("UPDATE sections SET metadata = '{\"mood\": \"calm\"}'")
            db.conn.execute("UPDATE blocks SET metadata = '{\"draft\": 2}'")
            db.conn.execute("UPDATE block_alignments SET confidence = 0.75")
            db.conn.commit()

        original = _export(src)

    archive = tmp_path / "archive.json"
    archive.write_text(json.dumps(original), encoding="utf-8")

    with init_work(tmp_path / "b") as dst:
        _cli(f"littera import json {archive}", dst)
        restored = _export(dst)

    assert _normalise(restored) == _normalise(original)

    # Guard against a vacuous pass: the archive really carries the state.
    work = original["work"]
    entity = work["entities"][0]
    assert {"language": "pl", "base_form": "Alicja", "aliases": ["Ala"]} in entity["labels"]
    assert entity["work_metadata"] == {"note": "Only in this work."}
    assert work["reviews"][0]["scope_id"] == block_id
    assert work["documents"][0]["metadata"] == {"pov": "Alice"}
    assert work["alignments"][0]["confidence"] == 0.75
