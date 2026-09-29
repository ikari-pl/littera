"""Data-integrity and parity tests for the TUI write path.

Real embedded Postgres throughout (per MANIFESTO): every assertion below is
about what actually lands in the database.
"""

import json
import uuid

import pytest

from littera.domain.guards import GuardViolation
from littera.tui import actions, queries
from littera.tui.app import describe_delete_dependents

# =============================================================================
# Helpers
# =============================================================================

def _scratch_section(db):
    """A throwaway document + section inside the seeded work."""
    with db.cursor() as cur:
        cur.execute("SELECT id FROM works LIMIT 1")
        work_id = str(cur.fetchone()[0])
    doc_id = actions.create_document(db, work_id, "Scratch Document")
    section_id = actions.create_section(db, doc_id, "Scratch Section")
    return work_id, doc_id, section_id


def _drop_document(db, doc_id):
    with db.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    db.commit()


# =============================================================================
# littera-4ib: deleting structure must not silently destroy meaning
# =============================================================================

def test_delete_counts_dependents_before_destroying_them(tui_state):
    db = tui_state.db
    _work_id, doc_id, section_id = _scratch_section(db)
    try:
        block_id = actions.create_block(db, section_id)
        # Alignments now require two languages (domain guard), so the
        # partner block is Polish rather than a second English one.
        other_block = actions.create_block(db, section_id, language="pl")

        entity_id = actions.create_entity(db, "concept", f"Dep {uuid.uuid4()}")
        actions.link_block_to_entity(db, block_id, entity_id)
        actions.create_alignment(db, block_id, other_block)

        counts = actions.count_delete_dependents(db, "document", doc_id)
        assert counts["sections"] == 1
        assert counts["blocks"] == 2
        assert counts["mentions"] == 1
        assert counts["alignments"] == 1

        text = describe_delete_dependents(counts)
        assert "1 section" in text
        assert "2 blocks" in text
        assert "1 mention" in text
        assert "1 alignment" in text
    finally:
        _drop_document(db, doc_id)


def test_deleting_a_block_unscopes_its_reviews_instead_of_orphaning_them(tui_state):
    """reviews.scope_id has no FK, so nothing cascades: the TUI must clear it."""
    db = tui_state.db
    work_id, doc_id, section_id = _scratch_section(db)
    try:
        block_id = actions.create_block(db, section_id)
        review_id = actions.create_review(
            db, work_id, "Tighten this", "low", scope="block", scope_id=block_id
        )

        counts = actions.count_delete_dependents(db, "block", block_id)
        assert counts["reviews"] == 1
        assert "unscoped" in describe_delete_dependents(counts)

        actions.delete_item(db, "block", block_id)

        with db.cursor() as cur:
            cur.execute(
                "SELECT scope, scope_id, description FROM reviews WHERE id = %s",
                (review_id,),
            )
            scope, scope_id, description = cur.fetchone()
        assert scope is None, "block-scoped review still points at a deleted block"
        assert scope_id is None
        assert description == "Tighten this", "the note itself must survive"

        actions.delete_review(db, review_id)
    finally:
        _drop_document(db, doc_id)


def test_deleting_a_document_unscopes_reviews_on_its_descendants(tui_state):
    db = tui_state.db
    work_id, doc_id, section_id = _scratch_section(db)
    block_id = actions.create_block(db, section_id)
    review_id = actions.create_review(
        db, work_id, "Nested scope", "low", scope="block", scope_id=block_id
    )

    counts = actions.delete_item(db, "document", doc_id)
    assert counts["reviews"] == 1

    with db.cursor() as cur:
        cur.execute("SELECT scope_id FROM reviews WHERE id = %s", (review_id,))
        assert cur.fetchone()[0] is None
    actions.delete_review(db, review_id)


# =============================================================================
# littera-bbe: work overlays and entity properties must merge, not clobber
# =============================================================================

