"""Tests for Polish morphology: PoliMorf lookup, dispatch, CLI, integration.

Unit tests (no DB) + CLI integration tests (real embedded PG).
"""

import json

import pytest

from littera.linguistics.pl import surface_form
from littera.linguistics.dispatch import surface_form as dispatch_surface_form

# Re-use test helpers from test_invariants
from tests.test_invariants import (
    init_work,
    run,
    add_document,
    add_section,
    add_block,
)


# ── Unit tests (PoliMorf SQLite, no PG) ────────────────────────────────────


class TestPolishSurfaceForm:
    def test_no_features_returns_base(self):
        assert surface_form("algorytm") == "algorytm"

    def test_empty_features_returns_base(self):
        assert surface_form("algorytm", {}) == "algorytm"

    def test_genitive_singular(self):
        assert surface_form("algorytm", {"case": "gen"}, {"gender": "m3"}) == "algorytmu"

    def test_genitive_plural(self):
        result = surface_form("algorytm", {"case": "gen", "number": "pl"}, {"gender": "m3"})
        assert result == "algorytmów"

    def test_instrumental_feminine(self):
        assert surface_form("Warszawa", {"case": "inst"}, {"gender": "f"}) == "Warszawą"

    def test_dative_singular(self):
        assert surface_form("algorytm", {"case": "dat"}, {"gender": "m3"}) == "algorytmowi"

    def test_locative_singular(self):
        assert surface_form("algorytm", {"case": "loc"}, {"gender": "m3"}) == "algorytmie"

    def test_vocative_singular(self):
        assert surface_form("algorytm", {"case": "voc"}, {"gender": "m3"}) == "algorytmie"

    def test_accusative_singular(self):
        assert surface_form("algorytm", {"case": "acc"}, {"gender": "m3"}) == "algorytm"

    def test_nominative_singular_returns_base(self):
        assert surface_form("algorytm", {"case": "nom"}, {"gender": "m3"}) == "algorytm"

    def test_nominative_plural(self):
        assert surface_form("algorytm", {"case": "nom", "number": "pl"}, {"gender": "m3"}) == "algorytmy"

    def test_unknown_word_returns_base(self):
        assert surface_form("xyzzyplugh", {"case": "gen"}, {"gender": "m3"}) == "xyzzyplugh"

    def test_gender_inferred_from_dict(self):
        # algorytm has unambiguous gender m3 in PoliMorf
        assert surface_form("algorytm", {"case": "gen"}) == "algorytmu"

    def test_invalid_case_returns_base(self):
        # "poss" is English, not valid for Polish
        assert surface_form("algorytm", {"case": "poss"}, {"gender": "m3"}) == "algorytm"

    def test_invalid_number_returns_base(self):
        assert surface_form("algorytm", {"case": "gen", "number": "dual"}, {"gender": "m3"}) == "algorytm"

    def test_invalid_gender_ignored(self):
        # Invalid gender falls back to inference
        assert surface_form("algorytm", {"case": "gen"}, {"gender": "xx"}) == "algorytmu"


class TestDeclensionOverride:
    def test_override_takes_precedence(self):
        props = {
            "gender": "f",
            "declension_override": json.dumps({
                "gen": "Szymborskiej",
                "dat": "Szymborskiej",
            }),
        }
        assert surface_form("Szymborska", {"case": "gen"}, props) == "Szymborskiej"

    def test_override_with_number_key(self):
        props = {
            "gender": "m3",
            "declension_override": json.dumps({
                "gen": "custom_sg",
                "pl:gen": "custom_pl",
            }),
        }
        assert surface_form("test", {"case": "gen"}, props) == "custom_sg"
        assert surface_form("test", {"case": "gen", "number": "pl"}, props) == "custom_pl"

    def test_override_as_dict(self):
        # Properties can be a dict (already parsed from JSONB)
        props = {
            "gender": "f",
            "declension_override": {"gen": "customgen"},
        }
        assert surface_form("test", {"case": "gen"}, props) == "customgen"


# ── Dispatch tests ──────────────────────────────────────────────────────────


class TestDispatch:
    def test_dispatch_english(self):
        assert dispatch_surface_form("en", "algorithm", {"number": "pl"}) == "algorithms"

    def test_dispatch_polish(self):
        assert dispatch_surface_form("pl", "algorytm", {"case": "gen"}, {"gender": "m3"}) == "algorytmu"

    def test_dispatch_unknown_language(self):
        assert dispatch_surface_form("de", "Algorithmus", {"case": "gen"}) == "Algorithmus"


# ── CLI tests (no PG needed) ───────────────────────────────────────────────


