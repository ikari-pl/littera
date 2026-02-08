"""Section commands: littera section add|list|delete|move"""

import sys
import uuid

import typer

from littera.db.workdb import open_work_db


def _resolve_document(cur, selector: str) -> tuple[str, str]:
    """Resolve document selector to (id, title)."""
    cur.execute("SELECT id, title FROM documents ORDER BY order_index NULLS LAST, created_at")
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
        "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index NULLS LAST, created_at",
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
                    "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index NULLS LAST, created_at",
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
    def move(document: str, section: str, position: int):
        """Move a section within its document to a new position (1-based)."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, _ = _resolve_document(cur, document)
                sec_id, sec_title = _resolve_section(cur, doc_id, section)

                # Get all sections for this document in current order
                cur.execute(
                    "SELECT id FROM sections WHERE document_id = %s "
                    "ORDER BY order_index NULLS LAST, created_at",
                    (doc_id,),
                )
                ids = [str(r[0]) for r in cur.fetchall()]

                if position < 1 or position > len(ids):
                    print(f"Position must be between 1 and {len(ids)}")
                    sys.exit(1)

                # Remove target, insert at new position
                ids.remove(str(sec_id))
                ids.insert(position - 1, str(sec_id))

                # Bulk update order_index
                for idx, sid in enumerate(ids, 1):
                    cur.execute(
                        "UPDATE sections SET order_index = %s WHERE id = %s",
                        (idx, sid),
                    )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Section moved: {sec_title} → position {position}")

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
