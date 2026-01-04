"""
Block management helpers for CLI: delete, create, resolve selectors.

These are intentionally split from block.py to keep editing flows
separate from list/add commands.
"""

from __future__ import annotations

import sys
import uuid

import typer

from littera.db.workdb import open_work_db


def _resolve_section(cur, selector: str) -> str:
    cur.execute("SELECT id, title FROM sections ORDER BY order_index")
    rows = cur.fetchall()
    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1][0]
        print("Invalid section index")
        sys.exit(1)
    matches = [sec_id for sec_id, title in rows if title == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print("Ambiguous section name")
        sys.exit(1)
    for sec_id, _ in rows:
        if sec_id == selector:
            return sec_id
    print("Section not found")
    sys.exit(1)


def _resolve_block(cur, selector: str) -> str:
    cur.execute("SELECT id FROM blocks ORDER BY created_at")
    rows = cur.fetchall()
    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1][0]
        print("Invalid block index")
        sys.exit(1)
    for (block_id,) in rows:
        if block_id == selector:
            return block_id
    print("Block not found")
    sys.exit(1)


def register(app: typer.Typer) -> None:
    app.command("block-create")(block_create)
    app.command("block-delete")(block_delete)


def block_create(
    section: str,
    text: str,
    lang: str = typer.Option("en", "--lang"),
) -> None:
    """Create a new block."""
    try:
        with open_work_db() as db:
            cur = db.conn.cursor()
            section_id = _resolve_section(cur, section)
            block_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO blocks (id, section_id, block_type, language, source_text)
                VALUES (%s, %s, 'paragraph', %s, %s)
                """,
                (block_id, section_id, lang, text),
            )
            db.conn.commit()
            print(f"✓ Block created ({lang})")
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)


def block_delete(
    selector: str,
) -> None:
    """Delete a block."""
    try:
        with open_work_db() as db:
            cur = db.conn.cursor()
            block_id = _resolve_block(cur, selector)
            cur.execute("DELETE FROM blocks WHERE id = %s", (block_id,))
            db.conn.commit()
            print(f"✓ Block deleted: {selector}")
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)
