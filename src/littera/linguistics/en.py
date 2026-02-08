"""English surface form generation.

Given a base_form and a features dict, produce the correct English text:
nouns (plurals, possessives, articles), verb conjugation, adjective comparison.

Noun pipeline:  base_form -> [override?] -> [pluralize?] -> [possessive?] -> [article?]
Verb pipeline:  base_form -> [override?] -> [conjugate]
Adj pipeline:   base_form -> [override?] -> [compare]
"""

from __future__ import annotations

import json
import re

import inflect

_engine = inflect.engine()

# ── Irregular forms tables ────────────────────────────────────────────────────
#
# These cover common irregular forms that either inflect handles poorly
# or that inflect doesn't support at all (verbs, adjectives).

# Irregular verbs: base -> (past, past_participle, present_participle, 3sg_present)
# Only forms that can't be derived by regular rules need entries here.
IRREGULAR_VERBS: dict[str, tuple[str, str, str, str]] = {
    "be":       ("was",     "been",     "being",      "is"),
    "have":     ("had",     "had",      "having",     "has"),
    "do":       ("did",     "done",     "doing",      "does"),
    "go":       ("went",    "gone",     "going",      "goes"),
    "say":      ("said",    "said",     "saying",     "says"),
    "get":      ("got",     "gotten",   "getting",    "gets"),
    "make":     ("made",    "made",     "making",     "makes"),
    "know":     ("knew",    "known",    "knowing",    "knows"),
    "think":    ("thought", "thought",  "thinking",   "thinks"),
    "take":     ("took",    "taken",    "taking",     "takes"),
    "see":      ("saw",     "seen",     "seeing",     "sees"),
    "come":     ("came",    "come",     "coming",     "comes"),
    "give":     ("gave",    "given",    "giving",     "gives"),
    "find":     ("found",   "found",    "finding",    "finds"),
    "tell":     ("told",    "told",     "telling",    "tells"),
    "write":    ("wrote",   "written",  "writing",    "writes"),
    "run":      ("ran",     "run",      "running",    "runs"),
    "begin":    ("began",   "begun",    "beginning",  "begins"),
    "break":    ("broke",   "broken",   "breaking",   "breaks"),
    "bring":    ("brought", "brought",  "bringing",   "brings"),
    "buy":      ("bought",  "bought",   "buying",     "buys"),
    "build":    ("built",   "built",    "building",   "builds"),
    "choose":   ("chose",   "chosen",   "choosing",   "chooses"),
    "cut":      ("cut",     "cut",      "cutting",    "cuts"),
    "draw":     ("drew",    "drawn",    "drawing",    "draws"),
    "drink":    ("drank",   "drunk",    "drinking",   "drinks"),
    "drive":    ("drove",   "driven",   "driving",    "drives"),
    "eat":      ("ate",     "eaten",    "eating",     "eats"),
    "fall":     ("fell",    "fallen",   "falling",    "falls"),
    "feel":     ("felt",    "felt",     "feeling",    "feels"),
    "fly":      ("flew",    "flown",    "flying",     "flies"),
    "forget":   ("forgot",  "forgotten","forgetting", "forgets"),
    "grow":     ("grew",    "grown",    "growing",    "grows"),
    "hear":     ("heard",   "heard",    "hearing",    "hears"),
    "hide":     ("hid",     "hidden",   "hiding",     "hides"),
    "hold":     ("held",    "held",     "holding",    "holds"),
    "keep":     ("kept",    "kept",     "keeping",    "keeps"),
    "lead":     ("led",     "led",      "leading",    "leads"),
    "leave":    ("left",    "left",     "leaving",    "leaves"),
    "let":      ("let",     "let",      "letting",    "lets"),
    "lie":      ("lay",     "lain",     "lying",      "lies"),
    "lose":     ("lost",    "lost",     "losing",     "loses"),
    "mean":     ("meant",   "meant",    "meaning",    "means"),
    "meet":     ("met",     "met",      "meeting",    "meets"),
    "pay":      ("paid",    "paid",     "paying",     "pays"),
    "put":      ("put",     "put",      "putting",    "puts"),
    "read":     ("read",    "read",     "reading",    "reads"),
    "ride":     ("rode",    "ridden",   "riding",     "rides"),
    "ring":     ("rang",    "rung",     "ringing",    "rings"),
    "rise":     ("rose",    "risen",    "rising",     "rises"),
    "sell":     ("sold",    "sold",     "selling",    "sells"),
    "send":     ("sent",    "sent",     "sending",    "sends"),
    "set":      ("set",     "set",      "setting",    "sets"),
    "show":     ("showed",  "shown",    "showing",    "shows"),
    "shut":     ("shut",    "shut",     "shutting",   "shuts"),
    "sing":     ("sang",    "sung",     "singing",    "sings"),
    "sit":      ("sat",     "sat",      "sitting",    "sits"),
    "sleep":    ("slept",   "slept",    "sleeping",   "sleeps"),
    "speak":    ("spoke",   "spoken",   "speaking",   "speaks"),
    "spend":    ("spent",   "spent",    "spending",   "spends"),
    "stand":    ("stood",   "stood",    "standing",   "stands"),
    "swim":     ("swam",    "swum",     "swimming",   "swims"),
    "teach":    ("taught",  "taught",   "teaching",   "teaches"),
    "throw":    ("threw",   "thrown",   "throwing",   "throws"),
    "understand": ("understood", "understood", "understanding", "understands"),
    "wake":     ("woke",    "woken",    "waking",     "wakes"),
    "wear":     ("wore",    "worn",     "wearing",    "wears"),
    "win":      ("won",     "won",      "winning",    "wins"),
}

