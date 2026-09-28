"""Review commands: littera review add|list|edit|delete"""

from __future__ import annotations

import json
import sys
import uuid
from typing import Optional

import typer

from littera.db.workdb import open_work_db

VALID_SCOPES = {"work", "document", "section", "block", "entity", "alignment"}
VALID_SEVERITIES = {"low", "medium", "high"}

# Sentinel so callers can pass None to clear a field vs omit it.
UNSET = object()


class ReviewUpdateError(ValueError):
    """Invalid review update (empty description, bad scope, nothing to change)."""

    def __init__(self, message: str, http_error: str | None = None):
        super().__init__(message)
        self.http_error = http_error or message


def apply_review_update(
    cur,
    review_id: str,
    *,
    description=UNSET,
    severity=UNSET,
    issue_type=UNSET,
    metadata=UNSET,
    scope=UNSET,
    scope_id=UNSET,
    clear_scope: bool = False,
) -> None:
    """Update only the fields the caller passed. Does not commit.

    ``metadata=None`` clears metadata. ``clear_scope`` nulls scope and scope_id.
    Raises ReviewUpdateError on validation failure or missing review.
    """
    cur.execute("SELECT id, scope FROM reviews WHERE id = %s", (review_id,))
    row = cur.fetchone()
    if row is None:
        raise ReviewUpdateError("review not found", "review not found")
    current_scope = row[1]

    updates: list[str] = []
    params: list = []

    if description is not UNSET:
        if not str(description).strip():
            raise ReviewUpdateError(
                "Description cannot be empty", "description cannot be empty"
            )
        updates.append("description = %s")
        params.append(description)

    if severity is not UNSET:
        if severity not in VALID_SEVERITIES:
            raise ReviewUpdateError(
                f"Invalid severity: {severity} (must be low, medium, or high)",
                "invalid severity",
            )
        updates.append("severity = %s")
        params.append(severity)

    if issue_type is not UNSET:
        updates.append("issue_type = %s")
        params.append(issue_type if issue_type else None)

    if metadata is not UNSET:
        if metadata is None or metadata == "":
            updates.append("metadata = NULL")
        else:
            updates.append("metadata = %s")
            params.append(
                metadata if isinstance(metadata, str) else json.dumps(metadata)
            )

    if clear_scope:
        updates.append("scope = NULL")
        updates.append("scope_id = NULL")
    elif scope is not UNSET:
        if scope is not None and scope not in VALID_SCOPES:
            raise ReviewUpdateError(
                f"Invalid scope: {scope} (must be one of: {', '.join(sorted(VALID_SCOPES))})",
                "invalid scope",
            )
        updates.append("scope = %s")
        params.append(scope)
        if scope_id is not UNSET:
            updates.append("scope_id = %s")
            params.append(scope_id)
        elif scope != current_scope:
            raise ReviewUpdateError(
                "scope_id required when changing scope",
                "scope_id required when changing scope",
            )

    if not updates:
        raise ReviewUpdateError("Nothing to change. Provide at least one field.")

    params.append(review_id)
    cur.execute(
        f"UPDATE reviews SET {', '.join(updates)} WHERE id = %s",
        params,
    )


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
    def edit(
        selector: str,
        description: Optional[str] = typer.Option(None, "--description", "-d"),
        scope: Optional[str] = typer.Option(None, "--scope", "-s"),
        scope_id: Optional[str] = typer.Option(None, "--scope-id"),
        type: Optional[str] = typer.Option(None, "--type", "-t"),
        severity: Optional[str] = typer.Option(None, "--severity"),
        metadata: Optional[str] = typer.Option(None, "--metadata", "-m"),
        clear_scope: bool = typer.Option(False, "--clear-scope"),
    ) -> None:
        """Edit a review. Only provided fields are changed."""
        if severity is not None and severity not in VALID_SEVERITIES:
            print(f"Invalid severity: {severity} (must be low, medium, or high)")
            sys.exit(1)

        if scope is not None and scope not in VALID_SCOPES:
            print(f"Invalid scope: {scope} (must be one of: {', '.join(sorted(VALID_SCOPES))})")
            sys.exit(1)

        if scope_id and not scope:
            print("--scope-id requires --scope")
            sys.exit(1)

        if clear_scope and (scope or scope_id):
            print("--clear-scope cannot be combined with --scope")
            sys.exit(1)

        parsed_metadata = None
        if metadata is not None:
            if metadata == "":
                parsed_metadata = ""
            else:
                try:
                    parsed_metadata = json.loads(metadata)
                except json.JSONDecodeError as e:
                    print(f"Invalid metadata JSON: {e}")
                    sys.exit(1)

        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                rid, desc, current_scope, _ = _resolve_review(cur, selector)

                fields: dict = {}
                if description is not None:
                    fields["description"] = description
                if severity is not None:
                    fields["severity"] = severity
                if type is not None:
                    fields["issue_type"] = type if type else None
                if metadata is not None:
                    fields["metadata"] = None if parsed_metadata == "" else parsed_metadata
                if clear_scope:
                    fields["clear_scope"] = True
                elif scope is not None:
                    fields["scope"] = scope
                    if scope_id:
                        fields["scope_id"] = _resolve_scope_id(cur, scope, scope_id)
                    elif scope != current_scope:
                        print("--scope-id required when changing scope")
                        sys.exit(1)

                try:
                    apply_review_update(cur, rid, **fields)
                except ReviewUpdateError as e:
                    print(str(e))
                    sys.exit(1)
                db.conn.commit()
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        preview = (description or desc or "").replace("\n", " ")[:40]
        print(f"✓ Review updated: \"{preview}\"")

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
