"""Comprehensive tests for English morphology engine.

Unit tests (no DB) covering nouns, verbs, adjectives, overrides, and dispatch.
"""

import json

import pytest

from littera.linguistics.en import surface_form
from littera.linguistics.dispatch import surface_form as dispatch_surface_form


# ── Noun plurals: regular ────────────────────────────────────────────────────


class TestRegularPlurals:
    def test_add_s(self):
        assert surface_form("cat", {"number": "pl"}) == "cats"

    def test_add_s_dog(self):
        assert surface_form("dog", {"number": "pl"}) == "dogs"

    def test_add_s_book(self):
        assert surface_form("book", {"number": "pl"}) == "books"

    def test_add_es_box(self):
        assert surface_form("box", {"number": "pl"}) == "boxes"

    def test_add_es_bus(self):
        assert surface_form("bus", {"number": "pl"}) == "buses"

    def test_add_es_church(self):
        assert surface_form("church", {"number": "pl"}) == "churches"

    def test_add_es_dish(self):
        assert surface_form("dish", {"number": "pl"}) == "dishes"

    def test_y_to_ies(self):
        assert surface_form("baby", {"number": "pl"}) == "babies"

    def test_y_to_ies_city(self):
        assert surface_form("city", {"number": "pl"}) == "cities"

    def test_y_to_ies_story(self):
        assert surface_form("story", {"number": "pl"}) == "stories"

    def test_vowel_y_stays(self):
        assert surface_form("key", {"number": "pl"}) == "keys"

    def test_vowel_y_stays_day(self):
        assert surface_form("day", {"number": "pl"}) == "days"

    def test_f_to_ves_knife(self):
        assert surface_form("knife", {"number": "pl"}) == "knives"

    def test_f_to_ves_life(self):
        assert surface_form("life", {"number": "pl"}) == "lives"

    def test_singular_unchanged(self):
        assert surface_form("cat", {"number": "sg"}) == "cat"


# ── Noun plurals: irregular ──────────────────────────────────────────────────


class TestIrregularPlurals:
    def test_child(self):
        assert surface_form("child", {"number": "pl"}) == "children"

    def test_mouse(self):
        assert surface_form("mouse", {"number": "pl"}) == "mice"

    def test_person(self):
        assert surface_form("person", {"number": "pl"}) == "people"

    def test_man(self):
        assert surface_form("man", {"number": "pl"}) == "men"

    def test_woman(self):
        assert surface_form("woman", {"number": "pl"}) == "women"

    def test_foot(self):
        assert surface_form("foot", {"number": "pl"}) == "feet"

    def test_tooth(self):
        assert surface_form("tooth", {"number": "pl"}) == "teeth"

    def test_goose(self):
        assert surface_form("goose", {"number": "pl"}) == "geese"

    def test_ox(self):
        assert surface_form("ox", {"number": "pl"}) == "oxen"

    def test_datum(self):
        assert surface_form("datum", {"number": "pl"}) == "data"

    def test_crisis(self):
        assert surface_form("crisis", {"number": "pl"}) == "crises"

    def test_phenomenon(self):
        assert surface_form("phenomenon", {"number": "pl"}) == "phenomena"


# ── Possessives ──────────────────────────────────────────────────────────────


class TestPossessives:
    def test_singular_possessive(self):
        assert surface_form("cat", {"case": "poss"}) == "cat's"

    def test_singular_possessive_ending_s(self):
        assert surface_form("James", {"case": "poss"}) == "James'"

    def test_plural_possessive(self):
        assert surface_form("cat", {"number": "pl", "case": "poss"}) == "cats'"

    def test_proper_noun_possessive(self):
        assert surface_form("Anna Karenina", {"case": "poss"}) == "Anna Karenina's"

    def test_irregular_plural_possessive(self):
        result = surface_form("child", {"number": "pl", "case": "poss"})
        assert result == "children's"

    def test_possessive_with_article_the(self):
        result = surface_form("cat", {"case": "poss", "article": "the"})
        assert result == "the cat's"

    def test_plural_possessive_with_article(self):
        result = surface_form("algorithm", {"number": "pl", "case": "poss", "article": "the"})
        assert result == "the algorithms'"


