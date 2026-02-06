"""Entity label commands.

Labels provide multilingual names for entities.
Each entity can have one base form per language plus optional aliases.

Commands:
  littera entity label-add <entity> <language> <base_form>
  littera entity label-list <entity>
  littera entity label-delete <entity> <language>
"""

from __future__ import annotations

import sys
import uuid

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
    """Register entity label commands to an entity subgroup."""

    @app.command("label-add")
    def label_add(entity: str, language: str, base_form: str) -> None:
        """Add a multilingual label to an entity."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                label_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO entity_labels (id, entity_id, language, base_form)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (entity_id, language)
                    DO UPDATE SET base_form = EXCLUDED.base_form
                    """,
                    (label_id, eid, language, base_form),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Label set: {name} ({language}) = {base_form}")

    @app.command("label-list")
    def label_list(entity: str) -> None:
        """List labels for an entity."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                cur.execute(
                    "SELECT language, base_form, aliases FROM entity_labels "
                    "WHERE entity_id = %s ORDER BY language",
                    (eid,),
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print(f"No labels for {etype} '{name}' yet.")
            return

        print(f"Labels for {etype} '{name}':")
        for lang, base_form, aliases in rows:
            line = f"  {lang}: {base_form}"
            if aliases:
                line += f"  (aliases: {aliases})"
            print(line)

    @app.command("label-delete")
    def label_delete(entity: str, language: str) -> None:
        """Delete a label by entity and language."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                cur.execute(
                    "DELETE FROM entity_labels WHERE entity_id = %s AND language = %s",
                    (eid, language),
                )
                if cur.rowcount == 0:
                    print(f"No {language} label found for {etype} '{name}'")
                    sys.exit(1)

                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Label deleted: {name} ({language})")
