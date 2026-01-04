"""Block editing CLI command.

Allows editing a block’s text via $EDITOR or a simple
fallback CLI prompt.
"""

from __future__ import annotations

import os
import sys

import typer

from littera.db.workdb import open_work_db


def _resolve_section(cur, selector: str) -> str:
    """Resolve section selector (index | UUID | name) to section UUID."""
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
    """Resolve block selector (index | UUID | name) to block UUID."""
    cur.execute("SELECT id FROM blocks ORDER BY created_at")
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1][0]
        print("Invalid block index")
        sys.exit(1)

    # UUID fallback
    for (block_id,) in rows:
        if block_id == selector:
            return block_id

    print("Block not found")
    sys.exit(1)


def register(app: typer.Typer) -> None:
    app.command("block-edit")(block_edit)


def block_edit(
    block_selector: str,
    section: str | None = typer.Argument(None, help="Section selector (optional)"),
) -> None:
    """Edit a block’s text."""
    try:
        with open_work_db() as db:
            cur = db.conn.cursor()

            # Resolve block
            block_id = _resolve_block(cur, block_selector)
            cur.execute(
                "SELECT language, source_text FROM blocks WHERE id = %s", (block_id,)
            )
            row = cur.fetchone()
            if row is None:
                print("Block not found")
                sys.exit(1)
            lang, text = row

            # Apply $EDITOR or fall back to a simple prompt
            editor_cmd = os.environ.get("EDITOR", None)
            if editor_cmd:
                import tempfile
                import subprocess

                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".txt", delete=False
                ) as tf:
                    tf.write(text)
                    tf.flush()
                    subprocess.run([editor_cmd, tf.name], check=True)
                    with open(tf.name, "r") as rf:
                        new_text = rf.read()
                os.unlink(tf.name)
                new_text = new_text.rstrip("\n")
            else:
                print("--- Current text (Ctrl+D to finish) ---")
                print(text)
                print("--- New text (Ctrl+D to finish) ---")
                new_text = sys.stdin.read().rstrip("\n")

            cur.execute(
                "UPDATE blocks SET source_text = %s WHERE id = %s",
                (new_text, block_id),
            )
            db.conn.commit()
            print(f"✓ Block updated ({lang})")
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)