# ── Articles ─────────────────────────────────────────────────────────────────


class TestArticles:
    def test_a_consonant(self):
        assert surface_form("cat", {"article": "a"}) == "a cat"

    def test_an_vowel(self):
        assert surface_form("elephant", {"article": "a"}) == "an elephant"

    def test_an_algorithm(self):
        assert surface_form("algorithm", {"article": "a"}) == "an algorithm"

    def test_an_umbrella(self):
        assert surface_form("umbrella", {"article": "a"}) == "an umbrella"

    def test_a_university(self):
        # "university" starts with a consonant sound "yoo"
        result = surface_form("university", {"article": "a"})
        assert result == "a university"

    def test_an_hour(self):
        # "hour" has silent h
        result = surface_form("hour", {"article": "a"})
        assert result == "an hour"

    def test_the(self):
        assert surface_form("cat", {"article": "the"}) == "the cat"

    def test_the_plural(self):
        assert surface_form("cat", {"number": "pl", "article": "the"}) == "the cats"


# ── Uncountable nouns ────────────────────────────────────────────────────────


class TestUncountableNouns:
    def test_uncountable_not_pluralized(self):
        props = {"countable": "no"}
        assert surface_form("water", {"number": "pl"}, props) == "water"

    def test_uncountable_information(self):
        props = {"countable": "no"}
        assert surface_form("information", {"number": "pl"}, props) == "information"

    def test_uncountable_with_article(self):
        props = {"countable": "no"}
        assert surface_form("water", {"number": "pl", "article": "the"}, props) == "the water"

    def test_uncountable_singular_unchanged(self):
        props = {"countable": "no"}
        assert surface_form("water", {"number": "sg"}, props) == "water"

    def test_countable_default(self):
        # Without countable property, pluralization works normally
        assert surface_form("water", {"number": "pl"}) == "waters"


# ── Proper nouns ─────────────────────────────────────────────────────────────


class TestProperNouns:
    def test_proper_noun_not_pluralized(self):
        assert surface_form("Anna Karenina", {"number": "pl"}) == "Anna Karenina"

    def test_proper_noun_possessive(self):
        assert surface_form("Anna Karenina", {"case": "poss"}) == "Anna Karenina's"

    def test_proper_noun_plural_possessive(self):
        # Proper noun skips pluralization, but still gets possessive
        result = surface_form("Anna Karenina", {"number": "pl", "case": "poss"})
        assert result == "Anna Karenina's"

    def test_single_word_not_proper(self):
        # Single capitalized word is NOT detected as proper noun
        assert surface_form("London", {"number": "pl"}) == "Londons"


# ── No features / base form passthrough ──────────────────────────────────────


class TestBaseForm:
    def test_none_features(self):
        assert surface_form("algorithm", None) == "algorithm"

    def test_empty_features(self):
        assert surface_form("algorithm", {}) == "algorithm"

    def test_none_features_none_props(self):
        assert surface_form("algorithm", None, None) == "algorithm"


# ── Verb conjugation ─────────────────────────────────────────────────────────


