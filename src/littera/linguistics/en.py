"""English surface form generation.

Given a base_form and a features dict, produce the correct English text:
plurals, possessives, articles.

Pipeline: base_form → [pluralize?] → [possessive?] → [prepend article?] → surface_form
"""

from __future__ import annotations

import inflect

_engine = inflect.engine()


def _is_proper_noun(text: str) -> bool:
    """Heuristic: multi-word names where every word is capitalized are proper nouns."""
    words = text.split()
    return len(words) >= 2 and all(w[0].isupper() for w in words)


def surface_form(base_form: str, features: dict | None = None) -> str:
    """Generate English surface form from base_form + features.

    features keys:
        number:  "sg" (default) | "pl"
        case:    "plain" (default) | "poss"
        article: None (default) | "a" | "the"
    """
    if not features:
        return base_form

    text = base_form

    # Step 1: Pluralize (skip proper nouns — they don't inflect)
    if features.get("number") == "pl" and not _is_proper_noun(text):
        result = _engine.plural_noun(text)
        if result:
            text = result

    # Step 2: Possessive suffix
    if features.get("case") == "poss":
        if text.endswith("s"):
            text = text + "'"
        else:
            text = text + "'s"

    # Step 3: Article
    article = features.get("article")
    if article == "a":
        # inflect.a() returns "a word" or "an word" — the full phrase
        text = _engine.a(text)
    elif article == "the":
        text = "the " + text

    return text
