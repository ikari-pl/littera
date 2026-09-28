"""Block commands: littera block add|list|edit|delete|set-language|move

Section resolution: section selectors are scoped to a document when a
document context is available.  For `add` and `list`, the caller provides
an explicit section selector.  For `edit`, `delete`, and `set-language`,
blocks are resolved globally (UUIDs are unique) but index-based resolution
uses the section that owns the block.
"""

import os
import sys
import uuid

import typer

from littera.db.workdb import open_work_db

# Sibling lists (docs/sections/blocks) and the global block walk share one clause.
SIBLING_ORDER_SQL = "order_index NULLS LAST, created_at"
GLOBAL_BLOCK_ORDER_SQL = (
    "d.order_index NULLS LAST, d.created_at, d.id, "
    "s.order_index NULLS LAST, s.created_at, s.id, "
    "b.order_index NULLS LAST, b.created_at, b.id"
)

_SIBLING_PARENT = {
    "documents": "work_id",
    "sections": "document_id",
    "blocks": "section_id",
}


def reorder_siblings(cur, table: str, item_id: str, new_position: int) -> tuple[bool, int]:
    """Move an item among its siblings and rewrite order_index.

    ``table`` must be documents, sections, or blocks. Returns
    ``(True, count)`` on success, or ``(False, count)`` if the position is
    out of range. Count is 0 when the item is missing. Does not commit.
    """
    parent_col = _SIBLING_PARENT.get(table)
    if parent_col is None:
        return False, 0
    cur.execute(
        f"SELECT id FROM {table} "
        f"WHERE {parent_col} = (SELECT {parent_col} FROM {table} WHERE id = %s) "
        f"ORDER BY {SIBLING_ORDER_SQL}",
        (item_id,),
    )
    ids = [str(r[0]) for r in cur.fetchall()]
    item_id = str(item_id)
    if item_id not in ids:
        return False, 0
    if new_position < 1 or new_position > len(ids):
        return False, len(ids)
    ids.remove(item_id)
    ids.insert(new_position - 1, item_id)
    cur.executemany(
        f"UPDATE {table} SET order_index = %s WHERE id = %s",
        [(idx, row_id) for idx, row_id in enumerate(ids, 1)],
    )
    return True, len(ids)


def _looks_like_uuid(selector: str) -> bool:
    try:
        uuid.UUID(selector)
        return True
    except ValueError:
        return False


def _resolve_section_global(cur, selector: str) -> tuple[str, str]:
    """Resolve a section selector across all documents.

    Accepts: 1-based index (global order), UUID, or exact title.
    Warns if multiple sections share the same title.
    """
    cur.execute(
        """
        SELECT s.id, s.title, d.title
        FROM sections s
        JOIN documents d ON d.id = s.document_id
        ORDER BY d.order_index NULLS LAST, d.created_at, s.order_index NULLS LAST, s.created_at
        """
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            sec_id, sec_title, doc_title = rows[idx - 1]
            return sec_id, sec_title
        print(f"Invalid section index: {selector} (have {len(rows)} sections)")
        sys.exit(1)

    # Try UUID match
    for sec_id, sec_title, doc_title in rows:
        if str(sec_id) == selector:
            return sec_id, sec_title

    # Try title match
    matches = [(sid, st) for sid, st, dt in rows if st == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous section title: '{selector}' matches {len(matches)} sections across documents")
        print("Use a UUID or index to disambiguate.")
        sys.exit(1)

    print(f"Section not found: {selector}")
    sys.exit(1)


def _resolve_block_in_section(cur, section_id: str, selector: str) -> tuple[str, str, str]:
    """Resolve a block selector scoped to a specific section."""
    cur.execute(
        f"SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY {SIBLING_ORDER_SQL}",
        (section_id,),
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid block index: {selector} (section has {len(rows)} blocks)")
        sys.exit(1)

    # Try UUID match
    for block_id, lang, text in rows:
        if str(block_id) == selector:
            return block_id, lang, text

    print(f"Block not found in section: {selector}")
    sys.exit(1)


def _resolve_block_global(cur, selector: str) -> tuple[str, str, str]:
    """Resolve a block by UUID or global 1-based index (for edit/delete/move)."""
    if _looks_like_uuid(selector):
        cur.execute(
            "SELECT id, language, source_text FROM blocks WHERE id = %s",
            (selector,),
        )
        row = cur.fetchone()
        if row:
            return row
        print(f"Block not found: {selector}")
        sys.exit(1)

    # Index-based: resolve across all blocks (ordered by document/section/block)
    cur.execute(
        f"""
        SELECT b.id, b.language, b.source_text
        FROM blocks b
        JOIN sections s ON s.id = b.section_id
        JOIN documents d ON d.id = s.document_id
        ORDER BY {GLOBAL_BLOCK_ORDER_SQL}
        """
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid block index: {selector} (have {len(rows)} blocks total)")
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
                sec_id, _ = _resolve_section_global(cur, section)

                block_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO blocks (id, section_id, block_type, language, source_text, order_index)
                    VALUES (%s, %s, 'paragraph', %s, %s,
                            COALESCE((SELECT MAX(order_index)+1 FROM blocks WHERE section_id = %s), 1))
                    """,
                    (block_id, sec_id, lang, text, sec_id),
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
                sec_id, sec_title = _resolve_section_global(cur, section)
                cur.execute(
                    f"SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY {SIBLING_ORDER_SQL}",
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
                block_id, lang, text = _resolve_block_global(cur, block)

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
                block_id, lang, text = _resolve_block_global(cur, block)

                # Count dependents before cascade
                cur.execute(
                    "SELECT COUNT(*) FROM mentions WHERE block_id = %s",
                    (block_id,),
                )
                mention_count = cur.fetchone()[0]

                cur.execute("DELETE FROM blocks WHERE id = %s", (block_id,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        preview = text.replace("\n", " ")[:40]
        suffix = f" (cascaded: {mention_count} mention(s))" if mention_count else ""
        print(f"✓ Block deleted: ({lang}) {preview}...{suffix}")

    @app.command("set-language")
    def set_language(block: str, language: str):
        """Change a block's language."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                block_id, old_lang, text = _resolve_block_global(cur, block)

                cur.execute(
                    "UPDATE blocks SET language = %s WHERE id = %s",
                    (language, block_id),
                )
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Block language changed: {old_lang} → {language}")

    @app.command()
    def move(block: str, position: int):
        """Move a block to a new position within its section (1-based)."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                block_id, lang, text = _resolve_block_global(cur, block)
                ok, count = reorder_siblings(cur, "blocks", str(block_id), position)
                if not ok:
                    print(f"Position must be between 1 and {count}")
                    sys.exit(1)
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        preview = text.replace("\n", " ")[:40]
        print(f"✓ Block moved: ({lang}) {preview} → position {position}")
