"""Label aliases are editable from the CLI (the authoritative interface).

Before this, only the desktop sidecar and JSON import could write
entity_labels.aliases. Black-box CLI tests on embedded Postgres, no mocks.
"""

from __future__ import annotations

from test_invariants import init_work, run


def _ok(cmd: str, workdir) -> str:
    res = run(cmd, cwd=workdir)
    assert res.returncode == 0, f"{cmd}\n{res.stdout}\n{res.stderr}"
    return res.stdout


def _labels(workdir) -> str:
    return _ok("littera entity label-list Alice", workdir)


def test_aliases_are_added_kept_and_removed(tmp_path):
    with init_work(tmp_path) as workdir:
        _ok("littera entity add person Alice", workdir)

        _ok("littera entity label-add Alice en Alice --alias Ally --alias Al", workdir)
        assert "en: Alice  (aliases: ['Ally', 'Al'])" in _labels(workdir)

        # Adding more never drops the ones already there.
        _ok("littera entity label-add Alice en Alice --alias Ali --alias Ally", workdir)
        assert "(aliases: ['Ally', 'Al', 'Ali'])" in _labels(workdir)

        # Changing only the base form keeps the aliases too.
        _ok("littera entity label-add Alice en Alicia", workdir)
        assert "en: Alicia  (aliases: ['Ally', 'Al', 'Ali'])" in _labels(workdir)

        _ok("littera entity label-alias-remove Alice en Al", workdir)
        assert "(aliases: ['Ally', 'Ali'])" in _labels(workdir)

        _ok("littera entity label-alias-remove Alice en Ally", workdir)
        _ok("littera entity label-alias-remove Alice en Ali", workdir)
        out = _labels(workdir)
        assert "en: Alicia" in out
        assert "aliases" not in out


def test_alias_edits_refuse_what_they_cannot_do(tmp_path):
    with init_work(tmp_path) as workdir:
        _ok("littera entity add person Alice", workdir)
        _ok("littera entity label-add Alice en Alice --alias Ally", workdir)

        res = run("littera entity label-alias-remove Alice en Nobody", cwd=workdir)
        assert res.returncode != 0
        assert "Nobody" in res.stdout

        res = run("littera entity label-alias-remove Alice pl Ala", cwd=workdir)
        assert res.returncode != 0
        assert "No pl label" in res.stdout

        res = run("littera entity label-add Alice en Alice --alias '  '", cwd=workdir)
        assert res.returncode != 0
        assert "(aliases: ['Ally'])" in _labels(workdir)
