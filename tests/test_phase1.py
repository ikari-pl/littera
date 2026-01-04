"""
Comprehensive Phase 1 unit test suite.

- CLI editing (entity notes, block text)
- Undo/redo stack correctness
- Block creation/deletion invariants
- Cross‑command consistency
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import typer
from littera.cli import block_edit
from littera.cli import block_manage
from littera.cli import entity_note
from littera.db.workdb import open_work_db


def run_cli(app: typer.Typer, cmd: str, cwd: Path) -> str:
    import subprocess

    env = {"LITTERA_PG_LEASE_SECONDS": "0"}
    res = subprocess.run(
        cmd, cwd=cwd, shell=True, capture_output=True, text=True, env=env
    )
    return res.stdout


def test_entity_note_cli_roundtrip(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    run_cli(typer.Typer(), "littera init .", workdir)
    run_cli(typer.Typer(), "littera entity-add concept Being", workdir)
    run_cli(typer.Typer(), 'littera entity-note-set concept Being "Note A"', workdir)
    out = run_cli(typer.Typer(), "littera entity-note-show concept Being", workdir)
    assert "Note A" in out or "Note A" in out


def test_block_edit_cli_via_fallback(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    app = typer.Typer()
    block_edit.register(app)
    run_cli(app, "littera init .", workdir)
    run_cli(app, "littera doc-add Doc", workdir)
    run_cli(app, "littera section-add 1 Sec", workdir)
    run_cli(app, "littera block-add 1 --lang en 'Old'", workdir)

    # Simulate stdin input for block-edit fallback
    import subprocess

    echo = subprocess.Popen(["echo", "New"], stdout=subprocess.PIPE)
    edit = subprocess.run(
        ["littera", "block-edit", "1"],
        cwd=workdir,
        input="New\n",
        capture_output=True,
        text=True,
        env={"EDITOR": "", "LITTERA_PG_LEASE_SECONDS": "0"},
    )
    assert edit.returncode == 0
    out = run_cli(app, "littera block-list 1", workdir)
    assert "New" in out


def test_block_create_delete_cli(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    app = typer.Typer()
    block_manage.register(app)
    run_cli(app, "littera init .", workdir)
    run_cli(app, "littera doc-add Doc", workdir)
    run_cli(app, "littera section-add 1 Sec", workdir)
    run_cli(app, "littera block-create 1 'New block' --lang en", workdir)

    out = run_cli(app, "littera block-list 1", workdir)
    assert "New block" in out

    run_cli(app, "littera block-delete 1", workdir)

    out = run_cli(app, "littera block-list 1", workdir)
    assert "No blocks yet." in out


def test_undo_redo_flow(tmp_path: Path) -> None:
    from littera.tui.undo import UndoRedo, EditTarget

    undo = UndoRedo()
    target = EditTarget(kind="block_text", id=str(uuid.uuid4()))

    assert not undo.can_undo()
    assert not undo.can_redo()
    undo.record(target, "a", "b")
    assert undo.can_undo()
    assert not undo.can_redo()
    assert undo.pop_undo() is not None
    assert undo.pop_undo() is None
    assert undo.can_redo()
    assert undo.pop_redo() is not None


if __name__ == "__main__":
    import tempfile

    repo_root = Path(__file__).parents[3]
    with tempfile.TemporaryDirectory(dir=repo_root) as td:
        test_entity_note_cli_roundtrip(Path(td))
        test_block_edit_cli_via_fallback(Path(td))
        test_block_create_delete_cli(Path(td))
        test_undo_redo_flow(Path(td))
    print("Phase 1 unit tests passed")