# Irregular adjective/adverb comparison: base -> (comparative, superlative)
IRREGULAR_COMPARISONS: dict[str, tuple[str, str]] = {
    "good":     ("better",  "best"),
    "bad":      ("worse",   "worst"),
    "far":      ("farther", "farthest"),
    "little":   ("less",    "least"),
    "much":     ("more",    "most"),
    "many":     ("more",    "most"),
    "well":     ("better",  "best"),
    "badly":    ("worse",   "worst"),
    "old":      ("older",   "oldest"),
    "late":     ("later",   "latest"),
}


# ── Regular inflection helpers ────────────────────────────────────────────────

def _regular_past(verb: str) -> str:
    """Apply regular English past tense rules: verb -> verb+ed."""
    if verb.endswith("e"):
        return verb + "d"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        return verb[:-1] + "ied"
    if (
        len(verb) >= 2
        and verb[-1] in "bdgklmnprt"
        and verb[-2] in "aeiou"
        and (len(verb) < 3 or verb[-3] not in "aeiou")
        and not verb.endswith("w") and not verb.endswith("x") and not verb.endswith("y")
    ):
        # Double final consonant for CVC pattern (one-syllable heuristic)
        return verb + verb[-1] + "ed"
    return verb + "ed"


def _regular_3sg(verb: str) -> str:
    """Apply regular English 3rd-person singular present rules: verb -> verb+s/es."""
    if verb.endswith(("s", "sh", "ch", "x", "z")):
        return verb + "es"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        return verb[:-1] + "ies"
    if verb.endswith("o"):
        return verb + "es"
    return verb + "s"


def _regular_present_participle(verb: str) -> str:
    """Apply regular present participle rules: verb -> verb+ing."""
    if verb.endswith("ie"):
        return verb[:-2] + "ying"
    if verb.endswith("e") and not verb.endswith("ee"):
        return verb[:-1] + "ing"
    if (
        len(verb) >= 2
        and verb[-1] in "bdgklmnprt"
        and verb[-2] in "aeiou"
        and (len(verb) < 3 or verb[-3] not in "aeiou")
    ):
        return verb + verb[-1] + "ing"
    return verb + "ing"


def _regular_comparative(adj: str) -> str:
    """Apply regular comparative rules: adj -> adj+er or more+adj."""
    # Short adjectives (one syllable, or two ending in -y) take -er
    syllable_count = _count_syllables(adj)
    if syllable_count <= 1 or (syllable_count == 2 and adj.endswith("y")):
        if adj.endswith("e"):
            return adj + "r"
        if adj.endswith("y") and len(adj) > 1 and adj[-2] not in "aeiou":
            return adj[:-1] + "ier"
        if (
            len(adj) >= 2
            and adj[-1] in "bdgkmnprt"
            and adj[-2] in "aeiou"
            and (len(adj) < 3 or adj[-3] not in "aeiou")
        ):
            return adj + adj[-1] + "er"
        return adj + "er"
    return "more " + adj


def _regular_superlative(adj: str) -> str:
    """Apply regular superlative rules: adj -> adj+est or most+adj."""
    syllable_count = _count_syllables(adj)
    if syllable_count <= 1 or (syllable_count == 2 and adj.endswith("y")):
        if adj.endswith("e"):
            return adj + "st"
        if adj.endswith("y") and len(adj) > 1 and adj[-2] not in "aeiou":
            return adj[:-1] + "iest"
        if (
            len(adj) >= 2
            and adj[-1] in "bdgkmnprt"
            and adj[-2] in "aeiou"
            and (len(adj) < 3 or adj[-3] not in "aeiou")
        ):
            return adj + adj[-1] + "est"
        return adj + "est"
    return "most " + adj


def _count_syllables(word: str) -> int:
    """Rough syllable count heuristic based on vowel groups."""
    word = word.lower()
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    # Trailing silent e
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


# ── Public API ────────────────────────────────────────────────────────────────

