"""Entity suggest-label command: littera entity suggest-label <entity> <language>

Standalone LLM-powered label suggestion for a single entity.
Finds existing labels in other languages to use as source material.
"""

from __future__ import annotations

import os
import sys

import typer

from littera.db.workdb import open_work_db


def _resolve_entity(cur, selector: str) -> tuple[str, str, str]:
    """Resolve entity selector to (id, entity_type, canonical_label)."""
    cur.execute(
        "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid entity index: {selector}")
        sys.exit(1)

    for eid, etype, label in rows:
        if str(eid) == selector:
            return eid, etype, label

    matches = [(eid, et, lab) for eid, et, lab in rows if lab == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous entity label: {selector}")
        sys.exit(1)

    print(f"Entity not found: {selector}")
    sys.exit(1)


def register(app: typer.Typer) -> None:
    """Register suggest-label command to the entity subgroup."""

    @app.command("suggest-label")
    def suggest_label_cmd(entity: str, language: str) -> None:
        """Suggest a translated label for an entity using a local LLM."""
        backend = os.environ.get("LITTERA_LLM_BACKEND")
        if not backend:
            # Resolve entity for the manual fallback message
            try:
                with open_work_db() as db:
                    cur = db.conn.cursor()
                    eid, etype, canonical = _resolve_entity(cur, entity)
            except RuntimeError as e:
                print(str(e))
                sys.exit(1)

            print("No LLM backend configured. Set LITTERA_LLM_BACKEND to enable suggestions.")
            print(f"  Add the label manually:")
            print(f"  littera entity label-add {canonical} {language} <base_form>")
            return

        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, canonical = _resolve_entity(cur, entity)

                # Find an existing label in another language to use as source
                cur.execute(
                    "SELECT language, base_form FROM entity_labels "
                    "WHERE entity_id = %s AND language != %s "
                    "ORDER BY language LIMIT 1",
                    (eid, language),
                )
                row = cur.fetchone()

                if row:
                    source_lang = row[0]
                else:
                    # No labels in other languages — use canonical_label
                    source_lang = "en"

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        from littera.linguistics.suggest import suggest_label

        suggestion = suggest_label(canonical, etype, source_lang, language)

        if suggestion:
            print(f'Suggested label for {etype} "{canonical}" in {language}: {suggestion}')
            print(f"  Apply: littera entity label-add {canonical} {language} {suggestion}")
        else:
            print(f"LLM unavailable or returned no result.")
            print(f"  Add the label manually:")
            print(f"  littera entity label-add {canonical} {language} <base_form>")
