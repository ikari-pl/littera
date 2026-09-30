"""Entity label commands.

Labels provide multilingual names for entities.
Each entity can have one base form per language plus optional aliases.

Commands:
  littera entity label-add <entity> <language> <base_form> [--alias A]...
  littera entity label-alias-remove <entity> <language> <alias>
  littera entity label-list <entity>
  littera entity label-delete <entity> <language>

Aliases are only ever added by label-add and removed one at a time by
label-alias-remove, so no command silently drops the ones already there.
"""

from __future__ import annotations

import json
import sys
import uuid
from typing import Annotated

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
    def label_add(
        entity: str,
        language: str,
        base_form: str,
        alias: Annotated[
            list[str] | None,
            typer.Option(
                "--alias",
                help="Another name for this label (repeatable). Added to existing aliases.",
            ),
        ] = None,
    ) -> None:
        """Add a multilingual label to an entity, or change its base form."""
        new_aliases = [a.strip() for a in alias or []]
        if any(not a for a in new_aliases):
            print("An alias cannot be empty.")
            sys.exit(1)
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, _etype, name = _resolve_entity(cur, entity)

                cur.execute(
                    "SELECT aliases FROM entity_labels WHERE entity_id = %s AND language = %s",
                    (eid, language),
                )
                row = cur.fetchone()
                aliases = list(row[0] or []) if row else []
                aliases += [a for a in dict.fromkeys(new_aliases) if a not in aliases]

                label_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO entity_labels (id, entity_id, language, base_form, aliases)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (entity_id, language)
                    DO UPDATE SET base_form = EXCLUDED.base_form,
                                  aliases = EXCLUDED.aliases
                    """,
                    (label_id, eid, language, base_form, json.dumps(aliases) if aliases else None),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Label set: {name} ({language}) = {base_form}")
        if aliases:
            print(f"  aliases: {', '.join(aliases)}")

    @app.command("label-alias-remove")
    def label_alias_remove(entity: str, language: str, alias: str) -> None:
        """Remove one alias from an entity's label."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                cur.execute(
                    "SELECT aliases FROM entity_labels WHERE entity_id = %s AND language = %s",
                    (eid, language),
                )
                row = cur.fetchone()
                if row is None:
                    print(f"No {language} label found for {etype} '{name}'")
                    sys.exit(1)
                aliases = list(row[0] or [])
                if alias not in aliases:
                    print(f"'{alias}' is not an alias of {name} ({language})")
                    sys.exit(1)
                aliases.remove(alias)

                cur.execute(
                    "UPDATE entity_labels SET aliases = %s WHERE entity_id = %s AND language = %s",
                    (json.dumps(aliases) if aliases else None, eid, language),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Alias removed: {name} ({language}) {alias}")

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
