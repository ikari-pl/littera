"""Entity note commands.

Notes are work-scoped overlays on global entities.

Storage: entity_work_metadata.metadata -> {"note": <text>}
"""

from __future__ import annotations

import json
import sys

import typer

from littera.db.workdb import open_work_db


def register(app: typer.Typer) -> None:
    app.command("entity-note-set")(entity_note_set)
    app.command("entity-note-show")(entity_note_show)


def _resolve_entity(cur, entity_type: str, name: str) -> str:
    cur.execute(
        "SELECT id FROM entities WHERE entity_type = %s AND canonical_label = %s",
        (entity_type, name),
    )
    row = cur.fetchone()
    if row is None:
        print("Entity not found")
        sys.exit(1)
    return str(row[0])


def entity_note_set(entity_type: str, name: str, note: str) -> None:
    """Set a work-scoped note for an entity."""

    try:
        with open_work_db() as db:
            cur = db.conn.cursor()

            work_id = db.cfg["work"]["id"]
            entity_id = _resolve_entity(cur, entity_type, name)

            cur.execute(
                """
                INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (entity_id, work_id)
                DO UPDATE SET metadata = EXCLUDED.metadata
                """,
                (entity_id, work_id, json.dumps({"note": note})),
            )

            db.conn.commit()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    print(f"✓ Note set: {entity_type} {name}")


def entity_note_show(entity_type: str, name: str) -> None:
    """Show a work-scoped note for an entity."""

    try:
        with open_work_db() as db:
            cur = db.conn.cursor()

            work_id = db.cfg["work"]["id"]
            entity_id = _resolve_entity(cur, entity_type, name)

            cur.execute(
                """
                SELECT metadata->>'note'
                FROM entity_work_metadata
                WHERE entity_id = %s AND work_id = %s
                """,
                (entity_id, work_id),
            )
            row = cur.fetchone()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    if row is None or row[0] is None:
        print("(no note)")
        return

    print(row[0])
