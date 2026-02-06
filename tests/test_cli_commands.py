"""Tests for CLI commands not covered by test_invariants.py.

Covers: delete, section list, mention lifecycle, entity labels, mntn-db-*.
Uses real embedded Postgres per MANIFESTO.
"""

from tests.test_invariants import init_work, run, add_document, add_section, add_block


# ── Delete commands ──────────────────────────────────────────────


def test_doc_delete_empty(tmp_path):
    """Delete a document with no children."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Ephemeral")
        res = run("littera doc delete 1", cwd=workdir)
        assert res.returncode == 0
        assert "Document deleted" in res.stdout

        res = run("littera doc list", cwd=workdir)
        assert "Ephemeral" not in res.stdout


def test_doc_delete_cascades(tmp_path):
    """Delete a document cascades sections and blocks."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Big Doc")
        add_section(workdir, "Section A")
        add_block(workdir, "Some text")

        res = run("littera doc delete 1", cwd=workdir)
        assert res.returncode == 0
        assert "cascaded" in res.stdout


def test_section_delete_empty(tmp_path):
    """Delete a section with no blocks."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Empty Section")

        res = run("littera section delete 1 1", cwd=workdir)
        assert res.returncode == 0
        assert "Section deleted" in res.stdout


def test_section_delete_cascades(tmp_path):
    """Delete a section cascades its blocks."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Full Section")
        add_block(workdir, "Block text")

        res = run("littera section delete 1 1", cwd=workdir)
        assert res.returncode == 0
        assert "cascaded" in res.stdout


def test_entity_delete(tmp_path):
    """Delete an entity."""
    with init_work(tmp_path) as workdir:
        run("littera entity add concept 'Transient'", cwd=workdir)
        res = run("littera entity delete 1", cwd=workdir)
        assert res.returncode == 0
        assert "Entity deleted" in res.stdout

        res = run("littera entity list", cwd=workdir)
        assert "Transient" not in res.stdout


def test_block_delete_with_mention(tmp_path):
    """Delete a block cascades its mentions."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Sec")
        add_block(workdir, "Text about Time")
        run("littera entity add concept 'Time'", cwd=workdir)
        run("littera mention add 1 concept Time", cwd=workdir)

        res = run("littera block delete 1", cwd=workdir)
        assert res.returncode == 0
        assert "cascaded" in res.stdout
        assert "mention" in res.stdout


# ── Section list ─────────────────────────────────────────────────


def test_section_list(tmp_path):
    """List sections in a document."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Alpha")
        run("littera section add 1 'Beta'", cwd=workdir)

        res = run("littera section list 1", cwd=workdir)
        assert res.returncode == 0
        assert "Alpha" in res.stdout
        assert "Beta" in res.stdout


def test_section_list_empty(tmp_path):
    """List sections when there are none."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Empty Doc")

        res = run("littera section list 1", cwd=workdir)
        assert res.returncode == 0
        assert "No sections" in res.stdout


# ── Mention list / delete ────────────────────────────────────────


def test_mention_list(tmp_path):
    """List mentions."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Sec")
        add_block(workdir, "About Aristotle")
        run("littera entity add person 'Aristotle'", cwd=workdir)
        run("littera mention add 1 person Aristotle", cwd=workdir)

        res = run("littera mention list", cwd=workdir)
        assert res.returncode == 0
        assert "Aristotle" in res.stdout


def test_mention_delete(tmp_path):
    """Delete a mention."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Sec")
        add_block(workdir, "About Time")
        run("littera entity add concept 'Time'", cwd=workdir)
        run("littera mention add 1 concept Time", cwd=workdir)

        res = run("littera mention delete 1", cwd=workdir)
        assert res.returncode == 0
        assert "Mention deleted" in res.stdout

        res = run("littera mention list", cwd=workdir)
        assert "No mentions" in res.stdout


# ── Entity labels ────────────────────────────────────────────────


def test_entity_label_lifecycle(tmp_path):
    """Add, list, and delete entity labels."""
    with init_work(tmp_path) as workdir:
        run("littera entity add person 'Aristotle'", cwd=workdir)

        # Add labels
        res = run("littera entity label-add Aristotle en Aristotle", cwd=workdir)
        assert res.returncode == 0
        assert "Label set" in res.stdout

        res = run("littera entity label-add Aristotle pl Arystoteles", cwd=workdir)
        assert res.returncode == 0

        # List labels
        res = run("littera entity label-list Aristotle", cwd=workdir)
        assert res.returncode == 0
        assert "en: Aristotle" in res.stdout
        assert "pl: Arystoteles" in res.stdout

        # Delete label
        res = run("littera entity label-delete Aristotle pl", cwd=workdir)
        assert res.returncode == 0
        assert "Label deleted" in res.stdout

        # Verify
        res = run("littera entity label-list Aristotle", cwd=workdir)
        assert "en: Aristotle" in res.stdout
        assert "Arystoteles" not in res.stdout


def test_entity_label_upsert(tmp_path):
    """Label-add with same language overwrites (upsert)."""
    with init_work(tmp_path) as workdir:
        run("littera entity add concept 'Truth'", cwd=workdir)
        run("littera entity label-add Truth en truth", cwd=workdir)
        run("littera entity label-add Truth en Truth", cwd=workdir)

        res = run("littera entity label-list Truth", cwd=workdir)
        assert res.returncode == 0
        assert "en: Truth" in res.stdout


# ── mntn-db-* ────────────────────────────────────────────────────


def test_mntn_db_status(tmp_path):
    """mntn-db-status shows Postgres state."""
    with init_work(tmp_path) as workdir:
        res = run("littera mntn-db-status", cwd=workdir)
        assert res.returncode == 0
        assert "Postgres:" in res.stdout


def test_mntn_db_start_stop(tmp_path):
    """mntn-db-start and mntn-db-stop cycle."""
    with init_work(tmp_path) as workdir:
        res = run("littera mntn-db-start --lease-seconds 0", cwd=workdir)
        assert res.returncode == 0
        assert "Postgres" in res.stdout

        res = run("littera mntn-db-stop", cwd=workdir)
        assert res.returncode == 0


def test_mntn_db_lease(tmp_path):
    """mntn-db-lease shows and sets lease."""
    with init_work(tmp_path) as workdir:
        # Show when no lease
        res = run("littera mntn-db-lease", cwd=workdir)
        assert res.returncode == 0
