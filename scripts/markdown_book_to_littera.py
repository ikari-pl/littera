"""Convert a folder of Markdown chapter files into a Littera import JSON.

    python scripts/markdown_book_to_littera.py CHAPTER_DIR OUT.json \\
        [--document "Book One"] [--entities FILE.yaml]

Then, inside an initialised work:

    littera import json OUT.json

Mapping, following MANIFESTO.md (Work -> Document -> Section -> Block):

- the folder                     -> one Document (``--document``): a book is
                                    one coherent piece, not one per file
- each ``*.md`` chapter file     -> Section; ``# Chapter N: Title`` gives the
                                    title ("Title") and the order (N)
- each scene (text between
  ``---`` / ``***`` / ``* * *``) -> Block holding all of its paragraphs
                                    verbatim, inline Markdown included

Blocks are units of meaning, not paragraphs (INVARIANTS.md lists "treating
paragraphs, pages, or files as atomic units" as a violation). A scene is what
a mention or a review points at.

Date lines and mid-chapter date headings stay where the author put them, at
the top of the scene they introduce, so a compiled manuscript prints them.
The chapter number is not kept in the title: order carries it, and a stored
number would go stale the first time a chapter moves.

With ``--entities FILE.yaml`` the semantic layer is converted too. The file is
the author's intent (Littera never creates entities it inferred on its own):
each listed entity is created with its labels, aliases, properties and a note
for this work, and a mention is bound in every block where one of its labels
or aliases occurs. The prose is not rewritten; mentions are rows, as the CLI
makes them. An entity with a ``review`` rule also gets a block-scoped review
on each block that mentions it. See the header of the example manifest for
the format.

Nothing is dropped silently. The script fails unless the blocks and titles
hold exactly the words of the source, minus the ``Chapter N:`` prefixes and
the scene-break lines it turned into structure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import yaml

CHAPTER_HEADING = re.compile(r"^#\s+(?:Chapter\s+(\d+)\s*[:.\-–—]\s*)?(.+?)\s*$")
SCENE_BREAK = re.compile(r"^\s*(?:-{3,}|\*{3,}|(?:\*\s*){3,}|_{3,})\s*$")
HEADING_LINE = re.compile(r"^#{2,6}\s+\S")
EMPHASISED_LINE = re.compile(r"^(\*{1,2}|_{1,2})(?!\s)(.+?)(?<!\s)\1$")
FILE_NUMBER = re.compile(r"(\d+)")


def _is_chapter_heading(line: str) -> bool:
    return line.startswith("# ") and CHAPTER_HEADING.match(line) is not None


def _paragraphs(lines: list[str]) -> list[str]:
    paras, current = [], []
    for line in lines:
        if line.strip():
            current.append(line.rstrip())
        elif current:
            paras.append("\n".join(current))
            current = []
    if current:
        paras.append("\n".join(current))
    return paras


def _is_dateline(paragraph: str) -> bool:
    """A lone heading or emphasised line: it introduces a scene, it is not one."""
    line = paragraph.strip()
    return "\n" not in line and (
        HEADING_LINE.match(line) is not None or EMPHASISED_LINE.match(line) is not None
    )


def convert_chapter(path: Path) -> tuple[int | None, dict]:
    """Return (chapter number or None, section dict) for one chapter file."""
    lines = path.read_text(encoding="utf-8").splitlines()

    number, title, body_start = None, path.stem, 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if _is_chapter_heading(line):
            m = CHAPTER_HEADING.match(line)
            number = int(m.group(1)) if m.group(1) else None
            title = m.group(2)
            body_start = i + 1
        break

    scenes: list[list[str]] = [[]]
    for line in lines[body_start:]:
        if SCENE_BREAK.match(line):
            scenes.append([])
        else:
            scenes[-1].append(line)

    blocks: list[list[str]] = []
    carried: list[str] = []  # date lines waiting for the scene they introduce
    for scene in scenes:
        paras = _paragraphs(scene)
        if not paras:
            continue
        if all(_is_dateline(p) for p in paras):
            carried += paras
            continue
        blocks.append(carried + paras)
        carried = []
    if carried:  # a trailing date with no scene after it is still text
        blocks.append(carried)

    return number, {
        "title": title,
        "blocks": [
            {"block_type": "paragraph", "language": "en", "source_text": "\n\n".join(paras)}
            for paras in blocks
        ],
    }


def _source_words(path: Path) -> list[str]:
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if SCENE_BREAK.match(line):
            continue
        if _is_chapter_heading(line):
            words += CHAPTER_HEADING.match(line).group(2).split()
            continue
        words += line.split()
    return words


def _written_words(section: dict) -> list[str]:
    words = section["title"].split()
    for blk in section["blocks"]:
        words += blk["source_text"].split()
    return words


def convert(chapter_dir: Path, work_title: str, document_title: str) -> dict:
    files = sorted(chapter_dir.glob("*.md"))
    if not files:
        raise SystemExit(f"no .md files in {chapter_dir}")

    chapters = []
    for path in files:
        number, section = convert_chapter(path)
        if number is None:
            m = FILE_NUMBER.search(path.stem)
            number = int(m.group(1)) if m else None
        if _source_words(path) != _written_words(section):
            raise SystemExit(f"{path.name}: converted text does not match the source")
        chapters.append((number if number is not None else 10**9, path.name, section))

    chapters.sort(key=lambda c: (c[0], c[1]))
    sections = []
    for s_idx, (_, _, section) in enumerate(chapters, 1):
        section["order_index"] = s_idx
        for b_idx, blk in enumerate(section["blocks"], 1):
            blk["order_index"] = b_idx
        sections.append(section)

    document = {"title": document_title, "order_index": 1, "sections": sections}
    return {"work": {"title": work_title, "documents": [document]}}


# =============================================================================
# Semantic layer: entities, labels, notes, mentions, reviews
# =============================================================================

POSSESSIVE = re.compile(r"^[’']s(?!\w)")


def _entity_matcher(entry: dict) -> tuple[re.Pattern, str]:
    """Compile a whole-word pattern for every term naming this entity."""
    terms = [entry["label"], *entry.get("aliases", [])]
    for spec in (entry.get("labels") or {}).values():
        base = spec["base"] if isinstance(spec, dict) else spec
        terms.append(base)
        if isinstance(spec, dict):
            terms += spec.get("aliases", [])
    # Longest first, so "Daði Freyr" wins over "Daði".
    alternation = "|".join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True))
    flags = re.IGNORECASE if entry.get("match") == "any-case" else 0
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)", flags), entry["label"]


def _features(surface: str, base: str, after: str) -> dict | None:
    features = {}
    if surface.lower() != base.lower() and surface.lower() in (base.lower() + "s", base.lower() + "es"):
        features["number"] = "pl"
    if POSSESSIVE.match(after):
        features["case"] = "poss"
    return features or None


def add_semantics(data: dict, manifest: list[dict]) -> None:
    """Add entities, mentions and reviews from an author's manifest."""
    work = data["work"]
    entities, matchers = [], []
    for entry in manifest:
        eid = str(uuid.uuid4())
        labels = [{"language": "en", "base_form": entry["label"]}]
        if entry.get("aliases"):
            labels[0]["aliases"] = entry["aliases"]
        for lang, spec in (entry.get("labels") or {}).items():
            label = {"language": lang, "base_form": spec["base"] if isinstance(spec, dict) else spec}
            if isinstance(spec, dict) and spec.get("aliases"):
                label["aliases"] = spec["aliases"]
            labels.append(label)
        entities.append(
            {
                "id": eid,
                "entity_type": entry["type"],
                "canonical_label": entry["label"],
                "properties": entry.get("properties"),
                "labels": labels,
                "work_metadata": {"note": entry["note"].strip()} if entry.get("note") else None,
            }
        )
        pattern, base = _entity_matcher(entry)
        matchers.append((eid, pattern, base, entry.get("review")))

    mentions, reviews = [], []
    for doc in work["documents"]:
        for sec in doc["sections"]:
            for blk in sec["blocks"]:
                blk.setdefault("id", str(uuid.uuid4()))
                text = blk["source_text"]
                for eid, pattern, base, review in matchers:
                    m = pattern.search(text)
                    if m is None:
                        continue
                    # One mention per entity per block, as the CLI and TUI keep it.
                    mentions.append(
                        {
                            "block_id": blk["id"],
                            "entity_id": eid,
                            "language": blk["language"],
                            "surface_form": m.group(0),
                            "features": _features(m.group(0), base, text[m.end():]),
                        }
                    )
                    if review:
                        reviews.append(
                            {
                                "scope": "block",
                                "scope_id": blk["id"],
                                "issue_type": review.get("issue_type"),
                                "severity": review.get("severity", "medium"),
                                "description": " ".join(review["description"].split()),
                                "metadata": {"source": "entity-review-rule", "entity": base},
                            }
                        )

    work["entities"] = entities
    work["mentions"] = mentions
    work["reviews"] = reviews


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("chapter_dir", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--title", default=None, help="work title (informational)")
    parser.add_argument("--document", default=None, help="document title (default: work title)")
    parser.add_argument("--entities", type=Path, default=None, help="author's entity manifest (YAML)")
    args = parser.parse_args()

    title = args.title or args.chapter_dir.name
    data = convert(args.chapter_dir, title, args.document or title)
    if args.entities:
        add_semantics(data, yaml.safe_load(args.entities.read_text(encoding="utf-8")) or [])
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    work = data["work"]
    docs = work["documents"]
    n_sec = sum(len(d["sections"]) for d in docs)
    n_blk = sum(len(s["blocks"]) for d in docs for s in d["sections"])
    n_words = sum(len(b["source_text"].split()) for d in docs for s in d["sections"] for b in s["blocks"])
    summary = f"{len(docs)} documents, {n_sec} sections, {n_blk} blocks, {n_words} words"
    if args.entities:
        summary += (
            f", {len(work['entities'])} entities, {len(work['mentions'])} mentions,"
            f" {len(work['reviews'])} reviews"
        )
    print(f"{summary} -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
