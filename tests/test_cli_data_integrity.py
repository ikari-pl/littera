"""CLI-side data integrity: overlays, shared guards, and DB recovery commands."""

import json

from test_invariants import add_block, add_document, add_section, init_work, run


def test_note_set_preserves_sibling_overlay_keys(tmp_path):
    """Setting a note must not wipe other keys in the work-scoped overlay."""
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        res = run("littera entity add concept 'Being'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT id FROM works LIMIT 1")
            work_id = cur.fetchone()[0]
            cur.execute(
                "SELECT id FROM entities WHERE canonical_label = %s", ("Being",)
            )
            entity_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO entity_work_metadata (entity_id, work_id, metadata) "
                "VALUES (%s, %s, %s::jsonb)",
                (entity_id, work_id, json.dumps({"role": "protagonist"})),
            )
            db.conn.commit()

        res = run("littera entity note-set concept Being 'Note A'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT metadata FROM entity_work_metadata "
                "WHERE entity_id = %s AND work_id = %s",
                (entity_id, work_id),
            )
            metadata = cur.fetchone()[0]

        assert metadata["note"] == "Note A"
        assert metadata["role"] == "protagonist"

        res = run("littera entity note-show concept Being", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Note A" in res.stdout


def test_alignment_refuses_same_language(tmp_path):
    """The shared guard keeps same-language alignments out of the database."""
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First", lang="en")
        add_block(workdir, "Second", lang="en")

        res = run("littera alignment add 1 2", cwd=workdir)
        assert res.returncode != 0
        assert "same language" in res.stdout

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT count(*) FROM block_alignments")
            assert cur.fetchone()[0] == 0


def test_mention_refuses_unknown_entity(tmp_path):
    """The shared guard refuses to invent an entity for a mention."""
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")

        res = run("littera mention add 1 concept Nowhere", cwd=workdir)
        assert res.returncode != 0
        assert "Entity not found" in res.stdout

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT count(*) FROM mentions")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM entities")
            assert cur.fetchone()[0] == 0


def test_mntn_db_recover_is_registered_and_runs(tmp_path):
    """WAL recovery is reachable headlessly, not only from the TUI dialog."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Survivor")

        res = run("littera mntn-db-recover", cwd=workdir)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "WAL reset" in res.stdout

        res = run("littera doc list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Survivor" in res.stdout


def test_mntn_db_reinit_requires_confirmation(tmp_path):
    """Re-init destroys data, so it refuses to run without --yes."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Precious")

        res = run("littera mntn-db-reinit", cwd=workdir)
        assert res.returncode != 0
        assert "Refusing" in res.stdout

        res = run("littera doc list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Precious" in res.stdout


def test_mntn_db_reinit_with_yes_empties_the_work(tmp_path):
    """With --yes the cluster is rebuilt empty and the work stays usable."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Precious")

        res = run("littera mntn-db-reinit --yes", cwd=workdir)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "re-initialized" in res.stdout

        res = run("littera doc list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Precious" not in res.stdout

        add_document(workdir, "Fresh")
        res = run("littera doc list", cwd=workdir)
        assert "Fresh" in res.stdout