def test_saving_a_note_keeps_other_overlay_keys(tui_state):
    db = tui_state.db
    with db.cursor() as cur:
        cur.execute("SELECT id FROM works LIMIT 1")
        work_id = str(cur.fetchone()[0])
    entity_id = actions.create_entity(db, "concept", f"Overlay {uuid.uuid4()}")

    # Another interface (CLI, desktop) wrote its own keys into the overlay.
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO entity_work_metadata (entity_id, work_id, metadata) "
            "VALUES (%s, %s, %s::jsonb)",
            (entity_id, work_id, json.dumps({"role": "antagonist", "note": "old"})),
        )
    db.commit()

    actions.save_entity_note(db, entity_id, work_id, "new note")

    with db.cursor() as cur:
        cur.execute(
            "SELECT metadata FROM entity_work_metadata "
            "WHERE entity_id = %s AND work_id = %s",
            (entity_id, work_id),
        )
        metadata = cur.fetchone()[0]

    assert metadata["note"] == "new note"
    assert metadata["role"] == "antagonist", "note save destroyed the work overlay"


def test_setting_a_property_does_not_drop_a_concurrent_write(tui_state):
    db = tui_state.db
    entity_id = actions.create_entity(db, "concept", f"Props {uuid.uuid4()}")
    actions.set_entity_property(db, entity_id, "era", "classical")

    # A second connection writes a different key between read and write.
    import psycopg

    dsn = db.info.dsn
    with psycopg.connect(dsn) as other:
        with other.cursor() as cur:
            cur.execute(
                "UPDATE entities SET properties = "
                "COALESCE(properties, '{}'::jsonb) || '{\"origin\": \"cli\"}'::jsonb "
                "WHERE id = %s",
                (entity_id,),
            )
        other.commit()

    actions.set_entity_property(db, entity_id, "status", "draft")

    with db.cursor() as cur:
        cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
        props = cur.fetchone()[0]

    assert props == {"era": "classical", "origin": "cli", "status": "draft"}


def test_deleting_a_property_removes_only_that_key(tui_state):
    db = tui_state.db
    entity_id = actions.create_entity(db, "concept", f"Props {uuid.uuid4()}")
    actions.set_entity_property(db, entity_id, "era", "classical")
    actions.set_entity_property(db, entity_id, "status", "draft")

    assert actions.delete_entity_property(db, entity_id, "era") is True
    assert actions.delete_entity_property(db, entity_id, "era") is False

    with db.cursor() as cur:
        cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
        assert cur.fetchone()[0] == {"status": "draft"}


# =============================================================================
# littera-d2p: linking must never auto-create an entity
# =============================================================================

def test_linking_never_auto_creates_an_entity(tui_state):
    """INVARIANTS.md: auto-creating entities without intent is a violation."""
    db = tui_state.db
    assert not hasattr(actions, "link_entity"), (
        "the auto-creating link_entity is back"
    )

    missing = f"Nowhere Near {uuid.uuid4()}"
    assert actions.find_entities_by_label(db, missing) == []

    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM entities")
        before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM entities WHERE canonical_label = %s", (missing,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM entities")
        assert cur.fetchone()[0] == before


def test_find_entities_by_label_separates_same_label_different_type(tui_state):
    db = tui_state.db
    label = f"Janus {uuid.uuid4()}"
    concept_id = actions.create_entity(db, "concept", label)
    person_id = actions.create_entity(db, "person", label)

    found = actions.find_entities_by_label(db, label)
    assert {f[0] for f in found} == {concept_id, person_id}
    assert {f[1] for f in found} == {"concept", "person"}


def test_link_block_to_entity_is_idempotent_and_checked(tui_state, seeded_ids):
    db = tui_state.db
    block_id = seeded_ids["blk1_id"]
    entity_id = actions.create_entity(db, "concept", f"Link {uuid.uuid4()}")

    assert actions.link_block_to_entity(db, block_id, entity_id) is True
    assert actions.link_block_to_entity(db, block_id, entity_id) is False

    with pytest.raises(LookupError):
        actions.link_block_to_entity(db, block_id, str(uuid.uuid4()))

    mentions = queries.fetch_block_mentions(db, block_id)
    for mention_id, _t, _l, _lang, _s in mentions:
        actions.delete_mention(db, mention_id)


