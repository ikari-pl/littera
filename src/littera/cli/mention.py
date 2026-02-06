"""Mention commands: littera mention add|list|delete"""

import sys
import uuid

import typer

from littera.db.workdb import open_work_db


def _resolve_block(cur, selector: str) -> tuple[str, str]:
    """Resolve block selector to (id, language)."""
    cur.execute("SELECT id, language FROM blocks ORDER BY created_at")
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid block index: {selector}")
        sys.exit(1)

    # Try UUID match
    for block_id, lang in rows:
        if str(block_id) == selector:
            return block_id, lang

    print(f"Block not found: {selector}")
    sys.exit(1)


def _resolve_entity(cur, entity_type: str, name: str) -> str:
    """Resolve entity by type and name to id."""
    cur.execute(
        "SELECT id FROM entities WHERE entity_type = %s AND canonical_label = %s",
        (entity_type, name),
    )
    row = cur.fetchone()
    if row is None:
        print(f"Entity not found: {entity_type} {name}")
        sys.exit(1)
    return row[0]


def _resolve_mention(cur, selector: str) -> tuple[str, str, str]:
    """Resolve mention selector to (id, block_id, entity_id)."""
    cur.execute("SELECT id, block_id, entity_id FROM mentions ORDER BY id")
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid mention index: {selector}")
        sys.exit(1)

    # Try UUID match
    for mid, bid, eid in rows:
        if str(mid) == selector:
            return mid, bid, eid

    print(f"Mention not found: {selector}")
    sys.exit(1)


def register(app: typer.Typer):
    @app.command()
    def add(block: str, entity_type: str, name: str):
        """Add a mention linking a block to an entity."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                block_id, language = _resolve_block(cur, block)
                entity_id = _resolve_entity(cur, entity_type, name)

                mention_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO mentions (id, block_id, entity_id, language) VALUES (%s, %s, %s, %s)",
                    (mention_id, block_id, entity_id, language),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Mention added: block → {entity_type} {name}")

    @app.command("list")
    def list_mentions():
        """List all mentions."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute(
                    """
                    SELECT m.id, b.source_text, e.entity_type, e.canonical_label
                    FROM mentions m
                    JOIN blocks b ON m.block_id = b.id
                    JOIN entities e ON m.entity_id = e.id
                    ORDER BY b.created_at
                    """
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No mentions yet.")
            return

        print("Mentions:")
        for idx, (mid, block_text, etype, label) in enumerate(rows, 1):
            preview = block_text.replace("\n", " ")[:30]
            print(f"[{idx}] \"{preview}...\" → {etype}: {label}")

    @app.command()
    def delete(selector: str):
        """Delete a mention by index or UUID."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                mid, block_id, entity_id = _resolve_mention(cur, selector)

                # Get info for confirmation message
                cur.execute(
                    "SELECT entity_type, canonical_label FROM entities WHERE id = %s",
                    (entity_id,),
                )
                row = cur.fetchone()
                etype, label = row if row else ("?", "?")

                cur.execute("DELETE FROM mentions WHERE id = %s", (mid,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Mention deleted: → {etype}: {label}")
