"""Littera desktop sidecar — lightweight HTTP API for the WebView frontend.

Starts embedded Postgres via the existing open_work_db() lifecycle,
then serves a minimal JSON API until stdin closes (signaling the
Tauri shell has exited).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from littera.db.workdb import open_work_db, WorkDb


# =============================================================================
# Route table — (pattern, method, handler_name)
# =============================================================================

ROUTES = [
    (re.compile(r"^/api/documents$"), "GET", "_get_documents"),
    (re.compile(r"^/api/documents$"), "POST", "_post_document"),
    (re.compile(r"^/api/documents/([^/]+)/order$"), "PUT", "_put_document_order"),
    (re.compile(r"^/api/documents/([^/]+)$"), "PUT", "_put_document"),
    (re.compile(r"^/api/documents/([^/]+)$"), "DELETE", "_delete_document"),
    (re.compile(r"^/api/documents/([^/]+)/sections$"), "GET", "_get_sections"),
    (re.compile(r"^/api/sections$"), "POST", "_post_section"),
    (re.compile(r"^/api/sections/([^/]+)/order$"), "PUT", "_put_section_order"),
    (re.compile(r"^/api/sections/([^/]+)$"), "PUT", "_put_section"),
    (re.compile(r"^/api/sections/([^/]+)$"), "DELETE", "_delete_section"),
    (re.compile(r"^/api/sections/([^/]+)/blocks$"), "GET", "_get_blocks"),
    (re.compile(r"^/api/blocks/batch$"), "PUT", "_put_blocks_batch"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "GET", "_get_block"),
    (re.compile(r"^/api/blocks/([^/]+)/language$"), "PUT", "_put_block_language"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "PUT", "_put_block"),
    (re.compile(r"^/api/blocks/([^/]+)$"), "DELETE", "_delete_block"),
    (re.compile(r"^/api/blocks$"), "POST", "_post_block"),
    (re.compile(r"^/api/entities$"), "GET", "_get_entities"),
    (re.compile(r"^/api/entities$"), "POST", "_post_entity"),
    (re.compile(r"^/api/entities/([^/]+)/properties/([^/]+)$"), "DELETE", "_delete_entity_property"),
    (re.compile(r"^/api/entities/([^/]+)/properties$"), "GET", "_get_entity_properties"),
    (re.compile(r"^/api/entities/([^/]+)/properties$"), "PUT", "_put_entity_properties"),
    (re.compile(r"^/api/entities/([^/]+)$"), "GET", "_get_entity"),
    (re.compile(r"^/api/entities/([^/]+)$"), "DELETE", "_delete_entity"),
    (re.compile(r"^/api/entities/([^/]+)/note$"), "PUT", "_put_entity_note"),
    (re.compile(r"^/api/entities/([^/]+)/labels$"), "POST", "_post_entity_label"),
    (re.compile(r"^/api/labels/([^/]+)$"), "DELETE", "_delete_label"),
    (re.compile(r"^/api/mentions/([^/]+)/surface$"), "PUT", "_put_mention_surface"),
    (re.compile(r"^/api/mentions/([^/]+)$"), "DELETE", "_delete_mention"),
    (re.compile(r"^/api/inflect$"), "POST", "_post_inflect"),
    (re.compile(r"^/api/alignment-gaps$"), "GET", "_get_alignment_gaps"),
    (re.compile(r"^/api/alignments$"), "GET", "_get_alignments"),
    (re.compile(r"^/api/alignments$"), "POST", "_post_alignment"),
    (re.compile(r"^/api/alignments/([^/]+)$"), "DELETE", "_delete_alignment"),
    (re.compile(r"^/api/reviews$"), "GET", "_get_reviews"),
    (re.compile(r"^/api/reviews$"), "POST", "_post_review"),
    (re.compile(r"^/api/reviews/([^/]+)$"), "DELETE", "_delete_review"),
    (re.compile(r"^/api/export/json$"), "GET", "_get_export_json"),
    (re.compile(r"^/api/export/markdown$"), "GET", "_get_export_markdown"),
    (re.compile(r"^/api/import/json$"), "POST", "_post_import_json"),
    (re.compile(r"^/api/status$"), "GET", "_get_status"),
    (re.compile(r"^/health$"), "GET", "_health"),
]


class SidecarHandler(BaseHTTPRequestHandler):
    """Thin HTTP handler — delegates all DB access to the shared WorkDb."""

    work_db: WorkDb  # Set by serve()

    def do_GET(self):
        self._dispatch("GET")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _dispatch(self, method):
        for pattern, route_method, handler_name in ROUTES:
            m = pattern.match(self.path)
            if m and route_method == method:
                handler = getattr(self, handler_name)
                self._json_response(handler(*m.groups()))
                return
        self.send_error(404)

    # -----------------------------------------------------------------
    # Route handlers
    # -----------------------------------------------------------------

    def _get_documents(self):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM documents ORDER BY order_index NULLS LAST, created_at"
            )
            return [{"id": str(r[0]), "title": r[1]} for r in cur.fetchall()]

    def _get_sections(self, document_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM sections WHERE document_id = %s ORDER BY order_index NULLS LAST, created_at",
                (document_id,),
            )
            return [{"id": str(r[0]), "title": r[1]} for r in cur.fetchall()]

    def _get_blocks(self, section_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, block_type, language, source_text FROM blocks WHERE section_id = %s ORDER BY created_at",
                (section_id,),
            )
            return [
                {"id": str(r[0]), "block_type": r[1], "language": r[2], "source_text": r[3]}
                for r in cur.fetchall()
            ]

    def _get_block(self, block_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, language, source_text FROM blocks WHERE id = %s",
                (block_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            return {"id": str(row[0]), "language": row[1], "source_text": row[2]}

    def _get_entities(self):
        with self.work_db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, entity_type, canonical_label FROM entities ORDER BY created_at"
            )
            return [
                {
                    "id": str(r[0]),
                    "entity_type": r[1],
                    "label": r[2] or "(unnamed)",
                }
                for r in cur.fetchall()
            ]

    def _get_entity(self, entity_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_type, canonical_label, properties FROM entities WHERE id = %s",
                (entity_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            entity_type, name, props = row

            # Work-scoped note
            work_id = self.work_db.cfg.get("work", {}).get("id")
            note = None
            if work_id is not None:
                cur.execute(
                    """
                    SELECT metadata->>'note'
                    FROM entity_work_metadata
                    WHERE entity_id = %s AND work_id = %s
                    """,
                    (entity_id, work_id),
                )
                note_row = cur.fetchone()
                note = note_row[0] if note_row else None

            # Labels
            cur.execute(
                """
                SELECT id, language, base_form, aliases
                FROM entity_labels
                WHERE entity_id = %s
                ORDER BY language
                """,
                (entity_id,),
            )
            labels = [
                {"id": str(r[0]), "language": r[1], "base_form": r[2], "aliases": r[3]}
                for r in cur.fetchall()
            ]

            # Mentions
            cur.execute(
                """
                SELECT m.id, m.block_id, d.title, s.title, b.language, b.source_text
                FROM mentions m
                JOIN blocks b ON b.id = m.block_id
                JOIN sections s ON s.id = b.section_id
                JOIN documents d ON d.id = s.document_id
                WHERE m.entity_id = %s
                ORDER BY b.created_at DESC
                """,
                (entity_id,),
            )
            mentions = [
                {
                    "id": str(r[0]),
                    "block_id": str(r[1]),
                    "document": r[2],
                    "section": r[3],
                    "language": r[4],
                    "preview": r[5].replace("\n", " ")[:80],
                }
                for r in cur.fetchall()
            ]

            return {
                "entity_type": entity_type,
                "label": name or "(unnamed)",
                "labels": labels,
                "properties": props or {},
                "mentions": mentions,
                "note": note,
            }

    # -----------------------------------------------------------------
    # Import / Export handlers
    # -----------------------------------------------------------------

    def _get_export_json(self):
        from littera.cli.io import export_work_json

        return export_work_json(self.work_db.conn)

    def _get_export_markdown(self):
        from littera.cli.io import export_work_markdown

        text = export_work_markdown(self.work_db.conn)
        return {"markdown": text}

    def _post_import_json(self):
        from littera.cli.io import import_work_json

        body = self._read_json_body()
        try:
            counts = import_work_json(self.work_db.conn, body)
        except (ValueError, RuntimeError) as e:
            return {"error": str(e)}
        return {"ok": True, "counts": counts}

    def _get_status(self):
        cfg = self.work_db.cfg
        work_title = cfg.get("work", {}).get("title", "Untitled")
        return {"work_title": work_title, "pg_status": "running"}

    def _health(self):
        return {"status": "ok"}

    # -----------------------------------------------------------------
    # Write handlers
    # -----------------------------------------------------------------

    def _put_document(self, document_id: str):
        body = self._read_json_body()
        title = body.get("title")
        if title is None:
            return {"error": "title required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET title = %s WHERE id = %s",
                (title, document_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_section(self, section_id: str):
        body = self._read_json_body()
        title = body.get("title")
        if title is None:
            return {"error": "title required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sections SET title = %s WHERE id = %s",
                (title, section_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_document_order(self, document_id: str):
        body = self._read_json_body()
        position = body.get("position")
        if position is None or not isinstance(position, int):
            return {"error": "position (integer) required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            # Get all sibling documents in current order
            cur.execute(
                "SELECT id FROM documents "
                "WHERE work_id = (SELECT work_id FROM documents WHERE id = %s) "
                "ORDER BY order_index NULLS LAST, created_at",
                (document_id,),
            )
            ids = [str(r[0]) for r in cur.fetchall()]

            if str(document_id) not in ids:
                return {"error": "document not found"}
            if position < 1 or position > len(ids):
                return {"error": f"position must be between 1 and {len(ids)}"}

            ids.remove(str(document_id))
            ids.insert(position - 1, str(document_id))

            for idx, did in enumerate(ids, 1):
                cur.execute(
                    "UPDATE documents SET order_index = %s WHERE id = %s",
                    (idx, did),
                )
        conn.commit()
        return {"ok": True}

    def _put_section_order(self, section_id: str):
        body = self._read_json_body()
        position = body.get("position")
        if position is None or not isinstance(position, int):
            return {"error": "position (integer) required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            # Get all sibling sections in current order
            cur.execute(
                "SELECT id FROM sections "
                "WHERE document_id = (SELECT document_id FROM sections WHERE id = %s) "
                "ORDER BY order_index NULLS LAST, created_at",
                (section_id,),
            )
            ids = [str(r[0]) for r in cur.fetchall()]

            if str(section_id) not in ids:
                return {"error": "section not found"}
            if position < 1 or position > len(ids):
                return {"error": f"position must be between 1 and {len(ids)}"}

            ids.remove(str(section_id))
            ids.insert(position - 1, str(section_id))

            for idx, sid in enumerate(ids, 1):
                cur.execute(
                    "UPDATE sections SET order_index = %s WHERE id = %s",
                    (idx, sid),
                )
        conn.commit()
        return {"ok": True}

    def _put_block(self, block_id: str):
        body = self._read_json_body()
        source_text = body.get("source_text")
        if source_text is None:
            return {"error": "source_text required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE blocks SET source_text = %s WHERE id = %s",
                (source_text, block_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_block_language(self, block_id: str):
        body = self._read_json_body()
        language = body.get("language")
        if language is None:
            return {"error": "language required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE blocks SET language = %s WHERE id = %s",
                (language, block_id),
            )
        conn.commit()
        return {"ok": True}

    def _put_blocks_batch(self):
        body = self._read_json_body()
        blocks = body.get("blocks", [])
        conn = self.work_db.conn
        with conn.cursor() as cur:
            for b in blocks:
                cur.execute(
                    "UPDATE blocks SET source_text = %s WHERE id = %s",
                    (b["source_text"], b["id"]),
                )
        conn.commit()
        return {"ok": True, "count": len(blocks)}

    def _post_block(self):
        body = self._read_json_body()
        block_id = body.get("id")
        section_id = body.get("section_id")
        block_type = body.get("block_type", "prose")
        language = body.get("language", "en")
        source_text = body.get("source_text", "")
        if not section_id:
            return {"error": "section_id required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            if block_id:
                cur.execute(
                    "INSERT INTO blocks (id, section_id, block_type, language, source_text) VALUES (%s, %s, %s, %s, %s)",
                    (block_id, section_id, block_type, language, source_text),
                )
            else:
                cur.execute(
                    "INSERT INTO blocks (section_id, block_type, language, source_text) VALUES (%s, %s, %s, %s) RETURNING id",
                    (section_id, block_type, language, source_text),
                )
                block_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": str(block_id)}

    def _delete_block(self, block_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM blocks WHERE id = %s", (block_id,))
        conn.commit()
        return {"ok": True}

    def _post_document(self):
        body = self._read_json_body()
        title = body.get("title", "Untitled")
        work_id = self.work_db.cfg.get("work", {}).get("id")
        if work_id is None:
            return {"error": "no work_id in config"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (work_id, title) VALUES (%s, %s) RETURNING id",
                (work_id, title),
            )
            doc_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": doc_id}

    def _delete_document(self, document_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        conn.commit()
        return {"ok": True}

    def _post_section(self):
        body = self._read_json_body()
        document_id = body.get("document_id")
        title = body.get("title", "Untitled")
        if not document_id:
            return {"error": "document_id required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sections (document_id, title, order_index) "
                "VALUES (%s, %s, COALESCE((SELECT MAX(order_index)+1 FROM sections WHERE document_id = %s), 1)) "
                "RETURNING id",
                (document_id, title, document_id),
            )
            section_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": section_id}

    def _delete_section(self, section_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sections WHERE id = %s", (section_id,))
        conn.commit()
        return {"ok": True}

    def _post_entity(self):
        body = self._read_json_body()
        entity_type = body.get("entity_type", "concept")
        label = body.get("label", "")
        if not label:
            return {"error": "label required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO entities (entity_type, canonical_label) VALUES (%s, %s) RETURNING id",
                (entity_type, label),
            )
            entity_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": entity_id}

    def _delete_entity(self, entity_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
        conn.commit()
        return {"ok": True}

    def _delete_mention(self, mention_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mentions WHERE id = %s", (mention_id,))
        conn.commit()
        return {"ok": True}

    def _post_inflect(self):
        from littera.linguistics.dispatch import surface_form as dispatch_surface_form

        body = self._read_json_body()
        language = body.get("language", "en")
        base_form = body.get("base_form", "")
        features = body.get("features")
        properties = body.get("properties")
        if not base_form:
            return {"error": "base_form required"}
        result = dispatch_surface_form(language, base_form, features, properties)
        return {"result": result}

    def _put_mention_surface(self, mention_id: str):
        from littera.linguistics.dispatch import surface_form as dispatch_surface_form

        body = self._read_json_body()
        features = body.get("features", {})
        conn = self.work_db.conn
        with conn.cursor() as cur:
            # Look up mention → entity_id + language
            cur.execute(
                "SELECT entity_id, language FROM mentions WHERE id = %s",
                (mention_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "mention not found"}
            entity_id, language = row

            # Look up base_form from entity_labels for this language
            cur.execute(
                "SELECT base_form FROM entity_labels WHERE entity_id = %s AND language = %s",
                (entity_id, language),
            )
            row = cur.fetchone()
            if row:
                base_form = row[0]
            else:
                # Fall back to canonical_label
                cur.execute(
                    "SELECT canonical_label FROM entities WHERE id = %s",
                    (entity_id,),
                )
                row = cur.fetchone()
                base_form = row[0] if row else "?"

            # Fetch entity properties
            cur.execute(
                "SELECT properties FROM entities WHERE id = %s",
                (entity_id,),
            )
            row = cur.fetchone()
            properties = row[0] if row and row[0] else None

            result = dispatch_surface_form(language, base_form, features or None, properties)

            cur.execute(
                "UPDATE mentions SET surface_form = %s, features = %s WHERE id = %s",
                (result, json.dumps(features) if features else None, mention_id),
            )
        conn.commit()
        return {"ok": True, "surface_form": result}

    def _put_entity_note(self, entity_id: str):
        body = self._read_json_body()
        note = body.get("note", "")
        work_id = self.work_db.cfg.get("work", {}).get("id")
        if work_id is None:
            return {"error": "no work_id in config"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO entity_work_metadata (entity_id, work_id, metadata)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (entity_id, work_id)
                DO UPDATE SET metadata = EXCLUDED.metadata
                """,
                (entity_id, work_id, json.dumps({"note": note})),
            )
        conn.commit()
        return {"ok": True}

    def _post_entity_label(self, entity_id: str):
        body = self._read_json_body()
        language = body.get("language", "en")
        base_form = body.get("base_form", "")
        aliases = body.get("aliases")
        if not base_form:
            return {"error": "base_form required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO entity_labels (entity_id, language, base_form, aliases) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (entity_id, language, base_form, json.dumps(aliases) if aliases else None),
            )
            label_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": label_id}

    def _delete_label(self, label_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entity_labels WHERE id = %s", (label_id,))
        conn.commit()
        return {"ok": True}

    def _get_entity_properties(self, entity_id: str):
        with self.work_db.conn.cursor() as cur:
            cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            return row[0] or {}

    def _put_entity_properties(self, entity_id: str):
        body = self._read_json_body()
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            props = row[0] or {}
            props.update(body)
            cur.execute("UPDATE entities SET properties = %s WHERE id = %s",
                        (json.dumps(props), entity_id))
        conn.commit()
        return {"ok": True}

    def _delete_entity_property(self, entity_id: str, key: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("SELECT properties FROM entities WHERE id = %s", (entity_id,))
            row = cur.fetchone()
            if row is None:
                return {"error": "not found"}
            props = row[0] or {}
            props.pop(key, None)
            cur.execute("UPDATE entities SET properties = %s WHERE id = %s",
                        (json.dumps(props) if props else None, entity_id))
        conn.commit()
        return {"ok": True}

    # -----------------------------------------------------------------
    # Alignment handlers
    # -----------------------------------------------------------------

    def _get_alignment_gaps(self):
        """Detect entities missing labels in aligned languages."""
        gaps = []
        checked = 0

        with self.work_db.conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.source_block_id, a.target_block_id,
                       sb.language, tb.language
                FROM block_alignments a
                JOIN blocks sb ON sb.id = a.source_block_id
                JOIN blocks tb ON tb.id = a.target_block_id
                ORDER BY a.created_at
            """)
            alignments = cur.fetchall()

            seen = set()

            for _, src_block_id, tgt_block_id, src_lang, tgt_lang in alignments:
                checked += 1
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
                        key = (str(eid), to_lang)
                        if key in seen:
                            continue
                        cur.execute(
                            "SELECT 1 FROM entity_labels WHERE entity_id = %s AND language = %s",
                            (eid, to_lang),
                        )
                        if not cur.fetchone():
                            seen.add(key)
                            gaps.append({
                                "entity_type": etype,
                                "canonical_label": canonical or "(unnamed)",
                                "missing_language": to_lang,
                                "has_language": from_lang,
                            })

        return {"gaps": gaps, "total": len(gaps), "checked": checked}

    def _get_alignments(self):
        """List all alignments with block details."""
        with self.work_db.conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.alignment_type,
                       sb.id, sb.language, sb.source_text,
                       tb.id, tb.language, tb.source_text
                FROM block_alignments a
                JOIN blocks sb ON sb.id = a.source_block_id
                JOIN blocks tb ON tb.id = a.target_block_id
                ORDER BY a.created_at
            """)
            return [
                {
                    "id": str(r[0]),
                    "alignment_type": r[1],
                    "source": {
                        "id": str(r[2]),
                        "language": r[3],
                        "preview": (r[4] or "").replace("\n", " ")[:80],
                    },
                    "target": {
                        "id": str(r[5]),
                        "language": r[6],
                        "preview": (r[7] or "").replace("\n", " ")[:80],
                    },
                }
                for r in cur.fetchall()
            ]

    def _post_alignment(self):
        """Create an alignment between two blocks."""
        body = self._read_json_body()
        source_block_id = body.get("source_block_id")
        target_block_id = body.get("target_block_id")
        alignment_type = body.get("alignment_type", "translation")
        if not source_block_id or not target_block_id:
            return {"error": "source_block_id and target_block_id required"}
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO block_alignments (source_block_id, target_block_id, alignment_type) "
                "VALUES (%s, %s, %s) RETURNING id",
                (source_block_id, target_block_id, alignment_type),
            )
            alignment_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": alignment_id}

    def _delete_alignment(self, alignment_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM block_alignments WHERE id = %s", (alignment_id,))
        conn.commit()
        return {"ok": True}

    # -----------------------------------------------------------------
    # Review handlers
    # -----------------------------------------------------------------

    def _get_reviews(self):
        """List all reviews for the current work."""
        work_id = self.work_db.cfg.get("work", {}).get("id")
        with self.work_db.conn.cursor() as cur:
            if work_id:
                cur.execute("""
                    SELECT id, scope, scope_id, issue_type, description, severity, created_at
                    FROM reviews
                    WHERE work_id = %s
                    ORDER BY created_at DESC
                """, (work_id,))
            else:
                cur.execute("""
                    SELECT id, scope, scope_id, issue_type, description, severity, created_at
                    FROM reviews
                    ORDER BY created_at DESC
                """)
            return [
                {
                    "id": str(r[0]),
                    "scope": r[1],
                    "scope_id": str(r[2]) if r[2] else None,
                    "issue_type": r[3],
                    "description": r[4],
                    "severity": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in cur.fetchall()
            ]

    def _post_review(self):
        """Create a review."""
        body = self._read_json_body()
        description = body.get("description")
        if not description:
            return {"error": "description required"}
        work_id = self.work_db.cfg.get("work", {}).get("id")
        scope = body.get("scope")
        scope_id = body.get("scope_id")
        issue_type = body.get("issue_type")
        severity = body.get("severity", "medium")
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reviews (work_id, scope, scope_id, issue_type, description, severity) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (work_id, scope, scope_id, issue_type, description, severity),
            )
            review_id = str(cur.fetchone()[0])
        conn.commit()
        return {"ok": True, "id": review_id}

    def _delete_review(self, review_id: str):
        conn = self.work_db.conn
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
        conn.commit()
        return {"ok": True}

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    # -----------------------------------------------------------------
    # Response helpers
    # -----------------------------------------------------------------

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress per-request logs


def _wait_for_stdin_close():
    """Block until stdin is closed (Tauri process exited)."""
    try:
        while True:
            # select() on stdin — returns when readable (EOF) or error
            readable, _, _ = select.select([sys.stdin], [], [])
            if readable:
                data = sys.stdin.buffer.read(1)
                if not data:  # EOF
                    break
    except (OSError, ValueError):
        pass


def serve(wdb: WorkDb, port: int = 0):
    """Start the HTTP server, print readiness signal, block until stdin closes."""

    SidecarHandler.work_db = wdb
    server = HTTPServer(("127.0.0.1", port), SidecarHandler)
    actual_port = server.server_address[1]

    # Start serving in a background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Signal readiness to Tauri (stdout line protocol)
    print(f"LITTERA_SIDECAR_READY:{actual_port}", flush=True)

    # Block until stdin closes (Tauri exited)
    _wait_for_stdin_close()

    server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Littera desktop sidecar")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Path to Littera work directory (default: cwd)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind (default: OS-assigned)",
    )
    args = parser.parse_args()

    # The sidecar owns Postgres for its full lifetime — disable the lease
    # watcher so PG isn't killed after 30s. PG stops when this process exits.
    os.environ["LITTERA_PG_LEASE_SECONDS"] = "0"

    with open_work_db(args.work_dir) as wdb:
        serve(wdb, port=args.port)


if __name__ == "__main__":
    main()