class TestVerbConjugation:
    """Test verb inflection via pos='verb' feature."""

    # Irregular verbs: past tense
    def test_irregular_past_run(self):
        assert surface_form("run", {"pos": "verb", "tense": "past"}) == "ran"

    def test_irregular_past_go(self):
        assert surface_form("go", {"pos": "verb", "tense": "past"}) == "went"

    def test_irregular_past_write(self):
        assert surface_form("write", {"pos": "verb", "tense": "past"}) == "wrote"

    def test_irregular_past_be(self):
        assert surface_form("be", {"pos": "verb", "tense": "past"}) == "was"

    def test_irregular_past_have(self):
        assert surface_form("have", {"pos": "verb", "tense": "past"}) == "had"

    def test_irregular_past_think(self):
        assert surface_form("think", {"pos": "verb", "tense": "past"}) == "thought"

    def test_irregular_past_buy(self):
        assert surface_form("buy", {"pos": "verb", "tense": "past"}) == "bought"

    # Irregular verbs: past participle
    def test_irregular_past_participle_write(self):
        assert surface_form("write", {"pos": "verb", "tense": "past_participle"}) == "written"

    def test_irregular_past_participle_go(self):
        assert surface_form("go", {"pos": "verb", "tense": "past_participle"}) == "gone"

    def test_irregular_past_participle_see(self):
        assert surface_form("see", {"pos": "verb", "tense": "past_participle"}) == "seen"

    def test_irregular_past_participle_run(self):
        assert surface_form("run", {"pos": "verb", "tense": "past_participle"}) == "run"

    def test_irregular_past_participle_do(self):
        assert surface_form("do", {"pos": "verb", "tense": "past_participle"}) == "done"

    # Irregular verbs: present participle
    def test_irregular_present_participle_run(self):
        assert surface_form("run", {"pos": "verb", "tense": "present_participle"}) == "running"

    def test_irregular_present_participle_be(self):
        assert surface_form("be", {"pos": "verb", "tense": "present_participle"}) == "being"

    def test_irregular_present_participle_write(self):
        assert surface_form("write", {"pos": "verb", "tense": "present_participle"}) == "writing"

    # Irregular verbs: 3rd person singular present
    def test_irregular_3sg_be(self):
        assert surface_form("be", {"pos": "verb", "tense": "present", "person": "3sg"}) == "is"

    def test_irregular_3sg_have(self):
        assert surface_form("have", {"pos": "verb", "tense": "present", "person": "3sg"}) == "has"

    def test_irregular_3sg_do(self):
        assert surface_form("do", {"pos": "verb", "tense": "present", "person": "3sg"}) == "does"

    def test_irregular_3sg_go(self):
        assert surface_form("go", {"pos": "verb", "tense": "present", "person": "3sg"}) == "goes"

    def test_irregular_3sg_say(self):
        assert surface_form("say", {"pos": "verb", "tense": "present", "person": "3sg"}) == "says"

    # Regular verbs: past tense
    def test_regular_past_walk(self):
        assert surface_form("walk", {"pos": "verb", "tense": "past"}) == "walked"

    def test_regular_past_love(self):
        assert surface_form("love", {"pos": "verb", "tense": "past"}) == "loved"

    def test_regular_past_try(self):
        assert surface_form("try", {"pos": "verb", "tense": "past"}) == "tried"

    def test_regular_past_play(self):
        assert surface_form("play", {"pos": "verb", "tense": "past"}) == "played"

    def test_regular_past_stop(self):
        assert surface_form("stop", {"pos": "verb", "tense": "past"}) == "stopped"

    # Regular verbs: 3sg present
    def test_regular_3sg_walk(self):
        assert surface_form("walk", {"pos": "verb", "tense": "present", "person": "3sg"}) == "walks"

    def test_regular_3sg_watch(self):
        assert surface_form("watch", {"pos": "verb", "tense": "present", "person": "3sg"}) == "watches"

    def test_regular_3sg_fix(self):
        assert surface_form("fix", {"pos": "verb", "tense": "present", "person": "3sg"}) == "fixes"

    def test_regular_3sg_buzz(self):
        assert surface_form("buzz", {"pos": "verb", "tense": "present", "person": "3sg"}) == "buzzes"

    def test_regular_3sg_try(self):
        assert surface_form("try", {"pos": "verb", "tense": "present", "person": "3sg"}) == "tries"

    def test_regular_3sg_play(self):
        assert surface_form("play", {"pos": "verb", "tense": "present", "person": "3sg"}) == "plays"

    # Regular verbs: present participle
    def test_regular_present_participle_walk(self):
        assert surface_form("walk", {"pos": "verb", "tense": "present_participle"}) == "walking"

    def test_regular_present_participle_love(self):
        assert surface_form("love", {"pos": "verb", "tense": "present_participle"}) == "loving"

    def test_regular_present_participle_stop(self):
        assert surface_form("stop", {"pos": "verb", "tense": "present_participle"}) == "stopping"

    # Non-3sg present uses base form
    def test_1sg_present_base_form(self):
        assert surface_form("run", {"pos": "verb", "tense": "present", "person": "1sg"}) == "run"

    def test_2sg_present_base_form(self):
        assert surface_form("run", {"pos": "verb", "tense": "present", "person": "2sg"}) == "run"

    def test_1pl_present_base_form(self):
        assert surface_form("run", {"pos": "verb", "tense": "present", "person": "1pl"}) == "run"

    def test_3pl_present_base_form(self):
        assert surface_form("run", {"pos": "verb", "tense": "present", "person": "3pl"}) == "run"

    # Default person is 3sg
    def test_default_person_is_3sg(self):
        assert surface_form("run", {"pos": "verb", "tense": "present"}) == "runs"

    # Default tense is present
    def test_default_tense_is_present(self):
        assert surface_form("run", {"pos": "verb"}) == "runs"


