"""Tests for cross-language block alignment CRUD, gap detection, and LLM suggestions.

Uses real embedded PostgreSQL — no mocks. Test helpers from test_invariants.py.
"""

import os
import socket
import subprocess

import pytest

from tests.test_invariants import (
    init_work,
    run,
    add_document,
    add_section,
    add_block,
)


# --- fixtures ---


@pytest.fixture
def bilingual_work(tmp_path):
    """Set up a bilingual work with en/pl blocks, entity, mentions, and labels."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Bilingual Essay")
        # Section 1 = English, Section 2 = Polish
        run("littera section add 1 'English'", cwd=workdir)
        run("littera section add 1 'Polish'", cwd=workdir)
        run("littera block add 1 'Time is the most fundamental concept.' --lang en", cwd=workdir)
        run("littera block add 2 'Czas jest najbardziej fundamentalnym pojęciem.' --lang pl", cwd=workdir)

        # Create entity and add en label
        run("littera entity add concept Time", cwd=workdir)
        run("littera entity label-add Time en time", cwd=workdir)

        # Add mentions on both blocks
        run("littera mention add 1 concept Time", cwd=workdir)
        run("littera mention add 2 concept Time", cwd=workdir)

        yield workdir


# --- Alignment CRUD ---


def test_alignment_add_and_list(bilingual_work):
    workdir = bilingual_work
    res = run("littera alignment add 1 2", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert "Alignment added" in res.stdout
    assert "(en)" in res.stdout
    assert "(pl)" in res.stdout

    res = run("littera alignment list", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert "[1]" in res.stdout
    assert "translation" in res.stdout


def test_alignment_add_rejects_same_language(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Sec")
        add_block(workdir, "Block one", lang="en")
        add_block(workdir, "Block two", lang="en")

        res = run("littera alignment add 1 2", cwd=workdir)
        assert res.returncode != 0
        assert "same language" in res.stdout


def test_alignment_add_rejects_duplicate(bilingual_work):
    workdir = bilingual_work
    res = run("littera alignment add 1 2", cwd=workdir)
    assert res.returncode == 0

    res = run("littera alignment add 1 2", cwd=workdir)
    assert res.returncode != 0
    assert "already exists" in res.stdout


def test_alignment_add_rejects_reverse_duplicate(bilingual_work):
    """Adding target→source when source→target exists should be rejected too."""
    workdir = bilingual_work
    res = run("littera alignment add 1 2", cwd=workdir)
    assert res.returncode == 0

    res = run("littera alignment add 2 1", cwd=workdir)
    assert res.returncode != 0
    assert "already exists" in res.stdout


def test_alignment_delete(bilingual_work):
    workdir = bilingual_work
    run("littera alignment add 1 2", cwd=workdir)

    res = run("littera alignment delete 1", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert "Alignment deleted" in res.stdout

    res = run("littera alignment list", cwd=workdir)
    assert "No alignments yet" in res.stdout


def test_alignment_list_filtered_by_block(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        run("littera section add 1 'English'", cwd=workdir)
        run("littera section add 1 'Polish'", cwd=workdir)
        run("littera section add 1 'French'", cwd=workdir)
        run("littera block add 1 'English block' --lang en", cwd=workdir)
        run("littera block add 2 'Polski blok' --lang pl", cwd=workdir)
        run("littera block add 3 'Bloc français' --lang fr", cwd=workdir)

        run("littera alignment add 1 2", cwd=workdir)
        run("littera alignment add 1 3", cwd=workdir)

        # Filter by block 2 (pl) — should show only en↔pl alignment
        res = run("littera alignment list --block 2", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "(pl)" in res.stdout
        assert "(en)" in res.stdout
        # Should have exactly 1 alignment listed
        assert "[1]" in res.stdout
        assert "[2]" not in res.stdout


def test_alignment_cascade_on_block_delete(bilingual_work):
    workdir = bilingual_work
    run("littera alignment add 1 2", cwd=workdir)

    res = run("littera alignment list", cwd=workdir)
    assert "[1]" in res.stdout

    # Delete the source block — alignment should cascade
    run("littera block delete 1", cwd=workdir)

    res = run("littera alignment list", cwd=workdir)
    assert "No alignments yet" in res.stdout


# --- Gap detection ---


def test_gaps_detects_missing_label(bilingual_work):
    workdir = bilingual_work
    run("littera alignment add 1 2", cwd=workdir)

    res = run("littera alignment gaps", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert 'no label for pl' in res.stdout
    assert '"Time"' in res.stdout


def test_gaps_no_gaps_when_labels_complete(bilingual_work):
    workdir = bilingual_work
    run("littera alignment add 1 2", cwd=workdir)

    # Add the missing pl label
    run("littera entity label-add Time pl czas", cwd=workdir)

    res = run("littera alignment gaps", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert "No gaps found" in res.stdout


def test_gaps_shows_fix_commands(bilingual_work):
    workdir = bilingual_work
    run("littera alignment add 1 2", cwd=workdir)

    res = run("littera alignment gaps", cwd=workdir)
    assert "littera entity label-add Time pl" in res.stdout


def test_gaps_scoped_to_block(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        run("littera section add 1 'English'", cwd=workdir)
        run("littera section add 1 'Polish'", cwd=workdir)
        run("littera block add 1 'Block about time' --lang en", cwd=workdir)
        run("littera block add 1 'Block about space' --lang en", cwd=workdir)
        run("littera block add 2 'Blok o czasie' --lang pl", cwd=workdir)
        run("littera block add 2 'Blok o przestrzeni' --lang pl", cwd=workdir)

        run("littera entity add concept Time", cwd=workdir)
        run("littera entity add concept Space", cwd=workdir)
        run("littera entity label-add Time en time", cwd=workdir)
        run("littera entity label-add Space en space", cwd=workdir)

        run("littera mention add 1 concept Time", cwd=workdir)
        run("littera mention add 2 concept Space", cwd=workdir)
        run("littera mention add 3 concept Time", cwd=workdir)
        run("littera mention add 4 concept Space", cwd=workdir)

        # Align block 1 (en time) ↔ block 3 (pl time)
        run("littera alignment add 1 3", cwd=workdir)
        # Align block 2 (en space) ↔ block 4 (pl space)
        run("littera alignment add 2 4", cwd=workdir)

        # Scope gaps to block 1 — should only report Time missing pl, not Space
        res = run("littera alignment gaps 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert '"Time"' in res.stdout
        assert '"Space"' not in res.stdout


# --- Suggestion ---


def test_suggest_label_graceful_when_no_backend(bilingual_work):
    """Without LITTERA_LLM_BACKEND, suggest-label prints fallback."""
    workdir = bilingual_work
    repo_root = workdir.parents[1] if hasattr(workdir, 'parents') else workdir.parent.parent
    # Run without LITTERA_LLM_BACKEND in env
    env = {**os.environ, "PATH": os.environ.get("PATH", "")}
    env.pop("LITTERA_LLM_BACKEND", None)

    res = run("littera entity suggest-label Time pl", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert "label-add" in res.stdout
    assert "<base_form>" in res.stdout


def test_gaps_suggest_graceful_when_no_backend(bilingual_work):
    """--suggest without backend still shows placeholder commands."""
    workdir = bilingual_work
    run("littera alignment add 1 2", cwd=workdir)

    res = run("littera alignment gaps --suggest", cwd=workdir)
    assert res.returncode == 0, res.stderr
    assert "label-add" in res.stdout
    assert "<base_form>" in res.stdout


def _lmstudio_reachable():
    """Check if LM Studio is running on localhost:1234."""
    try:
        s = socket.create_connection(("localhost", 1234), timeout=1)
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


@pytest.mark.skipif(
    not _lmstudio_reachable(),
    reason="LM Studio not available on localhost:1234",
)
def test_suggest_label_lmstudio_integration(bilingual_work):
    """Integration test: real LM Studio call. Skipped if unavailable."""
    workdir = bilingual_work

    from littera.linguistics.suggest import suggest_label

    os.environ["LITTERA_LLM_BACKEND"] = "lmstudio"
    try:
        result = suggest_label("Time", "concept", "en", "pl")
        assert result is not None
        assert len(result) > 0
    finally:
        os.environ.pop("LITTERA_LLM_BACKEND", None)
