"""Mention-related CLI commands."""

import sys

import typer

from littera.db.workdb import open_work_db


def register(app: typer.Typer) -> None:
    app.command("mention-add")(mention_add)


def _resolve_block(cur, index: int):
    cur.execute(
        "SELECT id, language FROM blocks ORDER BY created_at LIMIT 1 OFFSET %s",
        (index - 1,),
    )
    row = cur.fetchone()
    if row is None:
        print("Block not found")
        sys.exit(1)
    return row


def _resolve_entity(cur, entity_type: str, name: str):
    cur.execute(
        "SELECT id FROM entities WHERE entity_type = %s AND canonical_label = %s",
        (entity_type, name),
    )
    row = cur.fetchone()
    if row is None:
        print("Entity not found")
        sys.exit(1)
    return row[0]


def mention_add(block: int, entity_type: str, name: str):
    """Add a mention linking a block to an entity."""
    try:
        with open_work_db() as db:
            cur = db.conn.cursor()

            block_id, language = _resolve_block(cur, block)
            entity_id = _resolve_entity(cur, entity_type, name)

            cur.execute(
                "INSERT INTO mentions (block_id, entity_id, language) VALUES (%s, %s, %s)",
                (block_id, entity_id, language),
            )
            db.conn.commit()
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    print(f"✓ Mention added: block {block} → {entity_type} {name}")
