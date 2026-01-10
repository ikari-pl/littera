from pathlib import Path

from test_invariants import run, init_work, add_document, add_section, add_block


# --- entity invariants ---------------------------------------


def test_entity_requires_work(tmp_path: Path):
    workdir = tmp_path / "work"
    workdir.mkdir()

    # entity add must fail if work not initialized
    res = run("littera entity add Character Anna", cwd=workdir)
    assert res.returncode != 0


def test_entity_add_and_list(tmp_path: Path):
    with init_work(tmp_path) as workdir:
        res = run("littera entity add Character Anna", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera entity list", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Anna" in res.stdout


def test_entity_requires_block_for_mention(tmp_path: Path):
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)

        # entity must exist first
        res = run("littera entity add Character Anna", cwd=workdir)
        assert res.returncode == 0, res.stderr

        # Cannot add mention without a block
        res = run("littera mention add 1 Character Anna", cwd=workdir)
        assert res.returncode != 0


def test_entity_mention_lifecycle(tmp_path: Path):
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir)

        res = run("littera entity add Character Anna", cwd=workdir)
        assert res.returncode == 0, res.stderr

        res = run("littera mention add 1 Character Anna", cwd=workdir)
        assert res.returncode == 0, res.stderr
