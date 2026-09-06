"""TUI import/export wrappers call the same io.py path as CLI/desktop.

Uses the real embedded Postgres fixture. Import tests clean up after
themselves so the session-scoped seed stays stable for other TUI tests.
"""

import json
import uuid

import pytest

from littera.tui import actions
from littera.tui.app import LitteraApp


def test_app_has_io_bindings():
    keys = {binding[0] for binding in LitteraApp.BINDINGS}
    assert "x" in keys
    assert "X" in keys
    assert "i" in keys


def test_export_json_contains_seeded_work(tui_state, tmp_path):
    dest = tmp_path / "work.json"
    written = actions.export_json_to_path(tui_state.db, str(dest))
    assert written == dest

    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["littera_version"] == "1.0"
    titles = [doc["title"] for doc in data["work"]["documents"]]
    assert "Document One" in titles
    assert "Document Two" in titles


def test_export_markdown_contains_titles(tui_state, tmp_path):
    dest = tmp_path / "work.md"
    written = actions.export_markdown_to_path(tui_state.db, str(dest))
    assert written == dest

    text = dest.read_text(encoding="utf-8")
    assert "Document One" in text
    assert "Introduction" in text
    assert "This is the first block" in text


def test_import_json_adds_document_then_cleans_up(tui_state, tmp_path):
    title = f"Imported Doc {uuid.uuid4()}"
    payload = {
        "littera_version": "1.0",
        "work": {
            "title": "Imported",
            "description": None,
            "default_language": "en",
            "documents": [
                {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "sections": [],
                }
            ],
            "entities": [],
            "mentions": [],
            "alignments": [],
            "reviews": [],
        },
    }
    src = tmp_path / "in.json"
    src.write_text(json.dumps(payload), encoding="utf-8")

    counts = actions.import_json_from_path(tui_state.db, str(src))
    assert counts["documents"] == 1

    with tui_state.db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents WHERE title = %s", (title,))
        assert cur.fetchone()[0] == 1
        cur.execute("DELETE FROM documents WHERE title = %s", (title,))
    tui_state.db.commit()


def test_import_missing_file_raises(tui_state, tmp_path):
    missing = tmp_path / "no-such.json"
    with pytest.raises(FileNotFoundError):
        actions.import_json_from_path(tui_state.db, str(missing))


def test_import_invalid_json_raises(tui_state, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        actions.import_json_from_path(tui_state.db, str(bad))
