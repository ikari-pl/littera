"""Tests for littera block move — order is structural identity for indexes."""

from test_invariants import (
    _stop_postgres,
    add_block,
    add_document,
    add_section,
    init_work,
    run,
)


def test_block_move_changes_list_order(tmp_path):
    """Moving a block changes list order and index selectors."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")
        add_block(workdir, "Second")
        add_block(workdir, "Third")

        res = run("littera block list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) First" in res.stdout
        assert "[2] (en) Second" in res.stdout
        assert "[3] (en) Third" in res.stdout

        res = run("littera block move 3 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "position 1" in res.stdout

        res = run("littera block list 1", cwd=workdir)
        assert "[1] (en) Third" in res.stdout
        assert "[2] (en) First" in res.stdout
        assert "[3] (en) Second" in res.stdout


def test_block_move_by_uuid(tmp_path):
    """UUID selectors skip the global source_text scan and still reorder."""
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")
        add_block(workdir, "Second")

        with open_work_db(workdir) as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT id FROM blocks ORDER BY order_index NULLS LAST, created_at"
            )
            second_id = str(cur.fetchall()[1][0])

        res = run(f"littera block move {second_id} 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "position 1" in res.stdout

        res = run("littera block list 1", cwd=workdir)
        assert "[1] (en) Second" in res.stdout
        assert "[2] (en) First" in res.stdout


def test_block_move_out_of_range(tmp_path):
    """Reject a position outside the section."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "Only")

        res = run("littera block move 1 5", cwd=workdir)
        assert res.returncode != 0
        assert "Position must be between" in res.stdout


def test_block_move_stays_in_section(tmp_path):
    """Move is scoped to the block's own section."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir, "A")
        add_section(workdir, "B")
        run("littera block add 1 'A1'", cwd=workdir)
        run("littera block add 1 'A2'", cwd=workdir)
        run("littera block add 2 'B1'", cwd=workdir)

        res = run("littera block move 1 2", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera block list 1", cwd=workdir)
        assert "[1] (en) A2" in res.stdout
        assert "[2] (en) A1" in res.stdout

        res = run("littera block list 2", cwd=workdir)
        assert "[1] (en) B1" in res.stdout
        assert "A1" not in res.stdout


def test_legacy_import_assigns_order_index(tmp_path):
    """Imports without order_index get sequential indices; new blocks append."""
    import json

    with init_work(tmp_path) as workdir:
        payload = {
            "littera_version": "1.0",
            "work": {
                "title": "Imported",
                "documents": [
                    {
                        "title": "Doc",
                        "sections": [
                            {
                                "title": "SecA",
                                "blocks": [
                                    {"language": "en", "source_text": "Alpha"},
                                    {"language": "en", "source_text": "Beta"},
                                ],
                            },
                            {
                                "title": "SecB",
                                "blocks": [
                                    {"language": "en", "source_text": "Gamma"},
                                ],
                            },
                        ],
                    }
                ],
            },
        }
        src = workdir / "legacy.json"
        src.write_text(json.dumps(payload), encoding="utf-8")
        res = run(f"littera import json {src}", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera block add 1 'Delta'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera block list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) Alpha" in res.stdout
        assert "[2] (en) Beta" in res.stdout
        assert "[3] (en) Delta" in res.stdout

        res = run("littera section add 1 'SecC'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera section list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] SecA" in res.stdout
        assert "[2] SecB" in res.stdout
        assert "[3] SecC" in res.stdout


def test_export_import_preserves_document_order(tmp_path):
    """Multi-document JSON round-trip keeps chapter order and global block 1."""
    import json

    with init_work(tmp_path) as workdir:
        add_document(workdir, "DocA")
        add_document(workdir, "DocB")
        add_section(workdir, "SecA")
        res = run("littera section add 2 'SecB'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        add_block(workdir, "FromA")
        res = run("littera block add 2 'FromB'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera doc move 2 1", cwd=workdir)
        assert res.returncode == 0, res.stderr

        dest = workdir / "roundtrip.json"
        res = run(f"littera export json -o {dest}", cwd=workdir)
        assert res.returncode == 0, res.stderr
        payload = json.loads(dest.read_text(encoding="utf-8"))
        assert [d["title"] for d in payload["work"]["documents"]] == ["DocB", "DocA"]
        assert all("order_index" in d for d in payload["work"]["documents"])

        other = tmp_path / "other"
        other.mkdir()
        res = run("littera init .", cwd=other)
        assert res.returncode == 0, res.stderr
        res = run(f"littera import json {dest}", cwd=other)
        assert res.returncode == 0, res.stderr

        res = run("littera doc list", cwd=other)
        assert res.returncode == 0, res.stderr
        assert "[1] DocB" in res.stdout
        assert "[2] DocA" in res.stdout

        res = run("littera block list 1", cwd=other)
        assert res.returncode == 0, res.stderr
        assert "FromB" in res.stdout
        assert "FromA" not in res.stdout


def test_global_block_order_groups_null_section_index(tmp_path):
    """When section order_index ties, global block indexes stay inside each section."""
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir, "A")
        add_section(workdir, "B")
        run("littera block add 1 'A1'", cwd=workdir)
        run("littera block add 1 'A2'", cwd=workdir)
        run("littera block add 2 'B1'", cwd=workdir)
        run("littera block add 2 'B2'", cwd=workdir)

        with open_work_db(workdir) as db:
            db.conn.execute("UPDATE sections SET order_index = NULL")
            db.conn.commit()

        res = run("littera block list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) A1" in res.stdout
        assert "[2] (en) A2" in res.stdout
        res = run("littera block list 2", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) B1" in res.stdout
        assert "[2] (en) B2" in res.stdout

        res = run("littera entity add concept Target", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera mention add 2 concept Target", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera mention list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "A2" in res.stdout
        assert "B1" not in res.stdout


def test_export_import_preserves_moved_order(tmp_path):
    """Export then import keeps block order_index after a move."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")
        add_block(workdir, "Second")
        add_block(workdir, "Third")
        res = run("littera block move 3 1", cwd=workdir)
        assert res.returncode == 0, res.stderr

        dest = workdir / "roundtrip.json"
        res = run(f"littera export json -o {dest}", cwd=workdir)
        assert res.returncode == 0, res.stderr

        other = tmp_path / "other"
        other.mkdir()
        res = run("littera init .", cwd=other)
        assert res.returncode == 0, res.stderr
        res = run(f"littera import json {dest}", cwd=other)
        assert res.returncode == 0, res.stderr

        res = run("littera block list 1", cwd=other)
        assert res.returncode == 0, res.stderr
        assert "[1] (en) Third" in res.stdout
        assert "[2] (en) First" in res.stdout
        assert "[3] (en) Second" in res.stdout


