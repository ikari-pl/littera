from __future__ import annotations

import sys

from littera.db.workdb import open_work_db


def register(app):
    @app.command()
    def status():
        try:
            with open_work_db() as db:
                work_name = db.work_dir.name

                print(f"Littera work: {work_name}\n")
                print("Database:")

                started = "started" if db.started_here else "already running"
                print(
                    f"  ✓ Embedded Postgres available ({started}, port {db.pg_cfg.port})"
                )
                print(f"  ✓ Database: {db.pg_cfg.db_name}")

                cur = db.conn.cursor()

                cur.execute("SELECT COUNT(*) FROM documents")
                doc_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM sections")
                sec_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM blocks")
                blk_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM entities")
                ent_count = cur.fetchone()[0]

                print("\nContent:")
                print(f"  • Documents: {doc_count}")
                print(f"  • Sections:  {sec_count}")
                print(f"  • Blocks:    {blk_count}")
                print(f"  • Entities:  {ent_count}")
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)