# ── Adjective/adverb comparison ──────────────────────────────────────────────


class TestAdjectiveComparison:
    """Test adjective inflection via pos='adj' feature."""

    # Irregular comparatives
    def test_irregular_comp_good(self):
        assert surface_form("good", {"pos": "adj", "degree": "comparative"}) == "better"

    def test_irregular_super_good(self):
        assert surface_form("good", {"pos": "adj", "degree": "superlative"}) == "best"

    def test_irregular_comp_bad(self):
        assert surface_form("bad", {"pos": "adj", "degree": "comparative"}) == "worse"

    def test_irregular_super_bad(self):
        assert surface_form("bad", {"pos": "adj", "degree": "superlative"}) == "worst"

    def test_irregular_comp_much(self):
        assert surface_form("much", {"pos": "adj", "degree": "comparative"}) == "more"

    def test_irregular_super_much(self):
        assert surface_form("much", {"pos": "adj", "degree": "superlative"}) == "most"

    def test_irregular_comp_far(self):
        assert surface_form("far", {"pos": "adj", "degree": "comparative"}) == "farther"

    def test_irregular_super_far(self):
        assert surface_form("far", {"pos": "adj", "degree": "superlative"}) == "farthest"

    # Regular short adjectives: -er/-est
    def test_regular_comp_tall(self):
        assert surface_form("tall", {"pos": "adj", "degree": "comparative"}) == "taller"

    def test_regular_super_tall(self):
        assert surface_form("tall", {"pos": "adj", "degree": "superlative"}) == "tallest"

    def test_regular_comp_big(self):
        assert surface_form("big", {"pos": "adj", "degree": "comparative"}) == "bigger"

    def test_regular_super_big(self):
        assert surface_form("big", {"pos": "adj", "degree": "superlative"}) == "biggest"

    def test_regular_comp_nice(self):
        assert surface_form("nice", {"pos": "adj", "degree": "comparative"}) == "nicer"

    def test_regular_super_nice(self):
        assert surface_form("nice", {"pos": "adj", "degree": "superlative"}) == "nicest"

    def test_regular_comp_happy(self):
        assert surface_form("happy", {"pos": "adj", "degree": "comparative"}) == "happier"

    def test_regular_super_happy(self):
        assert surface_form("happy", {"pos": "adj", "degree": "superlative"}) == "happiest"

    # Long adjectives: more/most
    def test_long_comp_beautiful(self):
        assert surface_form("beautiful", {"pos": "adj", "degree": "comparative"}) == "more beautiful"

    def test_long_super_beautiful(self):
        assert surface_form("beautiful", {"pos": "adj", "degree": "superlative"}) == "most beautiful"

    def test_long_comp_important(self):
        assert surface_form("important", {"pos": "adj", "degree": "comparative"}) == "more important"

    def test_long_super_important(self):
        assert surface_form("important", {"pos": "adj", "degree": "superlative"}) == "most important"

    # No degree returns base form
    def test_no_degree_returns_base(self):
        assert surface_form("good", {"pos": "adj"}) == "good"


# ── Declension override ─────────────────────────────────────────────────────


