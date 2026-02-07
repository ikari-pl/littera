"""Tests for littera review add|list|delete commands."""

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
