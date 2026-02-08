"""Import/export commands: littera export json|markdown, littera import json

Round-trip JSON preserves all structure and metadata.
Markdown export is read-only, for human consumption.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import typer

from littera.db.workdb import open_work_db


# =========================================================================
# Shared export logic (used by CLI and desktop sidecar)
# =========================================================================


def export_work_json(conn) -> dict:
    """Build the full JSON export structure from a database connection."""
    cur = conn.cursor()

    # Work metadata
    cur.execute("SELECT id, title, description, default_language FROM works LIMIT 1")
    work_row = cur.fetchone()
    if work_row is None:
        return {"littera_version": "1.0", "work": None}

    work_id, work_title, work_desc, default_lang = work_row

    # Documents with sections and blocks
    cur.execute(
        "SELECT id, title FROM documents WHERE work_id = %s ORDER BY order_index, created_at",
        (work_id,),
    )
    documents = []
    for doc_id, doc_title in cur.fetchall():
        cur.execute(
            "SELECT id, title, order_index FROM sections WHERE document_id = %s ORDER BY order_index",
            (doc_id,),
        )
        sections = []
        for sec_id, sec_title, order_idx in cur.fetchall():
            cur.execute(
                "SELECT id, block_type, language, source_text "
                "FROM blocks WHERE section_id = %s ORDER BY created_at",
                (sec_id,),
            )
            blocks = [
                {
                    "id": str(bid),
                    "block_type": btype,
                    "language": lang,
                    "source_text": text,
                }
                for bid, btype, lang, text in cur.fetchall()
            ]
            sections.append(
                {
                    "id": str(sec_id),
                    "title": sec_title,
                    "order_index": order_idx,
                    "blocks": blocks,
                }
            )
        documents.append(
            {
                "id": str(doc_id),
                "title": doc_title,
                "sections": sections,
            }
        )

    # Entities with labels
    cur.execute(
        "SELECT id, entity_type, canonical_label, properties FROM entities ORDER BY created_at"
    )
    entities = []
    for eid, etype, canonical, props in cur.fetchall():
        cur.execute(
            "SELECT language, base_form FROM entity_labels WHERE entity_id = %s ORDER BY language",
            (eid,),
        )
        labels = [
            {"language": lang, "base_form": bf} for lang, bf in cur.fetchall()
        ]
        entities.append(
            {
                "id": str(eid),
                "entity_type": etype,
                "canonical_label": canonical,
                "properties": props,
                "labels": labels,
            }
        )

    # Mentions
    cur.execute(
        "SELECT block_id, entity_id, language, surface_form, features FROM mentions ORDER BY id"
    )
    mentions = [
        {
            "block_id": str(bid),
            "entity_id": str(eid),
            "language": lang,
            "surface_form": sf,
            "features": feat,
        }
        for bid, eid, lang, sf, feat in cur.fetchall()
    ]

    # Alignments
    cur.execute(
        "SELECT source_block_id, target_block_id, alignment_type FROM block_alignments ORDER BY created_at"
    )
    alignments = [
        {
            "source_block_id": str(src),
            "target_block_id": str(tgt),
            "alignment_type": atype,
        }
        for src, tgt, atype in cur.fetchall()
    ]

    # Reviews
    cur.execute(
        "SELECT description, severity, scope, issue_type FROM reviews WHERE work_id = %s ORDER BY created_at",
        (work_id,),
    )
    reviews = [
        {
            "description": desc,
            "severity": sev,
            "scope": scope,
            "issue_type": itype,
        }
        for desc, sev, scope, itype in cur.fetchall()
    ]

    return {
        "littera_version": "1.0",
        "work": {
            "title": work_title,
            "description": work_desc,
            "default_language": default_lang,
            "documents": documents,
            "entities": entities,
            "mentions": mentions,
            "alignments": alignments,
            "reviews": reviews,
        },
    }


def export_work_markdown(conn) -> str:
    """Build a Markdown representation of the work."""
    cur = conn.cursor()

    cur.execute("SELECT id, title FROM works LIMIT 1")
    work_row = cur.fetchone()
    if work_row is None:
        return "# (empty work)\n"

    work_id, work_title = work_row
    lines = [f"# {work_title or 'Untitled'}", ""]

    cur.execute(
        "SELECT id, title FROM documents WHERE work_id = %s ORDER BY order_index, created_at",
        (work_id,),
    )
    for doc_id, doc_title in cur.fetchall():
        lines.append(f"## Document: {doc_title or 'Untitled'}")
        lines.append("")

        cur.execute(
            "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index",
            (doc_id,),
        )
        for sec_id, sec_title in cur.fetchall():
            lines.append(f"### {sec_title or 'Untitled'}")
            lines.append("")

            cur.execute(
                "SELECT language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                (sec_id,),
            )
            for lang, text in cur.fetchall():
                lines.append(f"[{lang}] {text}")
                lines.append("")

    return "\n".join(lines)


def import_work_json(conn, data: dict) -> dict:
    """Import JSON data into the current work. Returns summary counts.

    Uses a single transaction for atomicity. Entities are deduplicated
    by canonical_label. UUIDs from the JSON are preserved where possible.
    """
    cur = conn.cursor()

    cur.execute("SELECT id FROM works LIMIT 1")
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("No work found. Run 'littera init' first.")
    work_id = row[0]

    work_data = data.get("work")
    if work_data is None:
        raise ValueError("Invalid export data: missing 'work' key")

    counts = {
        "documents": 0,
        "sections": 0,
        "blocks": 0,
        "entities": 0,
        "labels": 0,
        "mentions": 0,
        "alignments": 0,
        "reviews": 0,
    }

    # --- Entities (deduplicate by canonical_label) ---
    entity_id_map: dict[str, str] = {}  # old_id -> new_id
    for ent in work_data.get("entities", []):
        canonical = ent.get("canonical_label")
        etype = ent.get("entity_type", "concept")
        props = ent.get("properties")
        old_id = ent.get("id")

        # Check if entity already exists by canonical_label
        cur.execute(
            "SELECT id FROM entities WHERE canonical_label = %s",
            (canonical,),
        )
        existing = cur.fetchone()
        if existing:
            entity_id_map[old_id] = str(existing[0])
        else:
            new_id = old_id or str(uuid.uuid4())
            # Handle potential UUID collision
            cur.execute("SELECT id FROM entities WHERE id = %s", (new_id,))
            if cur.fetchone():
                new_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO entities (id, entity_type, canonical_label, properties) "
                "VALUES (%s, %s, %s, %s)",
                (new_id, etype, canonical, json.dumps(props) if props else None),
            )
            entity_id_map[old_id] = new_id
            counts["entities"] += 1

        # Labels for this entity
        resolved_eid = entity_id_map[old_id]
        for label in ent.get("labels", []):
            lang = label.get("language")
            bf = label.get("base_form")
            if lang and bf:
                cur.execute(
                    "SELECT id FROM entity_labels WHERE entity_id = %s AND language = %s",
                    (resolved_eid, lang),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO entity_labels (id, entity_id, language, base_form) "
                        "VALUES (%s, %s, %s, %s)",
                        (str(uuid.uuid4()), resolved_eid, lang, bf),
                    )
                    counts["labels"] += 1

    # --- Documents, Sections, Blocks ---
    block_id_map: dict[str, str] = {}  # old_id -> new_id
    for doc in work_data.get("documents", []):
        doc_old_id = doc.get("id")
        doc_new_id = doc_old_id or str(uuid.uuid4())
        # Handle UUID collision
        cur.execute("SELECT id FROM documents WHERE id = %s", (doc_new_id,))
        if cur.fetchone():
            doc_new_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO documents (id, work_id, title) VALUES (%s, %s, %s)",
            (doc_new_id, work_id, doc.get("title")),
        )
        counts["documents"] += 1

        for sec in doc.get("sections", []):
            sec_old_id = sec.get("id")
            sec_new_id = sec_old_id or str(uuid.uuid4())
            cur.execute("SELECT id FROM sections WHERE id = %s", (sec_new_id,))
            if cur.fetchone():
                sec_new_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO sections (id, document_id, title, order_index) "
                "VALUES (%s, %s, %s, %s)",
                (sec_new_id, doc_new_id, sec.get("title"), sec.get("order_index")),
            )
            counts["sections"] += 1

            for blk in sec.get("blocks", []):
                blk_old_id = blk.get("id")
                blk_new_id = blk_old_id or str(uuid.uuid4())
                cur.execute("SELECT id FROM blocks WHERE id = %s", (blk_new_id,))
                if cur.fetchone():
                    blk_new_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO blocks (id, section_id, block_type, language, source_text) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        blk_new_id,
                        sec_new_id,
                        blk.get("block_type", "paragraph"),
                        blk.get("language", "en"),
                        blk.get("source_text", ""),
                    ),
                )
                block_id_map[blk_old_id] = blk_new_id
                counts["blocks"] += 1

    # --- Mentions ---
    for m in work_data.get("mentions", []):
        old_block_id = m.get("block_id")
        old_entity_id = m.get("entity_id")
        block_id = block_id_map.get(old_block_id, old_block_id)
        entity_id = entity_id_map.get(old_entity_id, old_entity_id)
        features = m.get("features")
        cur.execute(
            "INSERT INTO mentions (id, block_id, entity_id, language, surface_form, features) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                block_id,
                entity_id,
                m.get("language", "en"),
                m.get("surface_form"),
                json.dumps(features) if features else None,
            ),
        )
        counts["mentions"] += 1

    # --- Alignments ---
    for a in work_data.get("alignments", []):
        old_src = a.get("source_block_id")
        old_tgt = a.get("target_block_id")
        src_id = block_id_map.get(old_src, old_src)
        tgt_id = block_id_map.get(old_tgt, old_tgt)
        cur.execute(
            "INSERT INTO block_alignments (id, source_block_id, target_block_id, alignment_type) "
            "VALUES (%s, %s, %s, %s)",
            (str(uuid.uuid4()), src_id, tgt_id, a.get("alignment_type", "translation")),
        )
        counts["alignments"] += 1

    # --- Reviews ---
    for r in work_data.get("reviews", []):
        cur.execute(
            "INSERT INTO reviews (id, work_id, description, severity, scope, issue_type) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                work_id,
                r.get("description"),
                r.get("severity", "medium"),
                r.get("scope"),
                r.get("issue_type"),
            ),
        )
        counts["reviews"] += 1

    conn.commit()
    return counts


# =========================================================================
# CLI command registration
# =========================================================================


def register_export(app: typer.Typer) -> None:
    """Register export subcommands onto the given Typer group."""

    @app.command("json")
    def export_json(
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    ) -> None:
        """Export the entire work as JSON."""
        try:
            with open_work_db() as db:
                data = export_work_json(db.conn)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        text = json.dumps(data, indent=2, ensure_ascii=False)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            print(f"Exported to {output}")
        else:
            print(text)

    @app.command("markdown")
    def export_markdown(
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    ) -> None:
        """Export the work as Markdown."""
        try:
            with open_work_db() as db:
                text = export_work_markdown(db.conn)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

        if output:
            Path(output).write_text(text, encoding="utf-8")
            print(f"Exported to {output}")
        else:
            print(text)


def register_import(app: typer.Typer) -> None:
    """Register import subcommands onto the given Typer group."""

    @app.command("json")
    def import_json(
        file: str = typer.Argument(help="Path to JSON file"),
    ) -> None:
        """Import a work from a JSON file."""
        path = Path(file)
        if not path.exists():
            print(f"File not found: {file}")
            sys.exit(1)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            sys.exit(1)

        try:
            with open_work_db() as db:
                counts = import_work_json(db.conn, data)
        except (RuntimeError, ValueError) as e:
            print(str(e))
            sys.exit(1)

        parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        summary = ", ".join(parts) if parts else "nothing"
        print(f"Imported: {summary}")