# =============================================================================
# littera-nge: new blocks are empty and inherit a language
# =============================================================================

def test_new_block_is_empty_and_inherits_language(tui_state):
    db = tui_state.db
    work_id, doc_id, section_id = _scratch_section(db)
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE works SET default_language = 'pl' WHERE id = %s", (work_id,)
            )
        db.commit()

        first = actions.create_block(db, section_id)
        with db.cursor() as cur:
            cur.execute(
                "SELECT source_text, language FROM blocks WHERE id = %s", (first,)
            )
            text, language = cur.fetchone()
        assert text == "", "placeholder text would count towards wc and export"
        assert language == "pl", "language must come from the work default"

        # The next block follows its sibling, whatever that is.
        actions.set_block_language(db, first, "fr")
        second = actions.create_block(db, section_id)
        with db.cursor() as cur:
            cur.execute("SELECT language FROM blocks WHERE id = %s", (second,))
            assert cur.fetchone()[0] == "fr"
    finally:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE works SET default_language = NULL WHERE id = %s", (work_id,)
            )
        db.commit()
        _drop_document(db, doc_id)


# =============================================================================
# littera-shv: reviews carry a scope, and the scope reads as a name
# =============================================================================

def test_review_can_be_created_with_a_scope(tui_state, seeded_ids):
    db = tui_state.db
    with db.cursor() as cur:
        cur.execute("SELECT id FROM works LIMIT 1")
        work_id = str(cur.fetchone()[0])

    review_id = actions.create_review(
        db, work_id, "Scoped note", "medium",
        scope="document", issue_type="clarity", scope_id=seeded_ids["doc1_id"],
    )
    with db.cursor() as cur:
        cur.execute(
            "SELECT scope, scope_id, issue_type FROM reviews WHERE id = %s",
            (review_id,),
        )
        scope, scope_id, issue_type = cur.fetchone()
    assert scope == "document"
    assert str(scope_id) == seeded_ids["doc1_id"]
    assert issue_type == "clarity"

    # The detail pane names the target instead of printing a raw UUID.
    with db.cursor() as cur:
        detail = queries._review_detail(cur, review_id)
    assert seeded_ids["doc1_title"] in detail
    assert seeded_ids["doc1_id"] not in detail.split("Description:")[0].replace(
        f"Review: {review_id}", ""
    )

    actions.update_review(db, review_id, clear_scope=True)
    with db.cursor() as cur:
        cur.execute("SELECT scope, scope_id FROM reviews WHERE id = %s", (review_id,))
        assert cur.fetchone() == (None, None)

    actions.delete_review(db, review_id)


def test_review_scope_is_validated_like_the_cli(tui_state):
    db = tui_state.db
    with db.cursor() as cur:
        cur.execute("SELECT id FROM works LIMIT 1")
        work_id = str(cur.fetchone()[0])

    with pytest.raises(GuardViolation):
        actions.create_review(db, work_id, "Bad scope", "low", scope="paragraph")
    db.rollback()


def test_scope_label_reports_a_deleted_target(tui_state):
    db = tui_state.db
    with db.cursor() as cur:
        label = queries.scope_target_label(cur, "block", str(uuid.uuid4()))
    assert label == "(deleted)"


# =============================================================================
# littera-ejj: snapshots are reachable from the TUI
# =============================================================================

def test_snapshot_writes_a_timestamped_export(tui_state, seeded_work):
    workdir, _cfg, _pg_cfg = seeded_work
    dest = actions.write_work_snapshot(tui_state.db, workdir, "before-delete-block")
    assert dest.exists()
    assert dest.parent == workdir / ".littera" / "snapshots"
    assert "before-delete-block" in dest.name
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["work"]["documents"]
    dest.unlink()
