"""Black-box test for scripts/markdown_book_to_littera.py.

Markdown chapters -> import JSON -> `littera import json` -> CLI output.
Real embedded Postgres, no mocks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_invariants import init_work, run

SCRIPT = Path(__file__).parents[1] / "scripts" / "markdown_book_to_littera.py"

CHAPTER_2 = """# Chapter 2: The Second

*March 3, 2025*

---

First scene, *first* paragraph.

First scene, second paragraph.

---

Second scene.

- a list item
- another item

---

## March 4, 2025

Third scene, dated.
"""

CHAPTER_10 = """# Chapter 10: The Tenth
## April 1, 2025

Only scene.
"""


def test_book_becomes_one_document_of_chapter_sections_and_scene_blocks(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    # Named so that a plain filename sort would put chapter 10 first.
    (chapters / "chapter_10_tenth.md").write_text(CHAPTER_10)
    (chapters / "chapter_2_second.md").write_text(CHAPTER_2)
    out = tmp_path / "book.json"

    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(chapters), str(out), "--document", "Book One"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    # Chapter 2: the date line joins the first scene; three scenes. Chapter 10: one.
    assert "1 documents, 2 sections, 4 blocks" in res.stderr

    with init_work(tmp_path) as workdir:
        res = run(f"littera import json {out}", cwd=workdir)
        assert res.returncode == 0, res.stderr

        # One coherent piece: the book is a document, not one per file.
        res = run("littera doc list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Book One" in res.stdout
        assert "The Second" not in res.stdout

        # Chapters are sections, in chapter order, without "Chapter N".
        res = run("littera section list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] The Second" in res.stdout
        assert "[2] The Tenth" in res.stdout
        assert "Chapter" not in res.stdout

        # A block is a whole scene: several paragraphs, text kept verbatim,
        # date lines at the top of the scene they introduce.
        res = run("littera export markdown", cwd=workdir)
        assert res.returncode == 0, res.stderr
        exported = res.stdout
        assert (
            "[en] *March 3, 2025*\n\nFirst scene, *first* paragraph."
            "\n\nFirst scene, second paragraph."
        ) in exported
        assert "[en] Second scene.\n\n- a list item\n- another item" in exported
        assert "[en] ## March 4, 2025\n\nThird scene, dated." in exported
        assert "---" not in exported

        res = run("littera wc", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "(work, 4 blocks)" in res.stdout


MANIFEST = """
- type: person
  label: Alice
  aliases: [Ally]
  properties: {gender: f}
  note: Narrator's sister.
- type: place
  label: Warsaw
  labels: {pl: Warszawa}
  review:
    issue_type: fact-check
    severity: high
    description: Confirm this is really Warsaw.
- type: place
  label: Skawina
"""

CHAPTER_WITH_ENTITIES = """# Chapter 1: Visit

Ally's train left Warsaw at noon. Warsaw was grey.

---

Nobody in Warsaw noticed. Alice did.

---

Skawina is not named here, but it exists.
"""


def test_entity_manifest_becomes_entities_mentions_and_reviews(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "chapter_1.md").write_text(CHAPTER_WITH_ENTITIES)
    manifest = tmp_path / "entities.yaml"
    manifest.write_text(MANIFEST)
    out = tmp_path / "book.json"

    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(chapters), str(out), "--entities", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "3 entities, 5 mentions, 2 reviews" in res.stderr

    with init_work(tmp_path) as workdir:
        res = run(f"littera import json {out}", cwd=workdir)
        assert res.returncode == 0, res.stderr

        # Every listed entity exists, mentioned or not: the manifest is intent.
        res = run("littera entity list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        for name in ("person: Alice", "place: Warsaw", "place: Skawina"):
            assert name in res.stdout

        res = run("littera entity label-list Alice", cwd=workdir)
        assert "aliases: ['Ally']" in res.stdout
        res = run("littera entity label-list Warsaw", cwd=workdir)
        assert "pl: Warszawa" in res.stdout
        res = run("littera entity note-show person Alice", cwd=workdir)
        assert "Narrator's sister." in res.stdout

        # Mentions are rows bound to blocks; the prose itself is untouched.
        res = run("littera mention list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert 'surface: "Ally"' in res.stdout
        assert res.stdout.count("place: Warsaw") == 2
        res = run("littera export json", cwd=workdir)
        exported = res.stdout[res.stdout.index("{"):]
        assert "Ally's train left Warsaw at noon. Warsaw was grey." in exported
        assert "{@" not in exported
        assert '"case": "poss"' in exported

        # The review rule flags each block that mentions Warsaw, nothing else.
        res = run("littera review list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert res.stdout.count("Confirm this is really Warsaw.") == 2
        assert res.stdout.count("block:") == 2
