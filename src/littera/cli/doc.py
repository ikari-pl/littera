"""Document commands: littera doc add|list|delete"""

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

                # Check for sections
                cur.execute(
                    "SELECT COUNT(*) FROM sections WHERE document_id = %s",
                    (doc_id,),
                )
                section_count = cur.fetchone()[0]
                if section_count > 0:
                    print(f"Cannot delete: document has {section_count} section(s)")
                    print("Delete sections first, or use --force (not implemented)")
                    sys.exit(1)

                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(f"✓ Document deleted: {doc_title}")
