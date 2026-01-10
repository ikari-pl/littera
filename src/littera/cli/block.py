import sys
import uuid


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
        if str(sec_id) == selector:
            return sec_id

    print("Section not found")
    sys.exit(1)


def register(app):
    import typer

    from littera.db.workdb import open_work_db

    @app.command()
    def block_add(
        section: str,
        text: str,
        lang: str = typer.Option("en", "--lang"),
    ):
        """Add a block to a section."""
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
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print("✓ Block added")

    @app.command()
    def block_list(section: str):
        """List blocks in a section."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                section_id = _resolve_section(cur, section)
                cur.execute(
                    "SELECT id, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                    (section_id,),
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No blocks yet.")
            return

        print("Blocks:")
        for idx, (_, lang, text) in enumerate(rows, start=1):
            preview = text.replace("\n", " ")[:60]
            print(f"[{idx}] ({lang}) {preview}")
