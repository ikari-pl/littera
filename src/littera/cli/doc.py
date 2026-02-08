"""Document commands: littera doc add|list|delete|rename"""

import sys
import uuid

import typer

from littera.db.workdb import open_work_db


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
                cur.execute("SELECT id, title FROM documents ORDER BY created_at")
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
    def delete(selector: str):
        """Delete a document by index or UUID."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                # Resolve selector to document ID
                cur.execute("SELECT id, title FROM documents ORDER BY created_at")
                rows = cur.fetchall()

                if not rows:
                    print("No documents to delete.")
                    sys.exit(1)

                doc_id = None
                doc_title = None

                if selector.isdigit():
                    idx = int(selector)
                    if 1 <= idx <= len(rows):
                        doc_id, doc_title = rows[idx - 1]
                    else:
                        print(f"Invalid index: {selector}")
                        sys.exit(1)
                else:
                    # Try matching by UUID
                    for did, title in rows:
                        if str(did) == selector:
                            doc_id, doc_title = did, title
                            break
                    if doc_id is None:
                        # Try matching by title
                        matches = [(did, t) for did, t in rows if t == selector]
                        if len(matches) == 1:
                            doc_id, doc_title = matches[0]
                        elif len(matches) > 1:
                            print(f"Ambiguous title: {selector}")
                            sys.exit(1)
                        else:
                            print(f"Document not found: {selector}")
                            sys.exit(1)

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

                # Resolve selector to document ID
                cur.execute("SELECT id, title FROM documents ORDER BY created_at")
                rows = cur.fetchall()

                if not rows:
                    print("No documents to rename.")
                    sys.exit(1)

                doc_id = None
                old_title = None

                if selector.isdigit():
                    idx = int(selector)
                    if 1 <= idx <= len(rows):
                        doc_id, old_title = rows[idx - 1]
                    else:
                        print(f"Invalid index: {selector}")
                        sys.exit(1)
                else:
                    # Try matching by UUID
                    for did, title in rows:
                        if str(did) == selector:
                            doc_id, old_title = did, title
                            break
                    if doc_id is None:
                        # Try matching by title
                        matches = [(did, t) for did, t in rows if t == selector]
                        if len(matches) == 1:
                            doc_id, old_title = matches[0]
                        elif len(matches) > 1:
                            print(f"Ambiguous title: {selector}")
                            sys.exit(1)
                        else:
                            print(f"Document not found: {selector}")
                            sys.exit(1)

                cur.execute(
                    "UPDATE documents SET title = %s WHERE id = %s",
                    (new_title, doc_id),
                )
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Document renamed: {old_title} → {new_title}")
