"""Entity property commands.

Properties store intrinsic grammatical facts on the entity itself
(e.g. countability for English, gender for Polish).

Storage: entities.properties JSONB — flat key-value, no nesting.

Commands:
  littera entity property-set <entity> <key=value> [<key=value> ...]
  littera entity property-list <entity>
  littera entity property-delete <entity> <key>
"""

from __future__ import annotations

import json
import sys
from typing import List

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
    """Register entity property commands to an entity subgroup."""

    @app.command("property-set")
    def property_set(
        entity: str = typer.Argument(help="Entity index, UUID, or label"),
        pairs: List[str] = typer.Argument(help="key=value pairs"),
    ) -> None:
        """Set properties on an entity (merged into existing)."""
        # Parse key=value pairs
        updates: dict[str, str] = {}
        for pair in pairs:
            if "=" not in pair:
                print(f"Invalid property format: {pair} (expected key=value)")
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            updates[key] = value

        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                # Read current properties
                cur.execute(
                    "SELECT properties FROM entities WHERE id = %s", (eid,)
                )
                row = cur.fetchone()
                current = row[0] if row and row[0] else {}

                # Merge updates
                current.update(updates)

                cur.execute(
                    "UPDATE entities SET properties = %s WHERE id = %s",
                    (json.dumps(current), eid),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        formatted = ", ".join(f"{k}={v}" for k, v in updates.items())
        print(f"✓ Properties set on {etype} '{name}': {formatted}")

    @app.command("property-list")
    def property_list(
        entity: str = typer.Argument(help="Entity index, UUID, or label"),
    ) -> None:
        """List all properties for an entity."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                cur.execute(
                    "SELECT properties FROM entities WHERE id = %s", (eid,)
                )
                row = cur.fetchone()
                props = row[0] if row and row[0] else {}
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not props:
            print(f"No properties for {etype} '{name}'.")
            return

        print(f"Properties for {etype} '{name}':")
        for key, value in props.items():
            print(f"  {key}: {value}")

    @app.command("property-delete")
    def property_delete(
        entity: str = typer.Argument(help="Entity index, UUID, or label"),
        key: str = typer.Argument(help="Property key to remove"),
    ) -> None:
        """Remove a single property from an entity."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, name = _resolve_entity(cur, entity)

                cur.execute(
                    "SELECT properties FROM entities WHERE id = %s", (eid,)
                )
                row = cur.fetchone()
                props = row[0] if row and row[0] else {}

                if key not in props:
                    print(f"Property '{key}' not found on {etype} '{name}'")
                    raise typer.Exit(1)

                del props[key]

                cur.execute(
                    "UPDATE entities SET properties = %s WHERE id = %s",
                    (json.dumps(props) if props else None, eid),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Property deleted: {key} from {etype} '{name}'")
