"""Review commands: littera review add|list|delete"""

from __future__ import annotations

import json
import sys
import uuid
from typing import Optional

import typer

from littera.db.workdb import open_work_db

VALID_SCOPES = {"work", "document", "section", "block", "entity", "alignment"}
VALID_SEVERITIES = {"low", "medium", "high"}


def _resolve_scope_id(cur, scope: str, selector: str) -> str:
    """Resolve a scope_id selector using the appropriate resolver."""
    if scope == "work":
        # Work scope_id is the work UUID — just validate it exists
        cur.execute("SELECT id FROM works WHERE id::text = %s", (selector,))
        row = cur.fetchone()
        if not row:
            print(f"Work not found: {selector}")
            sys.exit(1)
        return str(row[0])
    elif scope == "document":
        from littera.cli.section import _resolve_document

        doc_id, _ = _resolve_document(cur, selector)
        return str(doc_id)
    elif scope == "section":
        from littera.cli.block import _resolve_section_global

        sec_id, _ = _resolve_section_global(cur, selector)
        return str(sec_id)
    elif scope == "block":
        from littera.cli.block import _resolve_block_global

        block_id, _, _ = _resolve_block_global(cur, selector)
        return str(block_id)
    elif scope == "entity":
        from littera.cli.entity import _resolve_entity

        entity_id, _, _ = _resolve_entity(cur, selector)
        return str(entity_id)
    elif scope == "alignment":
        from littera.cli.alignment import _resolve_alignment

        alignment_id, _, _ = _resolve_alignment(cur, selector)
        return str(alignment_id)
    else:
        print(f"Invalid scope: {scope}")
        sys.exit(1)


def _resolve_review(cur, selector: str) -> tuple[str, str, str | None, str | None]:
    """Resolve review selector to (id, description, scope, scope_id)."""
    cur.execute(
        "SELECT id, description, scope, scope_id FROM reviews ORDER BY created_at"
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid review index: {selector} (have {len(rows)} reviews)")
        sys.exit(1)

    for rid, desc, scope, scope_id in rows:
        if str(rid) == selector:
            return rid, desc, scope, scope_id

    print(f"Review not found: {selector}")
    sys.exit(1)


def _get_work_id(cur) -> str:
    """Get the current work's UUID."""
    cur.execute("SELECT id FROM works LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("No work found. Run 'littera init' first.")
        sys.exit(1)
    return str(row[0])


def register(app: typer.Typer) -> None:
    @app.command()
    def add(
        description: str,
        scope: Optional[str] = typer.Option(None, "--scope", "-s"),
        scope_id: Optional[str] = typer.Option(None, "--scope-id"),
        type: Optional[str] = typer.Option(None, "--type", "-t"),
        severity: str = typer.Option("medium", "--severity"),
        metadata: Optional[str] = typer.Option(None, "--metadata", "-m"),
    ) -> None:
        """Add a review."""
        if severity not in VALID_SEVERITIES:
            print(f"Invalid severity: {severity} (must be low, medium, or high)")
            sys.exit(1)

        if scope and scope not in VALID_SCOPES:
            print(f"Invalid scope: {scope} (must be one of: {', '.join(sorted(VALID_SCOPES))})")
            sys.exit(1)

        if scope_id and not scope:
            print("--scope-id requires --scope")
            sys.exit(1)

        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                print(f"Invalid metadata JSON: {e}")
                sys.exit(1)

        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                work_id = _get_work_id(cur)

                resolved_scope_id = None
                if scope and scope_id:
                    resolved_scope_id = _resolve_scope_id(cur, scope, scope_id)

                review_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO reviews (id, work_id, scope, scope_id, issue_type, description, severity, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        review_id,
                        work_id,
                        scope,
                        resolved_scope_id,
                        type,
                        description,
                        severity,
                        json.dumps(parsed_metadata) if parsed_metadata else None,
                    ),
                )
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        scope_label = f" {scope}:{scope_id}" if scope else ""
        print(f"✓ Review added [{severity}]{scope_label}")

    @app.command("list")
    def list_reviews() -> None:
        """List all reviews."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                cur.execute(
                    """
                    SELECT id, scope, scope_id, issue_type, description, severity
                    FROM reviews
                    ORDER BY created_at
                    """
                )
                rows = cur.fetchall()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No reviews yet.")
            return

        print("Reviews:")
        for idx, (_, scope, scope_id, issue_type, desc, severity) in enumerate(rows, 1):
            scope_label = f" {scope}:{scope_id}" if scope else ""
            type_label = f" ({issue_type})" if issue_type else ""
            preview = desc.replace("\n", " ")[:60] if desc else ""
            print(f"[{idx}] [{severity}]{scope_label}{type_label} \"{preview}\"")

    @app.command()
    def delete(selector: str) -> None:
        """Delete a review by index or UUID."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                rid, desc, scope, scope_id = _resolve_review(cur, selector)
                cur.execute("DELETE FROM reviews WHERE id = %s", (rid,))
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        preview = desc.replace("\n", " ")[:40] if desc else ""
        print(f"✓ Review deleted: \"{preview}\"")