class TestInflectCLIPolish:
    def test_inflect_polish_genitive(self, tmp_path):
        res = run("littera inflect algorytm --lang=pl --case=gen --gender=m3", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "algorytmu"

    def test_inflect_polish_instrumental_feminine(self, tmp_path):
        res = run("littera inflect Warszawa --lang=pl --case=inst --gender=f", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "Warszawą"

    def test_inflect_polish_gender_inferred(self, tmp_path):
        res = run("littera inflect algorytm --lang=pl --case=gen", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "algorytmu"

    def test_inflect_english_still_works(self, tmp_path):
        res = run("littera inflect algorithm --plural", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "algorithms"

    def test_inflect_english_possessive_still_works(self, tmp_path):
        res = run("littera inflect algorithm --possessive", cwd=tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "algorithm's"

    def test_inflect_polish_rejects_article(self, tmp_path):
        res = run("littera inflect algorytm --lang=pl --article=a", cwd=tmp_path)
        assert res.returncode != 0

    def test_inflect_polish_rejects_possessive(self, tmp_path):
        res = run("littera inflect algorytm --lang=pl --possessive", cwd=tmp_path)
        assert res.returncode != 0

    def test_inflect_case_and_possessive_mutually_exclusive(self, tmp_path):
        res = run("littera inflect algorithm --possessive --case=poss", cwd=tmp_path)
        assert res.returncode != 0


# ── Integration tests (real embedded PG) ────────────────────────────────────


class TestMentionSetSurfacePolish:
    def test_mention_set_surface_polish_genitive(self, tmp_path):
        """Full round-trip: entity with gender → pl mention → set-surface --case=gen."""
        with init_work(tmp_path) as workdir:
            run("littera entity add concept algorytm", cwd=workdir)
            run("littera entity label-add algorytm pl algorytm", cwd=workdir)
            run("littera entity property-set algorytm gender=m3", cwd=workdir)
            add_document(workdir, "Essay")
            add_section(workdir, "Polish")
            add_block(workdir, "O algorytmach", lang="pl")
            run("littera mention add 1 concept algorytm", cwd=workdir)

            res = run("littera mention set-surface 1 --case=gen", cwd=workdir)
            assert res.returncode == 0, res.stderr
            assert "algorytmu" in res.stdout

            # Verify in listing
            res = run("littera mention list", cwd=workdir)
            assert res.returncode == 0
            assert 'surface: "algorytmu"' in res.stdout

    def test_mention_set_surface_english_possessive_unchanged(self, tmp_path):
        """--possessive still works for English mentions."""
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

    def test_mention_set_surface_case_flag_english(self, tmp_path):
        """--case=poss works same as --possessive for English."""
        with init_work(tmp_path) as workdir:
            run("littera entity add concept algorithm", cwd=workdir)
            run("littera entity label-add algorithm en algorithm", cwd=workdir)
            add_document(workdir, "Test")
            add_section(workdir, "Section")
            add_block(workdir, "About algorithms")
            run("littera mention add 1 concept algorithm", cwd=workdir)

            res = run("littera mention set-surface 1 --case=poss", cwd=workdir)
            assert res.returncode == 0, res.stderr
            assert "algorithm's" in res.stdout

    def test_features_round_trip_polish(self, tmp_path):
        """Features JSONB stores Polish case correctly."""
        with init_work(tmp_path) as workdir:
            run("littera entity add concept algorytm", cwd=workdir)
            run("littera entity label-add algorytm pl algorytm", cwd=workdir)
            run("littera entity property-set algorytm gender=m3", cwd=workdir)
            add_document(workdir, "Essay")
            add_section(workdir, "Polish")
            add_block(workdir, "O algorytmach", lang="pl")
            run("littera mention add 1 concept algorytm", cwd=workdir)

            res = run("littera mention set-surface 1 --case=gen", cwd=workdir)
            assert res.returncode == 0, res.stderr

            # Verify features stored correctly by querying DB directly
            from littera.db.workdb import open_work_db
            import os

            os.chdir(workdir)
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute("SELECT features, surface_form FROM mentions LIMIT 1")
                features, sform = cur.fetchone()

            assert features == {"case": "gen"}
            assert sform == "algorytmu"

    def test_mention_set_surface_case_and_possessive_error(self, tmp_path):
        """--case and --possessive together produce an error."""
        with init_work(tmp_path) as workdir:
            run("littera entity add concept algorithm", cwd=workdir)
            run("littera entity label-add algorithm en algorithm", cwd=workdir)
            add_document(workdir, "Test")
            add_section(workdir, "Section")
            add_block(workdir, "About algorithms")
            run("littera mention add 1 concept algorithm", cwd=workdir)

            res = run("littera mention set-surface 1 --possessive --case=gen", cwd=workdir)
            assert res.returncode != 0