def test_mention_index_follows_block_move(tmp_path):
    """Numeric mention selectors use order_index after a move."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")
        add_block(workdir, "Second")
        add_block(workdir, "Third")
        res = run("littera block move 3 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera entity add concept MovedTarget", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera mention add 1 concept MovedTarget", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera mention list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "MovedTarget" in res.stdout
        assert "Third" in res.stdout
        assert "First" not in res.stdout
        assert "Second" not in res.stdout


def test_migration_0003_backfills_existing_blocks(tmp_path):
    """Existing works get order_index when 0003 applies on open."""
    from littera.db.migrate import migrate
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "First")
        add_block(workdir, "Second")

        with open_work_db(workdir) as db:
            db.conn.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS order_index")
            db.conn.execute("DELETE FROM schema_version WHERE version = 3")
            db.conn.commit()

            applied = migrate(db.conn)
            assert applied == 1

            cur = db.conn.cursor()
            cur.execute(
                "SELECT source_text, order_index FROM blocks ORDER BY order_index, id"
            )
            rows = cur.fetchall()
            assert [r[0] for r in rows] == ["First", "Second"]
            assert [r[1] for r in rows] == [1, 2]


def test_section_index_follows_document_order(tmp_path):
    """Global section indexes follow document order_index after doc move."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "DocA")
        add_document(workdir, "DocB")
        add_section(workdir, "SecA")
        res = run("littera section add 2 'SecB'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera block add 1 'FromA'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        res = run("littera block add 2 'FromB'", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera doc move 2 1", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera block list 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "FromB" in res.stdout
        assert "FromA" not in res.stdout


def test_snapshot_second_write_does_not_clobber(tmp_path):
    """Two explicit snapshots in the same work keep both files."""
    from littera.cli.io import write_snapshot
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "Keep")
        with open_work_db(workdir) as db:
            dest1 = write_snapshot(workdir, db.conn, "draft")
            dest2 = write_snapshot(workdir, db.conn, "draft")
        assert dest1 != dest2
        assert dest1.exists()
        assert dest2.exists()
        assert "Keep" in dest1.read_text(encoding="utf-8")
        assert "Keep" in dest2.read_text(encoding="utf-8")


def test_import_appends_to_non_empty_work(tmp_path):
    """Importing into a work that already holds documents appends, never interleaves."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Imported1")
        add_document(workdir, "Imported2")

        dest = workdir / "payload.json"
        res = run(f"littera export json -o {dest}", cwd=workdir)
        assert res.returncode == 0, res.stderr

        other = tmp_path / "other"
        other.mkdir()
        res = run("littera init .", cwd=other)
        assert res.returncode == 0, res.stderr
        try:
            add_document(other, "Existing1")
            add_document(other, "Existing2")
            # Renumber the existing siblings the way a move does.
            res = run("littera doc move 1 1", cwd=other)
            assert res.returncode == 0, res.stderr

            res = run(f"littera import json {dest}", cwd=other)
            assert res.returncode == 0, res.stderr

            res = run("littera doc list", cwd=other)
            assert res.returncode == 0, res.stderr
            assert "[1] Existing1" in res.stdout
            assert "[2] Existing2" in res.stdout
            assert "[3] Imported1" in res.stdout
            assert "[4] Imported2" in res.stdout
        finally:
            _stop_postgres(other)


def test_import_appends_after_null_order_documents(tmp_path):
    """Documents created without an order_index still keep their place on import."""
    from littera.db.workdb import open_work_db

    with init_work(tmp_path) as workdir:
        add_document(workdir, "Imported1")

        dest = workdir / "payload.json"
        res = run(f"littera export json -o {dest}", cwd=workdir)
        assert res.returncode == 0, res.stderr

        other = tmp_path / "other"
        other.mkdir()
        res = run("littera init .", cwd=other)
        assert res.returncode == 0, res.stderr
        try:
            add_document(other, "Existing1")
            add_document(other, "Existing2")
            with open_work_db(other) as db:
                db.conn.execute("UPDATE documents SET order_index = NULL")
                db.conn.commit()

            res = run(f"littera import json {dest}", cwd=other)
            assert res.returncode == 0, res.stderr

            res = run("littera doc list", cwd=other)
            assert res.returncode == 0, res.stderr
            assert "[1] Existing1" in res.stdout
            assert "[2] Existing2" in res.stdout
            assert "[3] Imported1" in res.stdout
        finally:
            _stop_postgres(other)
