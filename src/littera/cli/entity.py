"""Entity-related CLI commands."""

import sys

import typer

from littera.db.workdb import open_work_db


def register(app: typer.Typer) -> None:
    app.command("entity-add")(entity_add)
    app.command("entity-list")(entity_list)


def entity_add(entity_type: str, name: str):
    """Add a new entity."""
    try:
        with open_work_db() as db:
            cur = db.conn.cursor()
            cur.execute(
                "INSERT INTO entities (entity_type, canonical_label) VALUES (%s, %s)",
                (entity_type, name),
            )
            db.conn.commit()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    print(f"✓ Entity added: {entity_type} {name}")


def entity_list():
    """List entities."""
    try:
        with open_work_db() as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT entity_type, canonical_label FROM entities ORDER BY created_at",
            )
            rows = cur.fetchall()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    if not rows:
        print("No entities yet.")
        return

    for idx, (etype, name) in enumerate(rows, start=1):
        print(f"[{idx}] {etype}: {name}")
