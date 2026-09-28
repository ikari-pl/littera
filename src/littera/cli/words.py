"""Word counts for block source_text.

Shared by CLI, TUI, and desktop. Mentions are stored as
``{@Label|entity:uuid}`` in source_text; only the visible label is counted.
"""

from __future__ import annotations

import re
import sys
from typing import Optional

import typer

from littera.db.workdb import open_work_db

MENTION_RE = re.compile(r"\{@([^|{}]+)\|entity:[^}]+\}")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
MARKUP_RE = re.compile(r"[*_`#]+")


def visible_text(source_text: str | None) -> str:
    """Return source_text with mention/link markup reduced to visible words."""
    text = source_text or ""
    text = MENTION_RE.sub(r"\1", text)
    text = LINK_RE.sub(r"\1", text)
    text = MARKUP_RE.sub(" ", text)
    return text


def count_words(source_text: str | None) -> int:
    """Count whitespace-separated tokens after stripping mention markup."""
    return len(visible_text(source_text).split())


def count_scope(
    conn,
    document_id: Optional[str] = None,
    section_id: Optional[str] = None,
) -> dict:
    """Count words and blocks in a work, document, or section."""
    cur = conn.cursor()
    sql = (
        "SELECT b.source_text FROM blocks b "
        "JOIN sections s ON s.id = b.section_id "
        "JOIN documents d ON d.id = s.document_id "
    )
    params: list = []
    if section_id:
        sql += "WHERE b.section_id = %s "
        params.append(section_id)
    elif document_id:
        sql += "WHERE s.document_id = %s "
        params.append(document_id)
    cur.execute(sql, params)
    texts = [row[0] for row in cur.fetchall()]
    return {"words": sum(count_words(t) for t in texts), "blocks": len(texts)}


def format_count(stats: dict, scope: str = "work") -> str:
    return f"{stats['words']:,} words ({scope}, {stats['blocks']} blocks)"


def register(app: typer.Typer) -> None:
    @app.command()
    def wc(
        document: Optional[str] = typer.Option(
            None, "--document", "-d", help="Document index, UUID, or title"
        ),
        section: Optional[str] = typer.Option(
            None, "--section", "-s", help="Section index, UUID, or title"
        ),
    ) -> None:
        """Count words in the work, a document, or a section."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                document_id = None
                section_id = None
                scope = "work"
                if document:
                    from littera.cli.doc import _resolve_doc

                    document_id, title = _resolve_doc(cur, document)
                    scope = f"document {title}"
                if section:
                    if document_id:
                        from littera.cli.section import _resolve_section

                        section_id, title = _resolve_section(cur, document_id, section)
                    else:
                        from littera.cli.block import _resolve_section_global

                        section_id, title = _resolve_section_global(cur, section)
                    scope = f"section {title}"
                stats = count_scope(
                    db.conn, document_id=document_id, section_id=section_id
                )
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(format_count(stats, scope))
