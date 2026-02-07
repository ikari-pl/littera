"""Alignment commands: littera alignment add|list|delete|gaps

Cross-language block alignment CRUD and gap detection.
Alignments link blocks in different languages (e.g. en ↔ pl translations).
Gap detection finds entities missing labels in the target language.
"""

from __future__ import annotations

import sys
import uuid
from typing import Optional

import typer

from littera.db.workdb import open_work_db


def _resolve_block_global(cur, selector: str) -> tuple[str, str, str]:
    """Resolve a block selector across all blocks.

    Returns (id, language, source_text).
    Accepts: 1-based global index or UUID.
    """
    cur.execute(
        """
        SELECT b.id, b.language, b.source_text
        FROM blocks b
        JOIN sections s ON s.id = b.section_id
        JOIN documents d ON d.id = s.document_id
        ORDER BY d.created_at, s.order_index, b.created_at
        """
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid block index: {selector} (have {len(rows)} blocks total)")
        sys.exit(1)

    for block_id, lang, text in rows:
        if str(block_id) == selector:
            return block_id, lang, text

    print(f"Block not found: {selector}")
    sys.exit(1)


def _resolve_alignment(cur, selector: str) -> tuple[str, str, str]:
    """Resolve alignment selector to (id, source_block_id, target_block_id)."""
    cur.execute(
        "SELECT id, source_block_id, target_block_id FROM block_alignments ORDER BY created_at"
    )
    rows = cur.fetchall()

    if selector.isdigit():
        idx = int(selector)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
        print(f"Invalid alignment index: {selector} (have {len(rows)} alignments)")
        sys.exit(1)

    for aid, src, tgt in rows:
        if str(aid) == selector:
            return aid, src, tgt

    print(f"Alignment not found: {selector}")
    sys.exit(1)


def _preview(text: str, max_len: int = 40) -> str:
    """Truncated single-line preview of block text."""
    return text.replace("\n", " ")[:max_len]


def register(app: typer.Typer) -> None:
    """Register alignment commands to the alignment subgroup."""

    @app.command()
    def add(
        source_block: str,
        target_block: str,
        type: str = typer.Option("translation", "--type", "-t"),
    ) -> None:
        """Create an alignment between two blocks in different languages."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                src_id, src_lang, src_text = _resolve_block_global(cur, source_block)
                tgt_id, tgt_lang, tgt_text = _resolve_block_global(cur, target_block)

                if src_lang == tgt_lang:
                    print(f"Cannot align blocks in the same language ({src_lang})")
                    sys.exit(1)

                # Check for duplicate
                cur.execute(
                    """
                    SELECT id FROM block_alignments
                    WHERE (source_block_id = %s AND target_block_id = %s)
                       OR (source_block_id = %s AND target_block_id = %s)
                    """,
                    (src_id, tgt_id, tgt_id, src_id),
                )
                if cur.fetchone():
                    print("Alignment already exists between these blocks")
                    sys.exit(1)

                alignment_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO block_alignments (id, source_block_id, target_block_id, alignment_type)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (alignment_id, src_id, tgt_id, type),
                )
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(
            f'✓ Alignment added: ({src_lang}) "{_preview(src_text)}" '
            f'↔ ({tgt_lang}) "{_preview(tgt_text)}"'
        )

    @app.command("list")
    def list_alignments(
        block: Optional[str] = typer.Option(None, "--block", "-b"),
    ) -> None:
        """List block alignments."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                if block:
                    block_id, _, _ = _resolve_block_global(cur, block)
                    cur.execute(
                        """
                        SELECT a.id, sb.language, sb.source_text,
                               tb.language, tb.source_text, a.alignment_type
                        FROM block_alignments a
                        JOIN blocks sb ON sb.id = a.source_block_id
                        JOIN blocks tb ON tb.id = a.target_block_id
                        WHERE a.source_block_id = %s OR a.target_block_id = %s
                        ORDER BY a.created_at
                        """,
                        (block_id, block_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT a.id, sb.language, sb.source_text,
                               tb.language, tb.source_text, a.alignment_type
                        FROM block_alignments a
                        JOIN blocks sb ON sb.id = a.source_block_id
                        JOIN blocks tb ON tb.id = a.target_block_id
                        ORDER BY a.created_at
                        """
                    )
                rows = cur.fetchall()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if not rows:
            print("No alignments yet.")
            return

        print("Alignments:")
        for idx, (_, src_lang, src_text, tgt_lang, tgt_text, atype) in enumerate(rows, 1):
            print(
                f'[{idx}] ({src_lang}) "{_preview(src_text)}" '
                f'↔ ({tgt_lang}) "{_preview(tgt_text)}" [{atype}]'
            )

    @app.command()
    def delete(selector: str) -> None:
        """Delete an alignment by index or UUID."""
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()
                aid, src_id, tgt_id = _resolve_alignment(cur, selector)

                # Get info for confirmation
                cur.execute(
                    "SELECT language, source_text FROM blocks WHERE id = %s", (src_id,)
                )
                src_lang, src_text = cur.fetchone()
                cur.execute(
                    "SELECT language, source_text FROM blocks WHERE id = %s", (tgt_id,)
                )
                tgt_lang, tgt_text = cur.fetchone()

                cur.execute("DELETE FROM block_alignments WHERE id = %s", (aid,))
                db.conn.commit()

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        print(
            f'✓ Alignment deleted: ({src_lang}) "{_preview(src_text)}" '
            f'↔ ({tgt_lang}) "{_preview(tgt_text)}"'
        )

    @app.command()
    def gaps(
        block: Optional[str] = typer.Argument(None),
        suggest: bool = typer.Option(False, "--suggest", "-s"),
    ) -> None:
        """Detect entities missing labels in aligned languages.

        For each alignment, finds entities mentioned in the source block
        that lack an entity_labels row in the target block's language.

        With --suggest, calls a local LLM to propose translations.
        """
        try:
            with open_work_db() as db:
                cur = db.conn.cursor()

                if block:
                    block_id, _, _ = _resolve_block_global(cur, block)
                    cur.execute(
                        """
                        SELECT a.id, a.source_block_id, a.target_block_id,
                               sb.language, sb.source_text,
                               tb.language, tb.source_text
                        FROM block_alignments a
                        JOIN blocks sb ON sb.id = a.source_block_id
                        JOIN blocks tb ON tb.id = a.target_block_id
                        WHERE a.source_block_id = %s OR a.target_block_id = %s
                        ORDER BY a.created_at
                        """,
                        (block_id, block_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT a.id, a.source_block_id, a.target_block_id,
                               sb.language, sb.source_text,
                               tb.language, tb.source_text
                        FROM block_alignments a
                        JOIN blocks sb ON sb.id = a.source_block_id
                        JOIN blocks tb ON tb.id = a.target_block_id
                        ORDER BY a.created_at
                        """
                    )
                alignments = cur.fetchall()

                if not alignments:
                    print("No alignments to check.")
                    return

                # Lazy-load suggestion module only if needed
                suggest_fn = None
                if suggest:
                    from littera.linguistics.suggest import suggest_label
                    suggest_fn = suggest_label

                total_gaps = 0
                no_gap_count = 0

                for _, src_block_id, tgt_block_id, src_lang, src_text, tgt_lang, tgt_text in alignments:
                    # Check both directions: source→target and target→source
                    direction_gaps = []
                    for from_block_id, from_lang, to_lang in [
                        (src_block_id, src_lang, tgt_lang),
                        (tgt_block_id, tgt_lang, src_lang),
                    ]:
                        cur.execute(
                            """
                            SELECT DISTINCT e.id, e.entity_type, e.canonical_label
                            FROM mentions m
                            JOIN entities e ON e.id = m.entity_id
                            WHERE m.block_id = %s
                            """,
                            (from_block_id,),
                        )
                        entities = cur.fetchall()

                        for eid, etype, canonical in entities:
                            cur.execute(
                                "SELECT 1 FROM entity_labels WHERE entity_id = %s AND language = %s",
                                (eid, to_lang),
                            )
                            if not cur.fetchone():
                                direction_gaps.append((etype, canonical, from_lang, to_lang))

                    if not direction_gaps:
                        no_gap_count += 1
                        continue

                    # Deduplicate (same entity might appear in both directions)
                    seen = set()
                    unique_gaps = []
                    for etype, canonical, from_lang, to_lang in direction_gaps:
                        key = (canonical, to_lang)
                        if key not in seen:
                            seen.add(key)
                            unique_gaps.append((etype, canonical, from_lang, to_lang))

                    print(
                        f'Gaps for ({src_lang}) "{_preview(src_text)}" '
                        f'↔ ({tgt_lang}) "{_preview(tgt_text)}":'
                    )
                    for etype, canonical, from_lang, to_lang in unique_gaps:
                        total_gaps += 1
                        print(f'  {etype} "{canonical}" — no label for {to_lang}')

                        if suggest_fn:
                            suggestion = suggest_fn(canonical, etype, from_lang, to_lang)
                            if suggestion:
                                print(f"    Suggested: {suggestion}")
                                print(f"    → littera entity label-add {canonical} {to_lang} {suggestion}")
                            else:
                                print(f"    → littera entity label-add {canonical} {to_lang} <base_form>")
                        else:
                            print(f"    → littera entity label-add {canonical} {to_lang} <base_form>")

        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if no_gap_count:
            print(f"\nNo gaps for {no_gap_count} other alignment(s).")
        if total_gaps == 0:
            print("No gaps found.")
