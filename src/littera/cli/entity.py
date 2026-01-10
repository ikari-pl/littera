"""Entity commands: littera entity add|list|delete"""

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

    # Try UUID match
    for eid, etype, label in rows:
        if str(eid) == selector:
            return eid, etype, label

    # Try label match
    matches = [(eid, et, lab) for eid, et, lab in rows if lab == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous entity label: {selector}")
        sys.exit(1)

    print(f"Entity not found: {selector}")
    sys.exit(1)


def register(app: typer.Typer):
    @app.command()
    def add(entity_type: str, name: str):
        """Add a new entity."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                entity_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO entities (id, entity_type, canonical_label) VALUES (%s, %s, %s)",
                    (entity_id, entity_type, name),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Entity added: {entity_type} {name}")

    @app.command("list")
    def list_entities():
        """List all entities."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute(
                    "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No entities yet.")
            return

        print("Entities:")
        for idx, (eid, etype, label) in enumerate(rows, 1):
            print(f"[{idx}] {etype}: {label}")

    @app.command()
    def delete(selector: str):
        """Delete an entity by index, UUID, or label."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                eid, etype, label = _resolve_entity(cur, selector)

                # Check for mentions
                cur.execute(
                    "SELECT COUNT(*) FROM mentions WHERE entity_id = %s",
                    (eid,),
                )
                mention_count = cur.fetchone()[0]
                if mention_count > 0:
                    print(f"Cannot delete: entity has {mention_count} mention(s)")
                    print("Delete mentions first, or use --force (not implemented)")
                    sys.exit(1)

                cur.execute("DELETE FROM entities WHERE id = %s", (eid,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Entity deleted: {etype} {label}")
