import os
import signal
import subprocess
from contextlib import contextmanager
from pathlib import Path


# --- helpers -------------------------------------------------


def run(cmd: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a CLI command in a work directory."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": os.environ.get("PATH", "")},
    )


def _stop_postgres(workdir: Path) -> None:
    littera_dir = workdir / ".littera"
    data_dir = littera_dir / "pgdata"
    pg_ctl = littera_dir / "pg" / "bin" / "pg_ctl"

    if pg_ctl.exists() and data_dir.exists():
        subprocess.run(
            [
                str(pg_ctl),
                "-D",
                str(data_dir),
                "-m",
                "immediate",
                "-w",
                "stop",
            ],
            capture_output=True,
            text=True,
        )

    pid_file = data_dir / "postmaster.pid"
    if not pid_file.exists():
        return

    try:
        pid = int(pid_file.read_text().splitlines()[0])
    except Exception:
        return

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


@contextmanager
def init_work(tmp_path: Path):
    """Initialize a fresh Littera work and always stop Postgres."""
    workdir = tmp_path / "work"
    workdir.mkdir(parents=True, exist_ok=True)

    res = run("littera init .", cwd=workdir)
    assert res.returncode == 0, res.stderr

    try:
        yield workdir
    finally:
        _stop_postgres(workdir)


def add_document(workdir: Path, title: str = "Doc") -> None:
    res = run(f"littera doc-add '{title}'", cwd=workdir)
    assert res.returncode == 0, res.stderr


def add_section(workdir: Path, title: str = "Section") -> None:
    # assumes single document
    res = run(f"littera section-add 1 '{title}'", cwd=workdir)
    assert res.returncode == 0, res.stderr


def add_block(workdir: Path, text: str = "Text", lang: str = "en") -> None:
    # assumes single section
    res = run(f"littera block-add 1 --lang {lang} '{text}'", cwd=workdir)
    assert res.returncode == 0, res.stderr


# --- invariants ----------------------------------------------


def test_cli_help_works(tmp_path):
    res = run("littera --help", cwd=tmp_path)
    assert res.returncode == 0
    assert "Littera" in res.stdout


def test_status_fails_if_not_initialized(tmp_path):
    res = run("littera status", cwd=tmp_path)
    assert res.returncode != 0


def test_init_creates_work(tmp_path):
    with init_work(tmp_path) as workdir:
        config = (workdir / ".littera" / "config.yml").read_text()
        assert "work:" in config


def test_doc_add_attached_to_work(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera doc-add 'Test doc'", cwd=workdir)
        res = run("littera doc-list", cwd=workdir)

        assert res.returncode == 0
        assert "Test doc" in res.stdout


def test_section_requires_document(tmp_path):
    with init_work(tmp_path) as workdir:
        # No documents yet, section-add must fail
        res = run("littera section-add 1 'Intro'", cwd=workdir)
        assert res.returncode != 0


def test_block_requires_section(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera doc-add 'Doc'", cwd=workdir)

        # No sections yet, block-add must fail
        res = run("littera block-add 1 --lang en 'Text'", cwd=workdir)
        assert res.returncode != 0


def test_entities_exist_without_documents(tmp_path):
    # Entities are not scoped to documents/sections/blocks.
    with init_work(tmp_path) as workdir:
        run("littera entity-add concept 'Time'", cwd=workdir)
        res = run("littera entity-list", cwd=workdir)
        assert res.returncode == 0
        assert "Time" in res.stdout


def test_entity_notes_round_trip(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity-add concept 'Being'", cwd=workdir)
        run("littera entity-note-set concept Being 'Note A'", cwd=workdir)

        res = run("littera entity-note-show concept Being", cwd=workdir)
        assert res.returncode == 0
        assert "Note A" in res.stdout


def test_block_is_required_for_mentions(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity-add concept 'Truth'", cwd=workdir)
        res = run("littera mention-add 1 concept Truth", cwd=workdir)
        assert res.returncode != 0


def test_status_recovers_from_stale_pid_file(tmp_path):
    with init_work(tmp_path) as workdir:
        pid_file = workdir / ".littera" / "pgdata" / "postmaster.pid"

        # Simulate a stale pid file (process doesn't exist).
        pid_file.write_text("999999\n")

        # status should auto-start embedded Postgres.
        res = run("littera status", cwd=workdir)
        assert res.returncode == 0
        assert "Embedded Postgres available" in res.stdout
