"""Shared domain guards — tested against the real database, no mocks."""

import pytest
from test_invariants import init_work, run

from littera.domain.guards import (
    GuardViolation,
    ensure_alignment_languages_differ,
    ensure_entity_exists,
    find_entity,
)


def test_same_language_alignment_is_refused():
    with pytest.raises(GuardViolation) as exc:
        ensure_alignment_languages_differ("en", "en")
    assert "same language" in str(exc.value)


def test_different_language_alignment_is_allowed():
    assert ensure_alignment_languages_differ("en", "pl") is None


def test_entity_guards_against_real_database(tmp_path):
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        res = run("littera entity add concept 'Being'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()

            entity_id = find_entity(cur, "concept", "Being")
            assert entity_id is not None
            assert ensure_entity_exists(cur, "concept", "Being") == entity_id

            assert find_entity(cur, "concept", "Nowhere") is None
            with pytest.raises(GuardViolation) as exc:
                ensure_entity_exists(cur, "concept", "Nowhere")
            assert str(exc.value) == "Entity not found: concept Nowhere"

            # Entity type is part of identity: same label, other type.
            assert find_entity(cur, "person", "Being") is None


# =============================================================================
# Every interface must go through the guards, not just the CLI.
# =============================================================================

def test_all_three_interfaces_import_the_guards():
    """The point of the module is that a guard cannot be walked around.

    If an interface stops importing it, the divergence has simply moved.
    """
    import pathlib

    src = pathlib.Path(__file__).parents[1] / "src" / "littera"
    for path in [
        src / "tui" / "actions.py",
        src / "cli" / "alignment.py",
        src / "cli" / "mention.py",
        src / "desktop" / "server.py",
    ]:
        assert "littera.domain" in path.read_text(), f"{path.name} bypasses domain guards"


def test_review_scope_rejects_unknown_scope():
    from littera.domain.guards import GuardViolation, ensure_review_scope

    try:
        ensure_review_scope(None, "nonsense", None)
    except GuardViolation as exc:
        assert "Invalid scope" in str(exc)
    else:
        raise AssertionError("unknown scope was accepted")


def test_review_scope_rejects_malformed_id_without_touching_db():
    """A malformed uuid must be refused before it reaches Postgres.

    Sending one aborts the surrounding transaction, and a refusal must not
    poison the caller's connection.
    """
    from littera.domain.guards import GuardViolation, ensure_review_scope

    # cur is None: if the guard queried the DB this would raise AttributeError.
    try:
        ensure_review_scope(None, "block", "not-a-uuid")
    except GuardViolation as exc:
        assert "Invalid block id" in str(exc)
    else:
        raise AssertionError("malformed scope id was accepted")


def test_work_scope_needs_no_id():
    from littera.domain.guards import ensure_review_scope

    ensure_review_scope(None, "work", None)
