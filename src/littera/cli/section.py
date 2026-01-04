import sys
import uuid

from littera.db.workdb import open_work_db


def register(app):
    def resolve_document_id(cur, selector: str) -> str:
        if selector.isdigit():
            cur.execute(
                "SELECT id FROM documents ORDER BY created_at LIMIT 1 OFFSET %s",
                (int(selector) - 1,),
            )
            row = cur.fetchone()
            if row is None:
                print("Document not found")
                sys.exit(1)
            return row[0]

        cur.execute(
            "SELECT id FROM documents WHERE title = %s ORDER BY created_at LIMIT 1",
            (selector,),
        )
        row = cur.fetchone()
        if row is not None:
            return row[0]

        return selector

    @app.command()
    def section_add(document: str, title: str):
        """Add a section to a document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                document_id = resolve_document_id(cur, document)

                section_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO sections (id, document_id, title, order_index)
                    VALUES (%s, %s, %s,
                        COALESCE(
                            (SELECT MAX(order_index) + 1 FROM sections WHERE document_id = %s),
                            1
                        )
                    )
                    """,
                    (section_id, document_id, title, document_id),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Section added: {title}")

    @app.command()
    def section_list(document: str):
        """List sections in a document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                document_id = resolve_document_id(cur, document)
                cur.execute(
                    "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
                    (document_id,),
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No sections yet.")
            return

        print("Sections:")
        for idx, (sec_id, title) in enumerate(rows, start=1):
            print(f"[{idx}] {title}")
