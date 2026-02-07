#!/usr/bin/env python3
"""Build a noun-only SQLite database from a PoliMorf TSV dump.

Usage:
    python scripts/build_polimorf_db.py scripts/polimorf.tab

Input:  PoliMorf TSV (form<TAB>lemma<TAB>tag), e.g. from
        http://zil.ipipan.waw.pl/PoliMorf?action=AttachFile&do=get&target=PoliMorf-0.6.7.tab.gz

Output: src/littera/linguistics/data/polimorf_nouns.db

Storage format:
    Each row is one (lemma, gender) pair with a JSON dict of forms:
        {"sg:gen": "algorytmu", "sg:dat": "algorytmowi", ...}
    This collapses ~13 rows per lemma/gender into 1, reducing DB from ~170MB to ~30MB.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "src" / "littera" / "linguistics" / "data"
OUTPUT_DB = OUTPUT_DIR / "polimorf_nouns.db"


def build(tsv_path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_DB.exists():
        OUTPUT_DB.unlink()

    # Collect: (lemma, gender) → {("sg", "gen"): "algorytmu", ...}
    forms: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)

    with open(tsv_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue

            form, lemma, tag = parts[0], parts[1], parts[2]

            if not tag.startswith("subst:"):
                continue

            tag_parts = tag.split(":")
            if len(tag_parts) != 4:
                continue

            _, number, case_val, gender = tag_parts

            # Skip nominative singular — pl.py returns base_form for that
            if case_val == "nom" and number == "sg":
                continue

            key = f"{number}:{case_val}"
            # First form wins (PoliMorf lists preferred forms first)
            if key not in forms[(lemma, gender)]:
                forms[(lemma, gender)][key] = form

    conn = sqlite3.connect(str(OUTPUT_DB))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE nouns (
            lemma  TEXT NOT NULL,
            gender TEXT NOT NULL,
            forms  TEXT NOT NULL
        )
    """)

    rows = [
        (lemma, gender, json.dumps(form_dict, ensure_ascii=False))
        for (lemma, gender), form_dict in forms.items()
    ]
    cur.executemany("INSERT INTO nouns VALUES (?, ?, ?)", rows)

    cur.execute("CREATE INDEX idx_nouns_lemma ON nouns (lemma)")

    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    print(f"Built {OUTPUT_DB}")
    print(f"  Lemma-gender entries: {len(rows):,}")
    print(f"  Size: {OUTPUT_DB.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <polimorf.tab>")
        sys.exit(1)

    tsv_path = Path(sys.argv[1])
    if not tsv_path.exists():
        print(f"File not found: {tsv_path}")
        sys.exit(1)

    build(tsv_path)
