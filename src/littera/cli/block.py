"""Block commands: littera block add|list|edit|delete"""

import os
import sys
import uuid

import typer

from littera.db.workdb import open_work_db


def _resolve_section(cur, selector: str) -> tuple[str, str]:
    """Resolve section selector to (id, title)."""
    cur.execute("SELECT id, title FROM sections ORDER BY order_index")
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid section index: {selector}")
        sys.exit(1)

    # Try UUID match
    for sec_id, title in rows:
        if str(sec_id) == selector:
            return sec_id, title

    # Try title match
    matches = [(sid, t) for sid, t in rows if t == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous section title: {selector}")
        sys.exit(1)

    print(f"Section not found: {selector}")
    sys.exit(1)


def _resolve_block(cur, selector: str) -> tuple[str, str, str]:
    """Resolve block selector to (id, language, text)."""
    cur.execute("SELECT id, language, source_text FROM blocks ORDER BY created_at")
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid block index: {selector}")
        sys.exit(1)

    # Try UUID match
    for block_id, lang, text in rows:
        if str(block_id) == selector:
            return block_id, lang, text

    print(f"Block not found: {selector}")
    sys.exit(1)


def register(app: typer.Typer):
    @app.command()
    def add(
        section: str,
        text: str,
        lang: str = typer.Option("en", "--lang", "-l"),
    ):
        """Add a block to a section."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                sec_id, _ = _resolve_section(cur, section)

                block_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO blocks (id, section_id, block_type, language, source_text)
                    VALUES (%s, %s, 'paragraph', %s, %s)
                    """,
                    (block_id, sec_id, lang, text),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Block added ({lang})")

    @app.command("list")
    def list_blocks(section: str):
        """List blocks in a section."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                sec_id, sec_title = _resolve_section(cur, section)
                cur.execute(
                    "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                    (sec_id,),
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print(f"No blocks in '{sec_title}' yet.")
            return

        print(f"Blocks in '{sec_title}':")
        for idx, (_, lang, text) in enumerate(rows, 1):
            preview = text.replace("\n", " ")[:60]
            print(f"[{idx}] ({lang}) {preview}")

    @app.command()
    def edit(block: str):
        """Edit a block's text."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                block_id, lang, text = _resolve_block(cur, block)

                # Use $EDITOR or fallback to stdin
                editor_cmd = os.environ.get("EDITOR")
                if editor_cmd:
                    import subprocess
                    import tempfile

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
                    print("--- Current text ---")
                    print(text)
                    print("--- Enter new text (Ctrl+D to finish) ---")
                    new_text = sys.stdin.read().rstrip("\n")

                cur.execute(
                    "UPDATE blocks SET source_text = %s WHERE id = %s",
                    (new_text, block_id),
                )
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Block updated ({lang})")

    @app.command()
    def delete(block: str):
        """Delete a block."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                block_id, lang, text = _resolve_block(cur, block)

                # Delete associated mentions first
                cur.execute("DELETE FROM mentions WHERE block_id = %s", (block_id,))
                cur.execute("DELETE FROM blocks WHERE id = %s", (block_id,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        preview = text.replace("\n", " ")[:40]
        print(f"✓ Block deleted: ({lang}) {preview}...")