def _is_proper_noun(text: str) -> bool:
    """Heuristic: multi-word names where every word is capitalized are proper nouns."""
    words = text.split()
    return len(words) >= 2 and all(w[0].isupper() for w in words)


def _check_override(props: dict, key: str) -> str | None:
    """Check declension_override for a matching key.

    Override is stored as either a JSON string or a dict in entity properties.
    Keys can be any feature combination, e.g. "pl", "poss", "pl:poss",
    "past", "comparative", etc.
    """
    override = props.get("declension_override")
    if not override:
        return None
    if isinstance(override, str):
        override = json.loads(override)
    return override.get(key)


def _conjugate_verb(base_form: str, features: dict, props: dict) -> str:
    """Conjugate an English verb based on features.

    features keys:
        tense:  "present" (default) | "past" | "past_participle" | "present_participle"
        person: "1sg"/"2sg"/"3sg"/"1pl"/"2pl"/"3pl" (only matters for present tense)
    """
    tense = features.get("tense", "present")
    person = features.get("person", "3sg")

    # Build override key
    if tense == "present" and person == "3sg":
        override_key = "3sg"
    elif tense == "present":
        override_key = "present"
    else:
        override_key = tense

    # Check override first
    result = _check_override(props, override_key)
    if result:
        return result

    lower = base_form.lower()
    irregular = IRREGULAR_VERBS.get(lower)

    if tense == "past":
        if irregular:
            return irregular[0]
        return _regular_past(lower)

    if tense == "past_participle":
        if irregular:
            return irregular[1]
        return _regular_past(lower)  # Regular: past == past_participle

    if tense == "present_participle":
        if irregular:
            return irregular[2]
        return _regular_present_participle(lower)

    # Present tense
    if person == "3sg":
        if irregular:
            return irregular[3]
        return _regular_3sg(lower)

    # All other persons in present tense use base form
    return base_form


def _compare_adjective(base_form: str, features: dict, props: dict) -> str:
    """Generate comparative or superlative form of an adjective/adverb.

    features keys:
        degree: "comparative" | "superlative"
    """
    degree = features.get("degree")
    if not degree:
        return base_form

    # Check override
    result = _check_override(props, degree)
    if result:
        return result

    lower = base_form.lower()
    irregular = IRREGULAR_COMPARISONS.get(lower)

    if degree == "comparative":
        if irregular:
            return irregular[0]
        return _regular_comparative(lower)

    if degree == "superlative":
        if irregular:
            return irregular[1]
        return _regular_superlative(lower)

    return base_form


def surface_form(
    base_form: str,
    features: dict | None = None,
    properties: dict | None = None,
) -> str:
    """Generate English surface form from base_form + features.

    features keys (nouns):
        number:  "sg" (default) | "pl"
        case:    "plain" (default) | "poss"
        article: None (default) | "a" | "the"

    features keys (verbs):
        pos:     "verb"
        tense:   "present" (default) | "past" | "past_participle" | "present_participle"
        person:  "1sg"/"2sg"/"3sg" (default)/"1pl"/"2pl"/"3pl"

    features keys (adjectives):
        pos:     "adj"
        degree:  "comparative" | "superlative"

    properties keys (from entity):
        countable:           "yes" (default) | "no" — uncountable nouns skip pluralization
        declension_override: dict of form_key -> surface_form
    """
    if not features:
        return base_form

    props = properties or {}
    pos = features.get("pos")

    # Verb conjugation
    if pos == "verb":
        return _conjugate_verb(base_form, features, props)

    # Adjective/adverb comparison
    if pos == "adj":
        return _compare_adjective(base_form, features, props)

    # ── Noun pipeline (default) ───────────────────────────────────────────

    text = base_form

    # Step 1: Check declension_override for the specific form combination
    number = features.get("number", "sg")
    case = features.get("case", "plain")
    compound_key = f"{number}:{case}" if case != "plain" else number
    override_result = _check_override(props, compound_key)
    if override_result:
        text = override_result
    elif number == "pl" and _check_override(props, "pl"):
        text = _check_override(props, "pl")  # type: ignore[assignment]
    else:
        # Step 2: Pluralize (skip proper nouns and uncountable nouns)
        if features.get("number") == "pl" and not _is_proper_noun(text):
            if props.get("countable") != "no":
                result = _engine.plural_noun(text)
                if result:
                    text = result

    # Step 3: Possessive suffix
    if features.get("case") == "poss":
        # If override already handled possessive via compound key, skip
        if not override_result or ":" not in compound_key:
            if text.endswith("s"):
                text = text + "'"
            else:
                text = text + "'s"

    # Step 4: Article
    article = features.get("article")
    if article == "a":
        # inflect.a() returns "a word" or "an word" — the full phrase
        text = _engine.a(text)
    elif article == "the":
        text = "the " + text

    return text
