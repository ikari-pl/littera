"""Section commands: littera section add|list|delete|rename"""

import sys
import uuid

import typer

from littera.db.workdb import open_work_db


def _resolve_document(cur, selector: str) -> tuple[str, str]:
    """Resolve document selector to (id, title)."""
    cur.execute("SELECT id, title FROM documents ORDER BY created_at")
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid document index: {selector}")
        sys.exit(1)

    # Try UUID match
    for doc_id, title in rows:
        if str(doc_id) == selector:
            return doc_id, title

    # Try title match
    matches = [(did, t) for did, t in rows if t == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous document title: {selector}")
        sys.exit(1)

    print(f"Document not found: {selector}")
    sys.exit(1)


def _resolve_section(cur, doc_id: str, selector: str) -> tuple[str, str]:
    """Resolve section selector to (id, title)."""
    cur.execute(
        "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
        (doc_id,),
    )
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


def register(app: typer.Typer):
    @app.command()
    def add(document: str, title: str):
        """Add a section to a document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, _ = _resolve_document(cur, document)

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
                    (section_id, doc_id, title, doc_id),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Section added: {title}")

    @app.command("list")
    def list_sections(document: str):
        """List sections in a document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, doc_title = _resolve_document(cur, document)
                cur.execute(
                    "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
                    (doc_id,),
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print(f"No sections in '{doc_title}' yet.")
            return

        print(f"Sections in '{doc_title}':")
        for idx, (sec_id, title) in enumerate(rows, 1):
            print(f"[{idx}] {title}")

    @app.command()
    def delete(document: str, section: str):
        """Delete a section from a document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, _ = _resolve_document(cur, document)
                sec_id, sec_title = _resolve_section(cur, doc_id, section)

                # Count dependents before cascade
                cur.execute(
                    "SELECT COUNT(*) FROM blocks WHERE section_id = %s",
                    (sec_id,),
                )
                blk_count = cur.fetchone()[0]

                cur.execute("DELETE FROM sections WHERE id = %s", (sec_id,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        suffix = f" (cascaded: {blk_count} block(s))" if blk_count else ""
        print(f"✓ Section deleted: {sec_title}{suffix}")

    @app.command()
    def rename(document: str, section: str, new_title: str):
        """Rename a section in a document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, _ = _resolve_document(cur, document)
                sec_id, old_title = _resolve_section(cur, doc_id, section)

                cur.execute(
                    "UPDATE sections SET title = %s WHERE id = %s",
                    (new_title, sec_id),
                )
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Section renamed: {old_title} → {new_title}")
