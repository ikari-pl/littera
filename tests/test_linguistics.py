"""Tests for the linguistics spike: English surface form generation.

Unit tests (no DB) + CLI integration tests (real embedded PG).
"""

import json

import pytest

from littera.linguistics.en import surface_form

# Re-use test helpers from test_invariants
from tests.test_invariants import (
    init_work,
    run,
    add_document,
    add_section,
    add_block,
)


# ── Unit tests (no DB) ──────────────────────────────────────────────────────


class TestSurfaceForm:
    def test_no_features_returns_base(self):
        assert surface_form("algorithm", None) == "algorithm"

    def test_empty_features_returns_base(self):
        assert surface_form("algorithm", {}) == "algorithm"

    def test_plural(self):
        assert surface_form("algorithm", {"number": "pl"}) == "algorithms"

    def test_possessive_singular(self):
        assert surface_form("algorithm", {"case": "poss"}) == "algorithm's"

    def test_plural_possessive(self):
        assert surface_form("algorithm", {"number": "pl", "case": "poss"}) == "algorithms'"

    def test_proper_noun_possessive(self):
        assert surface_form("Anna Karenina", {"case": "poss"}) == "Anna Karenina's"

    def test_proper_noun_not_pluralized(self):
        assert surface_form("Anna Karenina", {"number": "pl"}) == "Anna Karenina"

    def test_article_a_consonant(self):
        assert surface_form("cat", {"article": "a"}) == "a cat"

    def test_article_a_vowel_sound(self):
        assert surface_form("algorithm", {"article": "a"}) == "an algorithm"

    def test_article_a_umbrella(self):
        assert surface_form("umbrella", {"article": "a"}) == "an umbrella"

    def test_article_the(self):
        assert surface_form("cat", {"article": "the"}) == "the cat"

    def test_plural_with_article_the(self):
        assert surface_form("cat", {"number": "pl", "article": "the"}) == "the cats"

    def test_all_features_combined(self):
        result = surface_form("algorithm", {"number": "pl", "case": "poss", "article": "the"})
        assert result == "the algorithms'"


# ── CLI integration tests ────────────────────────────────────────────────────


class TestInflectCLI:
    def test_inflect_plural(self, tmp_path):
        res = run("littera inflect algorithm --plural", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "algorithms"

    def test_inflect_plural_possessive(self, tmp_path):
        res = run("littera inflect algorithm --plural --possessive", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "algorithms'"

    def test_inflect_possessive(self, tmp_path):
        res = run('littera inflect "Anna Karenina" --possessive', cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "Anna Karenina's"

    def test_inflect_article(self, tmp_path):
        res = run("littera inflect algorithm --article=a", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "an algorithm"


class TestMentionSetSurface:
    def test_set_surface_plural(self, tmp_path):
        with init_work(tmp_path) as workdir:
            # Set up: entity + label + doc + section + block + mention
            run("littera entity add concept algorithm", cwd=workdir)
            run("littera entity label-add algorithm en algorithm", cwd=workdir)
            add_document(workdir, "Test")
            add_section(workdir, "Section")
            add_block(workdir, "About algorithms")
            run("littera mention add 1 concept algorithm", cwd=workdir)

            # Set surface form
            res = run("littera mention set-surface 1 --plural", cwd=workdir)
            assert res.returncode == 0, res.stderr
            assert "algorithms" in res.stdout

            # Verify in listing
            res = run("littera mention list", cwd=workdir)
            assert res.returncode == 0
            assert 'surface: "algorithms"' in res.stdout

    def test_set_surface_possessive(self, tmp_path):
        with init_work(tmp_path) as workdir:
            run("littera entity add person 'Anna Karenina'", cwd=workdir)
            run("littera entity label-add 'Anna Karenina' en 'Anna Karenina'", cwd=workdir)
            add_document(workdir, "Test")
            add_section(workdir, "Section")
            add_block(workdir, "About Anna")
            run("littera mention add 1 person 'Anna Karenina'", cwd=workdir)

            res = run("littera mention set-surface 1 --possessive", cwd=workdir)
            assert res.returncode == 0, res.stderr
            assert "Anna Karenina's" in res.stdout

    def test_features_round_trip_jsonb(self, tmp_path):
        """Features dict round-trips through JSONB correctly."""
        with init_work(tmp_path) as workdir:
            run("littera entity add concept algorithm", cwd=workdir)
            run("littera entity label-add algorithm en algorithm", cwd=workdir)
            add_document(workdir, "Test")
            add_section(workdir, "Section")
            add_block(workdir, "About algorithms")
            run("littera mention add 1 concept algorithm", cwd=workdir)

            res = run("littera mention set-surface 1 --plural --possessive --article=a", cwd=workdir)
            assert res.returncode == 0, res.stderr

            # Verify features stored correctly by querying DB directly
            from littera.db.workdb import open_work_db
            import os

            os.chdir(workdir)
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute("SELECT features, surface_form FROM mentions LIMIT 1")
                features, sform = cur.fetchone()

            expected_features = {"number": "pl", "case": "poss", "article": "a"}
            assert features == expected_features
            assert sform == "an algorithms'"
