"""Import/export commands: littera export json|markdown, littera import json

Round-trip JSON preserves all structure and metadata.
Markdown export is read-only, for human consumption.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

import typer

from littera.cli.block import SIBLING_ORDER_SQL
from littera.db.workdb import open_work_db
from littera.domain import guards

# =========================================================================
# Shared export logic (used by CLI and desktop sidecar)
# =========================================================================


def _jsonb(value) -> str | None:
    return json.dumps(value) if value is not None else None


def export_work_json(conn) -> dict:
    """Build the full JSON export structure from a database connection."""
    cur = conn.cursor()

    # Work metadata
    cur.execute("SELECT id, title, description, default_language FROM works LIMIT 1")
    work_row = cur.fetchone()
    if work_row is None:
        return {"littera_version": "1.0", "work": None}

    work_id, work_title, work_desc, default_lang = work_row

    # Documents with sections and blocks
    cur.execute(
        "SELECT id, title, order_index, metadata FROM documents WHERE work_id = %s "
        f"ORDER BY {SIBLING_ORDER_SQL}",
        (work_id,),
    )
    documents = []
    for doc_id, doc_title, doc_order, doc_meta in cur.fetchall():
        cur.execute(
            "SELECT id, title, order_index, metadata FROM sections "
            "WHERE document_id = %s ORDER BY order_index",
            (doc_id,),
        )
        sections = []
        for sec_id, sec_title, order_idx, sec_meta in cur.fetchall():
            cur.execute(
                "SELECT id, block_type, language, source_text, order_index, metadata "
                f"FROM blocks WHERE section_id = %s ORDER BY {SIBLING_ORDER_SQL}",
                (sec_id,),
            )
            blocks = [
                {
                    "id": str(bid),
                    "block_type": btype,
                    "language": lang,
                    "source_text": text,
                    "order_index": order_idx,
                    "metadata": meta,
                }
                for bid, btype, lang, text, order_idx, meta in cur.fetchall()
            ]
            sections.append(
                {
                    "id": str(sec_id),
                    "title": sec_title,
                    "order_index": order_idx,
                    "metadata": sec_meta,
                    "blocks": blocks,
                }
            )
        documents.append(
            {
                "id": str(doc_id),
                "title": doc_title,
                "order_index": doc_order,
                "metadata": doc_meta,
                "sections": sections,
            }
        )

    # Entities with labels
    cur.execute(
        "SELECT id, entity_type, canonical_label, properties FROM entities ORDER BY created_at"
    )
    entities = []
    for eid, etype, canonical, props in cur.fetchall():
        cur.execute(
            "SELECT language, base_form, aliases FROM entity_labels "
            "WHERE entity_id = %s ORDER BY language",
            (eid,),
        )
        labels = []
        for lang, bf, aliases in cur.fetchall():
            label = {"language": lang, "base_form": bf}
            if aliases:
                label["aliases"] = aliases
            labels.append(label)
        # Entities are global; their overlay for this work (notes, ...) is not.
        cur.execute(
            "SELECT metadata FROM entity_work_metadata WHERE entity_id = %s AND work_id = %s",
            (eid, work_id),
        )
        overlay = cur.fetchone()
        entities.append(
            {
                "id": str(eid),
                "entity_type": etype,
                "canonical_label": canonical,
                "properties": props,
                "labels": labels,
                "work_metadata": overlay[0] if overlay else None,
            }
        )

    # Mentions
    cur.execute(
        "SELECT block_id, entity_id, language, surface_form, features FROM mentions ORDER BY id"
    )
    mentions = [
        {
            "block_id": str(bid),
            "entity_id": str(eid),
            "language": lang,
            "surface_form": sf,
            "features": feat,
        }
        for bid, eid, lang, sf, feat in cur.fetchall()
    ]

    # Alignments
    cur.execute(
        "SELECT id, source_block_id, target_block_id, alignment_type, confidence "
        "FROM block_alignments ORDER BY created_at"
    )
    alignments = [
        {
            # The id lets an alignment-scoped review find its target on import.
            "id": str(aid),
            "source_block_id": str(src),
            "target_block_id": str(tgt),
            "alignment_type": atype,
            "confidence": float(conf) if conf is not None else None,
        }
        for aid, src, tgt, atype, conf in cur.fetchall()
    ]

    # Reviews
    cur.execute(
        "SELECT description, severity, scope, scope_id, issue_type, metadata "
        "FROM reviews WHERE work_id = %s ORDER BY created_at",
        (work_id,),
    )
    reviews = [
        {
            "description": desc,
            "severity": sev,
            "scope": scope,
            "scope_id": str(scope_id) if scope_id else None,
            "issue_type": itype,
            "metadata": meta,
        }
        for desc, sev, scope, scope_id, itype, meta in cur.fetchall()
    ]

    return {
        "littera_version": "1.0",
        "work": {
            "title": work_title,
            "description": work_desc,
            "default_language": default_lang,
            "documents": documents,
            "entities": entities,
            "mentions": mentions,
            "alignments": alignments,
            "reviews": reviews,
        },
    }


def export_work_markdown(conn, compile: bool = False) -> str:
    """Build a Markdown representation of the work.

    Default is a labeled dump (Document: prefixes, [lang] tags).
    ``compile=True`` joins chapters as a manuscript: no language tags,
    mention markup reduced to visible labels.
    """
    from littera.cli.words import visible_text

    cur = conn.cursor()

    cur.execute("SELECT id, title FROM works LIMIT 1")
    work_row = cur.fetchone()
    if work_row is None:
        return "# (empty work)\n"

    work_id, work_title = work_row
    lines = [f"# {work_title or 'Untitled'}", ""]

    cur.execute(
        "SELECT id, title FROM documents WHERE work_id = %s ORDER BY order_index, created_at",
        (work_id,),
    )
    for doc_id, doc_title in cur.fetchall():
        if compile:
            lines.append(f"## {doc_title or 'Untitled'}")
        else:
            lines.append(f"## Document: {doc_title or 'Untitled'}")
        lines.append("")

        cur.execute(
            "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
            (doc_id,),
        )
        for sec_id, sec_title in cur.fetchall():
            lines.append(f"### {sec_title or 'Untitled'}")
            lines.append("")

            cur.execute(
                f"SELECT language, source_text FROM blocks WHERE section_id = %s ORDER BY {SIBLING_ORDER_SQL}",
                (sec_id,),
            )
            for lang, text in cur.fetchall():
                if compile:
                    body = visible_text(text).strip()
                    if body:
                        lines.append(body)
                        lines.append("")
                else:
                    lines.append(f"[{lang}] {text}")
                    lines.append("")

    return "\n".join(lines)


def import_work_json(conn, data: dict) -> dict:
    """Import JSON data into the current work. Returns summary counts.

    Uses a single transaction for atomicity. Entities are deduplicated
    by canonical_label. UUIDs from the JSON are preserved where possible.
    """
    cur = conn.cursor()

    cur.execute("SELECT id FROM works LIMIT 1")
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("No work found. Run 'littera init' first.")
    work_id = row[0]

    work_data = data.get("work")
    if work_data is None:
        raise ValueError("Invalid export data: missing 'work' key")

    counts = {
        "documents": 0,
        "sections": 0,
        "blocks": 0,
        "entities": 0,
        "labels": 0,
        "mentions": 0,
        "alignments": 0,
        "reviews": 0,
    }

    # --- Entities (deduplicate by canonical_label) ---
    entity_id_map: dict[str, str] = {}  # old_id -> new_id
    for ent in work_data.get("entities", []):
        canonical = ent.get("canonical_label")
        etype = ent.get("entity_type", "concept")
        props = ent.get("properties")
        old_id = ent.get("id")

        # Check if entity already exists by canonical_label
        cur.execute(
            "SELECT id FROM entities WHERE canonical_label = %s",
            (canonical,),
        )
        existing = cur.fetchone()
        if existing:
            entity_id_map[old_id] = str(existing[0])
        else:
            new_id = old_id or str(uuid.uuid4())
            # Handle potential UUID collision
            cur.execute("SELECT id FROM entities WHERE id = %s", (new_id,))
            if cur.fetchone():
                new_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO entities (id, entity_type, canonical_label, properties) "
                "VALUES (%s, %s, %s, %s)",
                (new_id, etype, canonical, json.dumps(props) if props else None),
            )
            entity_id_map[old_id] = new_id
            counts["entities"] += 1

        # Labels for this entity
        resolved_eid = entity_id_map[old_id]
        for label in ent.get("labels", []):
            lang = label.get("language")
            bf = label.get("base_form")
            if lang and bf:
                cur.execute(
                    "SELECT id FROM entity_labels WHERE entity_id = %s AND language = %s",
                    (resolved_eid, lang),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO entity_labels (id, entity_id, language, base_form, aliases) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (str(uuid.uuid4()), resolved_eid, lang, bf, _jsonb(label.get("aliases"))),
                    )
                    counts["labels"] += 1

        # This work's overlay (notes, ...). Merged like every other writer, so
        # importing never erases keys the work already had for this entity.
        overlay = ent.get("work_metadata")
        if overlay:
            cur.execute(
                """
                INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
                VALUES (%s, %s, %s)
                ON CONFLICT (entity_id, work_id)
                DO UPDATE SET metadata =
                    COALESCE(entity_work_metadata.metadata, '{}'::jsonb) || EXCLUDED.metadata
                """,
                (resolved_eid, work_id, json.dumps(overlay)),
            )

    # --- Documents, Sections, Blocks ---
    # Import appends: existing documents keep the order the user already sees
    # and imported ones land after them.  Existing rows may be numbered 1..n
    # (the CLI renumbers on move) or carry NULL order_index (TUI-created, and
    # NULLS LAST would push them behind the import), so freeze the current
    # order as explicit indexes first and offset the import past it.
    cur.execute(
        f"SELECT id FROM documents WHERE work_id = %s ORDER BY {SIBLING_ORDER_SQL}",
        (work_id,),
    )
    existing_doc_ids = [row[0] for row in cur.fetchall()]
    if existing_doc_ids:
        cur.executemany(
            "UPDATE documents SET order_index = %s WHERE id = %s",
            [(idx, doc_id) for idx, doc_id in enumerate(existing_doc_ids, 1)],
        )
    doc_order_offset = len(existing_doc_ids)

    # old_id -> new_id, so references (mentions, alignments, review scopes)
    # follow the rows they point at.
    doc_id_map: dict[str, str] = {}
    sec_id_map: dict[str, str] = {}
    block_id_map: dict[str, str] = {}
    for doc_idx, doc in enumerate(work_data.get("documents", []), 1):
        doc_old_id = doc.get("id")
        doc_new_id = doc_old_id or str(uuid.uuid4())
        # Handle UUID collision
        cur.execute("SELECT id FROM documents WHERE id = %s", (doc_new_id,))
        if cur.fetchone():
            doc_new_id = str(uuid.uuid4())
        doc_order = doc.get("order_index")
        if doc_order is None:
            doc_order = doc_idx
        doc_order += doc_order_offset
        cur.execute(
            "INSERT INTO documents (id, work_id, title, order_index, metadata) "
            "VALUES (%s, %s, %s, %s, %s)",
            (doc_new_id, work_id, doc.get("title"), doc_order, _jsonb(doc.get("metadata"))),
        )
        doc_id_map[doc_old_id] = doc_new_id
        counts["documents"] += 1

        for sec_idx, sec in enumerate(doc.get("sections", []), 1):
            sec_old_id = sec.get("id")
            sec_new_id = sec_old_id or str(uuid.uuid4())
            cur.execute("SELECT id FROM sections WHERE id = %s", (sec_new_id,))
            if cur.fetchone():
                sec_new_id = str(uuid.uuid4())
            sec_order = sec.get("order_index")
            if sec_order is None:
                sec_order = sec_idx
            cur.execute(
                "INSERT INTO sections (id, document_id, title, order_index, metadata) "
                "VALUES (%s, %s, %s, %s, %s)",
                (sec_new_id, doc_new_id, sec.get("title"), sec_order, _jsonb(sec.get("metadata"))),
            )
            sec_id_map[sec_old_id] = sec_new_id
            counts["sections"] += 1

            for idx, blk in enumerate(sec.get("blocks", []), 1):
                blk_old_id = blk.get("id")
                blk_new_id = blk_old_id or str(uuid.uuid4())
                cur.execute("SELECT id FROM blocks WHERE id = %s", (blk_new_id,))
                if cur.fetchone():
                    blk_new_id = str(uuid.uuid4())
                order_index = blk.get("order_index")
                if order_index is None:
                    order_index = idx
                cur.execute(
                    "INSERT INTO blocks "
                    "(id, section_id, block_type, language, source_text, order_index, metadata) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        blk_new_id,
                        sec_new_id,
                        blk.get("block_type", "paragraph"),
                        blk.get("language", "en"),
                        blk.get("source_text", ""),
                        order_index,
                        _jsonb(blk.get("metadata")),
                    ),
                )
                block_id_map[blk_old_id] = blk_new_id
                counts["blocks"] += 1

    # --- Mentions ---
    for m in work_data.get("mentions", []):
        old_block_id = m.get("block_id")
        old_entity_id = m.get("entity_id")
        block_id = block_id_map.get(old_block_id, old_block_id)
        entity_id = entity_id_map.get(old_entity_id, old_entity_id)
        features = m.get("features")
        cur.execute(
            "INSERT INTO mentions (id, block_id, entity_id, language, surface_form, features) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                block_id,
                entity_id,
                m.get("language", "en"),
                m.get("surface_form"),
                json.dumps(features) if features else None,
            ),
        )
        counts["mentions"] += 1

    # --- Alignments ---
    alignment_id_map: dict[str, str] = {}
    for a in work_data.get("alignments", []):
        old_src = a.get("source_block_id")
        old_tgt = a.get("target_block_id")
        src_id = block_id_map.get(old_src, old_src)
        tgt_id = block_id_map.get(old_tgt, old_tgt)
        new_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO block_alignments "
            "(id, source_block_id, target_block_id, alignment_type, confidence) "
            "VALUES (%s, %s, %s, %s, %s)",
            (new_id, src_id, tgt_id, a.get("alignment_type", "translation"), a.get("confidence")),
        )
        if a.get("id"):
            alignment_id_map[a["id"]] = new_id
        counts["alignments"] += 1

    # --- Reviews ---
    scope_id_maps = {
        "document": doc_id_map,
        "section": sec_id_map,
        "block": block_id_map,
        "entity": entity_id_map,
        "alignment": alignment_id_map,
    }
    for r in work_data.get("reviews", []):
        scope, scope_id = r.get("scope"), r.get("scope_id")
        if scope == "work":
            scope_id = str(work_id) if scope_id else None
        elif scope_id:
            scope_id = scope_id_maps.get(scope, {}).get(scope_id, scope_id)
        # reviews.scope_id has no foreign key; the same guard as every other
        # writer refuses an archive whose review points at nothing.
        guards.ensure_review_scope(cur, scope, scope_id)
        cur.execute(
            "INSERT INTO reviews "
            "(id, work_id, description, severity, scope, scope_id, issue_type, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                work_id,
                r.get("description"),
                r.get("severity", "medium"),
                scope,
                scope_id,
                r.get("issue_type"),
                _jsonb(r.get("metadata")),
            ),
        )
        counts["reviews"] += 1

    conn.commit()
    return counts


# =========================================================================
# CLI command registration
# =========================================================================


def register_export(app: typer.Typer) -> None:
    """Register export subcommands onto the given Typer group."""

    @app.command("json")
    def export_json(
        output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
    ) -> None:
        """Export the entire work as JSON."""
        try:
            with open_work_db() as db:
                data = export_work_json(db.conn)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        text = json.dumps(data, indent=2, ensure_ascii=False)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            print(f"Exported to {output}")
        else:
            print(text)

    @app.command("markdown")
    def export_markdown(
        output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
        compile: bool = typer.Option(
            False,
            "--compile",
            help="Chapter-joined manuscript (no Document: / [lang] prefixes)",
        ),
    ) -> None:
        """Export the work as Markdown."""
        try:
            with open_work_db() as db:
                text = export_work_markdown(db.conn, compile=compile)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if output:
            Path(output).write_text(text, encoding="utf-8")
            print(f"Exported to {output}")
        else:
            print(text)


def register_import(app: typer.Typer) -> None:
    """Register import subcommands onto the given Typer group."""

    @app.command("json")
    def import_json(
        file: str = typer.Argument(help="Path to JSON file"),
    ) -> None:
        """Import a work from a JSON file."""
        path = Path(file)
        if not path.exists():
            print(f"File not found: {file}")
            sys.exit(1)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            sys.exit(1)

        try:
            with open_work_db() as db:
                counts = import_work_json(db.conn, data)
        except (RuntimeError, ValueError) as e:
            print(str(e))
            sys.exit(1)

        parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        summary = ", ".join(parts) if parts else "nothing"
        print(f"Imported: {summary}")


def write_snapshot(work_dir: Path, conn, name: str | None = None) -> Path:
    """Write a timestamped JSON export under .littera/snapshots/. Explicit only."""
    from datetime import datetime

    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    slug = ""
    if name:
        slug = "-" + re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    dest_dir = work_dir / ".littera" / "snapshots"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stamp}{slug}.json"
    suffix = 2
    while dest.exists():
        dest = dest_dir / f"{stamp}{slug}-{suffix}.json"
        suffix += 1
    dest.write_text(
        json.dumps(export_work_json(conn), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return dest


def register_snapshot(app: typer.Typer) -> None:
    """Register the explicit snapshot command."""

    @app.command("snapshot")
    def snapshot(
        name: str | None = typer.Option(
            None, "--name", "-n", help="Optional label appended to the timestamp"
        ),
    ) -> None:
        """Write a timestamped JSON export into .littera/snapshots/."""
        try:
            with open_work_db() as db:
                dest = write_snapshot(db.work_dir, db.conn, name)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"Snapshot written to {dest}")
