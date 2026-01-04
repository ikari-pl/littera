import sys
import uuid

from littera.db.workdb import open_work_db


def register(app):
    @app.command()
    def doc_add(title: str):
        """Add a new document to the work."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                doc_id = str(uuid.uuid4())
                work_id = db.cfg["work"]["id"]
                cur.execute(
                    "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
                    (doc_id, work_id, title),
                )
                db.conn.commit()
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        print(f"✓ Document added: {title}")

    @app.command()
    def doc_list():
        """List documents in the work."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute("SELECT id, title FROM documents ORDER BY created_at")
                rows = cur.fetchall()
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        if not rows:
            print("No documents yet.")
            return

        print("Documents:")
        for doc_id, title in rows:
            print(f"- {title} ({doc_id})")
