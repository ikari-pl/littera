"""Tests for entity property constraints and their effect on morphology."""

from pathlib import Path

from littera.linguistics.en import surface_form
from tests.test_invariants import (
    add_block,
    add_document,
    add_section,
    init_work,
    run,
)


# ── Unit tests: surface_form with properties ────────────────────


def test_uncountable_skips_pluralization():
    result = surface_form("information", {"number": "pl"}, {"countable": "no"})
    assert result == "information"


def test_countable_yes_pluralizes():
    result = surface_form("algorithm", {"number": "pl"}, {"countable": "yes"})
    assert result == "algorithms"


def test_no_properties_pluralizes_normally():
    result = surface_form("algorithm", {"number": "pl"}, None)
    assert result == "algorithms"


def test_uncountable_still_gets_possessive():
    result = surface_form(
        "information", {"number": "pl", "case": "poss"}, {"countable": "no"}
    )
    assert result == "information's"


def test_uncountable_singular_possessive():
    result = surface_form("information", {"case": "poss"}, {"countable": "no"})
    assert result == "information's"


def test_empty_properties_pluralizes():
    result = surface_form("algorithm", {"number": "pl"}, {})
    assert result == "algorithms"


def test_uncountable_with_article():
    result = surface_form(
        "information", {"article": "the"}, {"countable": "no"}
    )
    assert result == "the information"


# ── CLI integration tests: property commands ─────────────────────


def test_property_set_and_list(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity add concept algorithm", cwd=workdir)
        res = run(
            "littera entity property-set algorithm countable=yes", cwd=workdir
        )
        assert res.returncode == 0
        assert "countable=yes" in res.stdout

        res = run("littera entity property-list algorithm", cwd=workdir)
        assert res.returncode == 0
        assert "countable: yes" in res.stdout


def test_property_set_multiple_pairs(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity add concept algorithm", cwd=workdir)
        res = run(
            "littera entity property-set algorithm countable=yes category=abstract",
            cwd=workdir,
        )
        assert res.returncode == 0

        res = run("littera entity property-list algorithm", cwd=workdir)
        assert res.returncode == 0
        assert "countable: yes" in res.stdout
        assert "category: abstract" in res.stdout


def test_property_set_merges_with_existing(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity add concept algorithm", cwd=workdir)
        run(
            "littera entity property-set algorithm countable=yes", cwd=workdir
        )
        run(
            "littera entity property-set algorithm category=abstract",
            cwd=workdir,
        )

        res = run("littera entity property-list algorithm", cwd=workdir)
        assert res.returncode == 0
        assert "countable: yes" in res.stdout
        assert "category: abstract" in res.stdout


def test_property_delete(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity add concept algorithm", cwd=workdir)
        run(
            "littera entity property-set algorithm countable=yes", cwd=workdir
        )

        res = run(
            "littera entity property-delete algorithm countable", cwd=workdir
        )
        assert res.returncode == 0
        assert "deleted" in res.stdout

        res = run("littera entity property-list algorithm", cwd=workdir)
        assert "No properties" in res.stdout


def test_property_delete_nonexistent_key(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity add concept algorithm", cwd=workdir)
        res = run(
            "littera entity property-delete algorithm nonexistent", cwd=workdir
        )
        assert res.returncode != 0


def test_entity_list_shows_properties(tmp_path):
    with init_work(tmp_path) as workdir:
        run("littera entity add concept algorithm", cwd=workdir)
        run("littera entity add person 'Anna'", cwd=workdir)
        run(
            "littera entity property-set algorithm countable=yes", cwd=workdir
        )

        res = run("littera entity list", cwd=workdir)
        assert res.returncode == 0
        assert "{countable: yes}" in res.stdout
        # Anna has no properties — no braces shown
        lines = res.stdout.strip().split("\n")
        anna_line = [l for l in lines if "Anna" in l][0]
        assert "{" not in anna_line


def test_inflect_countable_no(tmp_path):
    res = run("littera inflect information --plural --countable=no", cwd=tmp_path)
    assert res.returncode == 0
    assert res.stdout.strip() == "information"


def test_inflect_countable_yes(tmp_path):
    res = run("littera inflect algorithm --plural --countable=yes", cwd=tmp_path)
    assert res.returncode == 0
    assert res.stdout.strip() == "algorithms"


def test_inflect_without_countable(tmp_path):
    res = run("littera inflect algorithm --plural", cwd=tmp_path)
    assert res.returncode == 0
    assert res.stdout.strip() == "algorithms"


def test_mention_set_surface_respects_countability(tmp_path):
    """Full pipeline: entity + property + label + block + mention → set-surface."""
    with init_work(tmp_path) as workdir:
        # Set up document structure
        add_document(workdir, "Doc")
        add_section(workdir, "Section")
        add_block(workdir, "Some text about information", "en")

        # Create entity with uncountable property
        run("littera entity add concept information", cwd=workdir)
        run(
            "littera entity property-set information countable=no", cwd=workdir
        )
        run(
            "littera entity label-add information en information", cwd=workdir
        )

        # Add mention and set surface form with --plural
        run("littera mention add 1 concept information", cwd=workdir)
        res = run("littera mention set-surface 1 --plural", cwd=workdir)
        assert res.returncode == 0
        # Should NOT pluralize because countable=no
        assert '"information"' in res.stdout


def test_mention_set_surface_countable_entity(tmp_path):
    """Countable entity pluralizes normally."""
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Doc")
        add_section(workdir, "Section")
        add_block(workdir, "Some text about algorithms", "en")

        run("littera entity add concept algorithm", cwd=workdir)
        run(
            "littera entity property-set algorithm countable=yes", cwd=workdir
        )
        run("littera entity label-add algorithm en algorithm", cwd=workdir)

        run("littera mention add 1 concept algorithm", cwd=workdir)
        res = run("littera mention set-surface 1 --plural", cwd=workdir)
        assert res.returncode == 0
        assert '"algorithms"' in res.stdout
