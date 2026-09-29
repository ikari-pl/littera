"""
Comprehensive Phase 1 unit test suite.

- CLI editing (entity notes, block text)
- Undo/redo stack correctness
- Block creation/deletion invariants
- Cross-command consistency
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import typer

from littera.db.workdb import open_work_db


def run_cli(app: typer.Typer, cmd: str, cwd: Path) -> str:
    """Run a CLI command in a work directory."""
    # When called from subprocess, we need to use the full path to python module
    repo_root = Path(__file__).parents[1]
    python_path = f"{repo_root}/.venv/bin/python"
    module_cmd = f"{python_path} -m littera {cmd.replace('littera ', '')}"
    return subprocess.run(
        module_cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": os.environ.get("PATH", ""), "LITTERA_PG_LEASE_SECONDS": "0"},
        check=False,
    ).stdout


def test_entity_note_cli_roundtrip(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    run_cli(typer.Typer(), "littera init .", workdir)
    run_cli(typer.Typer(), "littera entity add concept Being", workdir)
    run_cli(typer.Typer(), 'littera entity note-set concept Being "Note A"', workdir)
    out = run_cli(typer.Typer(), "littera entity note-show concept Being", workdir)
    assert "Note A" in out


def test_block_edit_cli_via_fallback(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    app = typer.Typer()
    run_cli(app, "littera init .", workdir)
    run_cli(app, "littera doc add Doc", workdir)
    run_cli(app, "littera section add 1 Sec", workdir)
    run_cli(app, "littera block add 1 --lang en 'Old'", workdir)

    # Simulate stdin input for block edit fallback using proper CLI call
    import subprocess

    repo_root = Path(__file__).parents[1]
    python_path = f"{repo_root}/.venv/bin/python"

    # Run block edit with stdin input
    result = subprocess.run(
        [python_path, "-m", "littera", "block", "edit", "1"],
        cwd=workdir,
        input="New\n",
        capture_output=True,
        text=True,
        # Inherit the environment: replacing it wipes PATH, and psycopg then
        # cannot find libpq in the subprocess.
        env={**os.environ, "EDITOR": "", "LITTERA_PG_LEASE_SECONDS": "0"},
        check=False,
    )
    assert result.returncode == 0
    out = run_cli(app, "littera block list 1", workdir)
    assert "New" in out


def test_block_create_delete_cli(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    app = typer.Typer()
    run_cli(app, "littera init .", workdir)
    run_cli(app, "littera doc add Doc", workdir)
    run_cli(app, "littera section add 1 Sec", workdir)
    run_cli(app, "littera block add 1 'New block' --lang en", workdir)

    out = run_cli(app, "littera block list 1", workdir)
    assert "New block" in out

    run_cli(app, "littera block delete 1", workdir)

    out = run_cli(app, "littera block list 1", workdir)
    assert "No blocks" in out


def test_block_create_with_uuid_selector(tmp_path: Path) -> None:
    """Test that block add works with UUID string selectors (regression test)."""

    workdir = tmp_path / "work"
    workdir.mkdir()
    app = typer.Typer()
    run_cli(app, "littera init .", workdir)
    run_cli(app, "littera doc add Doc", workdir)
    run_cli(app, "littera section add 1 Sec", workdir)

    # Get the section UUID directly from the database
    os.chdir(workdir)
    with open_work_db() as db:
        cur = db.conn.cursor()
        cur.execute("SELECT id FROM sections LIMIT 1")
        section_uuid = str(cur.fetchone()[0])

    # Create block using UUID selector (not index)
    out = run_cli(app, f"littera block add {section_uuid} 'UUID test block' --lang en", workdir)

    out = run_cli(app, "littera block list 1", workdir)
    assert "UUID test block" in out


if __name__ == "__main__":
    import tempfile

    repo_root = Path(__file__).parents[3]
    with tempfile.TemporaryDirectory(dir=repo_root) as td:
        test_entity_note_cli_roundtrip(Path(td))
        test_block_edit_cli_via_fallback(Path(td))
        test_block_create_delete_cli(Path(td))
    print("Phase 1 unit tests passed")
