"""Document commands: littera doc add|list|delete|rename|move"""

import sys
import uuid

import typer

from littera.db.workdb import open_work_db


def _resolve_doc(cur, selector: str) -> tuple[str, str]:
    """Resolve document selector (index, UUID, or title) to (id, title)."""
    cur.execute(
        "SELECT id, title FROM documents ORDER BY order_index NULLS LAST, created_at"
    )
    rows = cur.fetchall()

    if not rows:
        print("No documents found.")
        sys.exit(1)

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid index: {selector}")
        sys.exit(1)

    # Try UUID match
    for did, title in rows:
        if str(did) == selector:
            return did, title

    # Try title match
    matches = [(did, t) for did, t in rows if t == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous title: {selector}")
        sys.exit(1)

    print(f"Document not found: {selector}")
    sys.exit(1)


def register(app: typer.Typer):
    @app.command()
    def add(title: str):
        """Add a new document."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id = str(uuid.uuid4())
                cur.execute("SELECT id FROM works LIMIT 1")
                row = cur.fetchone()
                if row is None:
                    print("Error: No work found in database")
                    sys.exit(1)
                work_id = row[0]
                cur.execute(
                    "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
                    (doc_id, work_id, title),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Document added: {title}")

    @app.command("list")
    def list_docs():
        """List all documents."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute(
                    "SELECT id, title FROM documents "
                    "ORDER BY order_index NULLS LAST, created_at"
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No documents yet.")
            return

        print("Documents:")
        for idx, (doc_id, title) in enumerate(rows, 1):
            print(f"[{idx}] {title} ({doc_id})")

    @app.command()
    def move(selector: str, position: int):
        """Move a document to a new position (1-based)."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, doc_title = _resolve_doc(cur, selector)

                # Get all documents in current order
                cur.execute(
                    "SELECT id FROM documents "
                    "WHERE work_id = (SELECT work_id FROM documents WHERE id = %s) "
                    "ORDER BY order_index NULLS LAST, created_at",
                    (doc_id,),
                )
                ids = [str(r[0]) for r in cur.fetchall()]

                if position < 1 or position > len(ids):
                    print(f"Position must be between 1 and {len(ids)}")
                    sys.exit(1)

                # Remove target, insert at new position
                ids.remove(str(doc_id))
                ids.insert(position - 1, str(doc_id))

                # Bulk update order_index
                for idx, did in enumerate(ids, 1):
                    cur.execute(
                        "UPDATE documents SET order_index = %s WHERE id = %s",
                        (idx, did),
                    )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Document moved: {doc_title} → position {position}")

    @app.command()
    def delete(selector: str):
        """Delete a document by index or UUID."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, doc_title = _resolve_doc(cur, selector)

                # Count dependents before cascade
                cur.execute(
                    "SELECT COUNT(*) FROM sections WHERE document_id = %s",
                    (doc_id,),
                )
                sec_count = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM blocks b "
                    "JOIN sections s ON s.id = b.section_id "
                    "WHERE s.document_id = %s",
                    (doc_id,),
                )
                blk_count = cur.fetchone()[0]

                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        cascade = []
        if sec_count:
            cascade.append(f"{sec_count} section(s)")
        if blk_count:
            cascade.append(f"{blk_count} block(s)")
        suffix = f" (cascaded: {', '.join(cascade)})" if cascade else ""
        print(f"✓ Document deleted: {doc_title}{suffix}")

    @app.command()
    def rename(selector: str, new_title: str):
        """Rename a document by index, UUID, or title."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id, old_title = _resolve_doc(cur, selector)

                cur.execute(
                    "UPDATE documents SET title = %s WHERE id = %s",
                    (new_title, doc_id),
                )
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Document renamed: {old_title} → {new_title}")
