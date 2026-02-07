"""Polish surface form generation via PoliMorf noun lookup.

Given a base_form (lemma) and features dict, produce the correct Polish
inflected form by looking up the PoliMorf noun database.

Pipeline: base_form → [check declension_override] → [lookup PoliMorf] → [fallback to base_form]

DB schema (JSON-collapsed for size):
    nouns(lemma TEXT, gender TEXT, forms TEXT)
    forms is a JSON dict: {"sg:gen": "algorytmu", "pl:nom": "algorytmy", ...}
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_DB_PATH: Path = Path(__file__).parent / "data" / "polimorf_nouns.db"
_conn: sqlite3.Connection | None = None

VALID_CASES = {"nom", "gen", "dat", "acc", "inst", "loc", "voc"}
VALID_NUMBERS = {"sg", "pl"}
VALID_GENDERS = {"m1", "m2", "m3", "f", "n"}


def _get_conn() -> sqlite3.Connection:
    """Lazy singleton connection to the PoliMorf SQLite database."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_DB_PATH))
    return _conn


def _infer_gender(conn: sqlite3.Connection, lemma: str) -> str | None:
    """Infer gender from dictionary if the lemma has a single unambiguous gender."""
    cur = conn.execute(
        "SELECT DISTINCT gender FROM nouns WHERE lemma = ?",
        (lemma,),
    )
    genders = [row[0] for row in cur.fetchall()]
    if len(genders) == 1:
        return genders[0]
    return None


def _lookup(conn: sqlite3.Connection, lemma: str, gender: str, key: str) -> str | None:
    """Look up a form by lemma, gender, and number:case key."""
    cur = conn.execute(
        "SELECT forms FROM nouns WHERE lemma = ? AND gender = ?",
        (lemma, gender),
    )
    row = cur.fetchone()
    if row:
        forms = json.loads(row[0])
        return forms.get(key)
    return None


def _lookup_any_gender(conn: sqlite3.Connection, lemma: str, key: str) -> str | None:
    """Look up a form across all genders for a lemma."""
    cur = conn.execute(
        "SELECT forms FROM nouns WHERE lemma = ?",
        (lemma,),
    )
    for (forms_json,) in cur.fetchall():
        forms = json.loads(forms_json)
        if key in forms:
            return forms[key]
    return None


def surface_form(
    base_form: str,
    features: dict | None = None,
    properties: dict | None = None,
) -> str:
    """Generate Polish surface form from base_form + features.

    features keys:
        number: "sg" (default) | "pl"
        case:   "nom" (default) | "gen" | "dat" | "acc" | "inst" | "loc" | "voc"

    properties keys (from entity):
        gender:              "m1" | "m2" | "m3" | "f" | "n"
        declension_override: dict of case→form (or "case:number"→form)
    """
    if not features:
        return base_form

    props = properties or {}
    number = features.get("number", "sg")
    case = features.get("case", "nom")

    # Validate inputs — return base_form for invalid values
    if case not in VALID_CASES:
        return base_form
    if number not in VALID_NUMBERS:
        return base_form

    # Nominative singular is just the base form
    if case == "nom" and number == "sg":
        return base_form

    # Step 1: Check declension_override
    override = props.get("declension_override")
    if override:
        if isinstance(override, str):
            override = json.loads(override)
        # Try specific key "number:case" first, then just "case" for sg
        compound_key = f"{number}:{case}"
        if compound_key in override:
            return override[compound_key]
        if number == "sg" and case in override:
            return override[case]

    # Step 2: Look up in PoliMorf
    conn = _get_conn()
    lookup_key = f"{number}:{case}"

    gender = props.get("gender")
    if gender and gender not in VALID_GENDERS:
        gender = None

    if not gender:
        gender = _infer_gender(conn, base_form)

    if gender:
        result = _lookup(conn, base_form, gender, lookup_key)
    else:
        result = _lookup_any_gender(conn, base_form, lookup_key)

    if result:
        return result

    # Step 3: Fallback
    return base_form
