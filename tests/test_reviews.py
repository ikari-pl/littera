"""Tests for littera review add|list|edit|delete commands."""

from test_invariants import run, init_work, add_document, add_section, add_block


def test_review_add_global(tmp_path):
    """Add a review without scope (global review)."""
    with init_work(tmp_path) as workdir:
        res = run("littera review add 'Missing introduction'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Review added" in res.stdout
        assert "[medium]" in res.stdout


def test_review_add_scoped_to_block(tmp_path):
    """Add a review scoped to a specific block."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, "Some text")

        res = run(
            "littera review add 'Grammar issue here' --scope=block --scope-id=1",
            cwd=workdir,
        )
        assert res.returncode == 0, res.stderr
        assert "Review added" in res.stdout
        assert "block:1" in res.stdout


def test_review_list_empty(tmp_path):
    """List reviews when none exist."""
    with init_work(tmp_path) as workdir:
        res = run("littera review list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "No reviews yet." in res.stdout


def test_review_list_shows_reviews(tmp_path):
    """Add reviews then list them."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'First issue' --severity=high", cwd=workdir)
        run("littera review add 'Second issue' --severity=low", cwd=workdir)

        res = run("littera review list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "[1]" in res.stdout
        assert "[high]" in res.stdout
        assert "First issue" in res.stdout
        assert "[2]" in res.stdout
        assert "[low]" in res.stdout
        assert "Second issue" in res.stdout


def test_review_delete(tmp_path):
    """Add a review, delete it, verify it's gone."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'To be deleted'", cwd=workdir)

        res = run("littera review delete 1", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Review deleted" in res.stdout

        res = run("littera review list", cwd=workdir)
        assert "No reviews yet." in res.stdout


def test_review_add_invalid_severity(tmp_path):
    """Reject invalid severity value."""
    with init_work(tmp_path) as workdir:
        res = run("littera review add 'Bad review' --severity=critical", cwd=workdir)
        assert res.returncode != 0
        assert "Invalid severity" in res.stdout


def test_review_add_with_type_and_metadata(tmp_path):
    """Full options round-trip: type, severity, metadata."""
    with init_work(tmp_path) as workdir:
        res = run(
            """littera review add 'Inconsistent naming' --type=consistency --severity=high --metadata='{"ref": "ch1"}'""",
            cwd=workdir,
        )
        assert res.returncode == 0, res.stderr
        assert "Review added" in res.stdout

        res = run("littera review list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "(consistency)" in res.stdout
        assert "[high]" in res.stdout
        assert "Inconsistent naming" in res.stdout


def test_review_add_scoped_to_document(tmp_path):
    """Add a review scoped to a document."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "My Doc")

        res = run(
            "littera review add 'Document needs restructuring' --scope=document --scope-id=1",
            cwd=workdir,
        )
        assert res.returncode == 0, res.stderr
        assert "document:1" in res.stdout


def test_review_add_scoped_to_section(tmp_path):
    """Add a review scoped to a section."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir, "Intro")

        res = run(
            "littera review add 'Section too long' --scope=section --scope-id=1",
            cwd=workdir,
        )
        assert res.returncode == 0, res.stderr
        assert "section:1" in res.stdout


def test_review_add_invalid_scope(tmp_path):
    """Reject invalid scope value."""
    with init_work(tmp_path) as workdir:
        res = run("littera review add 'Bad scope' --scope=paragraph --scope-id=1", cwd=workdir)
        assert res.returncode != 0
        assert "Invalid scope" in res.stdout


def test_review_edit_description(tmp_path):
    """Edit a review description and see it in list."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Original text'", cwd=workdir)
        res = run("littera review edit 1 --description 'Revised text'", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Review updated" in res.stdout

        res = run("littera review list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Revised text" in res.stdout
        assert "Original text" not in res.stdout


def test_review_edit_severity(tmp_path):
    """Edit severity without changing description."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Keep this' --severity=low", cwd=workdir)
        res = run("littera review edit 1 --severity=high", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera review list", cwd=workdir)
        assert "[high]" in res.stdout
        assert "Keep this" in res.stdout


def test_review_edit_type(tmp_path):
    """Set and change issue type."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Naming' --type=style", cwd=workdir)
        res = run("littera review edit 1 --type=consistency", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera review list", cwd=workdir)
        assert "(consistency)" in res.stdout
        assert "(style)" not in res.stdout


def test_review_edit_nothing(tmp_path):
    """Reject edit with no fields."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Untouched'", cwd=workdir)
        res = run("littera review edit 1", cwd=workdir)
        assert res.returncode != 0
        assert "Nothing to change" in res.stdout


def test_review_edit_invalid_severity(tmp_path):
    """Reject invalid severity on edit."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Bad edit'", cwd=workdir)
        res = run("littera review edit 1 --severity=critical", cwd=workdir)
        assert res.returncode != 0
        assert "Invalid severity" in res.stdout


def test_review_edit_clear_scope(tmp_path):
    """Clear scope from a scoped review."""
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        run(
            "littera review add 'Scoped' --scope=document --scope-id=1",
            cwd=workdir,
        )
        res = run("littera review edit 1 --clear-scope", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera review list", cwd=workdir)
        assert "document:" not in res.stdout
        assert "Scoped" in res.stdout


def test_review_edit_empty_description(tmp_path):
    """Reject an empty description."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Keep me'", cwd=workdir)
        res = run("littera review edit 1 --description '   '", cwd=workdir)
        assert res.returncode != 0
        assert "Description cannot be empty" in res.stdout


def test_review_edit_scope_id_requires_scope(tmp_path):
    """--scope-id without --scope is rejected."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Scoped later'", cwd=workdir)
        res = run("littera review edit 1 --scope-id=1", cwd=workdir)
        assert res.returncode != 0
        assert "--scope-id requires --scope" in res.stdout


def test_review_edit_clear_scope_conflicts(tmp_path):
    """--clear-scope cannot combine with --scope."""
    with init_work(tmp_path) as workdir:
        run("littera review add 'Conflict'", cwd=workdir)
        res = run("littera review edit 1 --clear-scope --scope=work", cwd=workdir)
        assert res.returncode != 0
        assert "--clear-scope cannot be combined" in res.stdout