class TestDeclensionOverride:
    """Test declension_override property (matching pl.py pattern)."""

    def test_noun_plural_override(self):
        props = {"declension_override": json.dumps({"pl": "indices"})}
        assert surface_form("index", {"number": "pl"}, props) == "indices"

    def test_noun_plural_override_as_dict(self):
        props = {"declension_override": {"pl": "indices"}}
        assert surface_form("index", {"number": "pl"}, props) == "indices"

    def test_noun_override_singular_unchanged(self):
        props = {"declension_override": {"pl": "indices"}}
        assert surface_form("index", {"number": "sg"}, props) == "index"

    def test_noun_possessive_override(self):
        props = {"declension_override": {"sg:poss": "Jesus'"}}
        assert surface_form("Jesus", {"case": "poss"}, props) == "Jesus'"

    def test_noun_plural_possessive_compound_override(self):
        props = {"declension_override": json.dumps({"pl:poss": "children's"})}
        assert surface_form("child", {"number": "pl", "case": "poss"}, props) == "children's"

    def test_noun_plural_override_with_natural_possessive(self):
        """Override provides plural, possessive is applied naturally."""
        props = {"declension_override": {"pl": "kine"}}
        assert surface_form("cow", {"number": "pl", "case": "poss"}, props) == "kine's"

    def test_verb_override(self):
        props = {"declension_override": {"past": "yeeted"}}
        assert surface_form("yeet", {"pos": "verb", "tense": "past"}, props) == "yeeted"

    def test_verb_3sg_override(self):
        props = {"declension_override": {"3sg": "hath"}}
        assert surface_form("have", {"pos": "verb", "tense": "present", "person": "3sg"}, props) == "hath"

    def test_adjective_override(self):
        props = {"declension_override": {"comparative": "more fun"}}
        assert surface_form("fun", {"pos": "adj", "degree": "comparative"}, props) == "more fun"

    def test_adjective_superlative_override(self):
        props = {"declension_override": {"superlative": "most fun"}}
        assert surface_form("fun", {"pos": "adj", "degree": "superlative"}, props) == "most fun"

    def test_override_not_present_falls_through(self):
        """Override dict exists but doesn't have the needed key -> normal inflection."""
        props = {"declension_override": {"pl": "indices"}}
        assert surface_form("index", {"case": "poss"}, props) == "index's"

    def test_no_override_property(self):
        """No declension_override at all -> normal inflection."""
        assert surface_form("cat", {"number": "pl"}, {}) == "cats"


# ── Dispatch integration ─────────────────────────────────────────────────────


class TestDispatchEnglish:
    """Test that dispatch.surface_form routes to English correctly."""

    def test_dispatch_plural(self):
        assert dispatch_surface_form("en", "cat", {"number": "pl"}) == "cats"

    def test_dispatch_possessive(self):
        assert dispatch_surface_form("en", "cat", {"case": "poss"}) == "cat's"

    def test_dispatch_article(self):
        assert dispatch_surface_form("en", "elephant", {"article": "a"}) == "an elephant"

    def test_dispatch_verb(self):
        assert dispatch_surface_form("en", "run", {"pos": "verb", "tense": "past"}) == "ran"

    def test_dispatch_adjective(self):
        assert dispatch_surface_form("en", "good", {"pos": "adj", "degree": "comparative"}) == "better"

    def test_dispatch_with_properties(self):
        props = {"declension_override": {"pl": "indices"}}
        assert dispatch_surface_form("en", "index", {"number": "pl"}, props) == "indices"

    def test_dispatch_unknown_language_returns_base(self):
        assert dispatch_surface_form("xx", "cat", {"number": "pl"}) == "cat"

    def test_dispatch_no_features(self):
        assert dispatch_surface_form("en", "cat") == "cat"


# ── Combined features ────────────────────────────────────────────────────────


class TestCombinedFeatures:
    """Test combinations of features working together."""

    def test_plural_possessive_article(self):
        result = surface_form("algorithm", {"number": "pl", "case": "poss", "article": "the"})
        assert result == "the algorithms'"

    def test_plural_article_a(self):
        # "a cats" doesn't make grammatical sense, but the engine should handle it
        result = surface_form("cat", {"number": "pl", "article": "a"})
        # inflect.a() will figure out the article for "cats"
        assert "cats" in result

    def test_singular_article_the_possessive(self):
        result = surface_form("cat", {"article": "the", "case": "poss"})
        assert result == "the cat's"

    def test_uncountable_plural_possessive(self):
        props = {"countable": "no"}
        result = surface_form("water", {"number": "pl", "case": "poss"}, props)
        assert result == "water's"

    def test_proper_noun_all_features(self):
        result = surface_form("Anna Karenina", {"number": "pl", "case": "poss", "article": "the"})
        assert result == "the Anna Karenina's"
