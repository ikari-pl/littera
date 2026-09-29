"""Convert a folder of Markdown chapter files into a Littera import JSON.

    python scripts/markdown_book_to_littera.py CHAPTER_DIR OUT.json [--title T]

Then, inside an initialised work:

    littera import json OUT.json

Mapping (one Work, the one you import into):

- each ``*.md`` file            -> Document; ``# Chapter N: Title`` gives the
                                   title ("Title") and the order (N)
- a date/subtitle line straight
  after the chapter heading
  (``*...*``, ``**...**``, ``## ...``) -> title of the first Section
- ``## ...`` later in the chapter -> starts a new Section with that title
- ``---`` / ``***`` / ``* * *``   -> starts a new, untitled Section
- each blank-line-separated
  paragraph                      -> ``paragraph`` Block, text kept verbatim
                                   (inline Markdown included)

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

Nothing is dropped silently. The script fails if the words it wrote differ
from the words in the source, ignoring only the ``Chapter N:`` prefixes,
heading markers and scene-break lines it consumed.
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
SUBHEADING = re.compile(r"^#{2,6}\s+(.+?)\s*$")
SCENE_BREAK = re.compile(r"^\s*(?:-{3,}|\*{3,}|(?:\*\s*){3,}|_{3,})\s*$")
EMPHASISED_LINE = re.compile(r"^(\*{1,2}|_{1,2})(?!\s)(.+?)(?<!\s)\1$")
FILE_NUMBER = re.compile(r"(\d+)")


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


def convert_chapter(path: Path) -> tuple[int | None, dict]:
    """Return (chapter number or None, document dict) for one file."""
    lines = path.read_text(encoding="utf-8").splitlines()

    number, title = None, path.stem
    body_start = 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = CHAPTER_HEADING.match(line)
        if m and not line.startswith("##"):
            number = int(m.group(1)) if m.group(1) else None
            title = m.group(2)
            body_start = i + 1
        break

    sections: list[dict] = []
    pending_title: str | None = None
    chunk: list[str] = []
    at_chapter_start = True

    def flush() -> None:
        nonlocal pending_title, chunk
        paras = _paragraphs(chunk)
        chunk = []
        if not paras and pending_title is None:
            return
        sections.append(
            {
                "title": pending_title,
                "blocks": [
                    {"block_type": "paragraph", "language": "en", "source_text": p}
                    for p in paras
                ],
            }
        )
        pending_title = None

    for line in lines[body_start:]:
        if at_chapter_start and not line.strip():
            continue
        if at_chapter_start:
            at_chapter_start = False
            m = EMPHASISED_LINE.match(line.strip())
            if m:
                pending_title = m.group(2).strip()
                continue
        sub = SUBHEADING.match(line)
        if sub:
            flush()
            pending_title = sub.group(1)
            continue
        if SCENE_BREAK.match(line):
            # A break right after a subtitle separates the subtitle from its
            # scene; it does not end an (empty) section.
            if _paragraphs(chunk) or pending_title is None:
                flush()
            continue
        chunk.append(line)
    flush()

    # A section holding only a title (e.g. "## Date" followed by a break)
    # gives that title to the scene after it.
    merged: list[dict] = []
    for sec in sections:
        if merged and not merged[-1]["blocks"] and merged[-1]["title"] and sec["title"] is None:
            sec["title"] = merged.pop()["title"]
        merged.append(sec)

    return number, {"title": title, "sections": merged}


def _words(text: str) -> list[str]:
    return text.split()


def _source_words(path: Path) -> list[str]:
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if SCENE_BREAK.match(line):
            continue
        m = CHAPTER_HEADING.match(line)
        if m and not line.startswith("##"):
            words += _words(m.group(2))
            continue
        sub = SUBHEADING.match(line)
        if sub:
            words += _words(sub.group(1))
            continue
        words += _words(line)
    return words


def _written_words(doc: dict) -> list[str]:
    words = _words(doc["title"])
    for sec in doc["sections"]:
        if sec["title"]:
            words += _words(sec["title"])
        for blk in sec["blocks"]:
            words += _words(blk["source_text"])
    return words


def _strip_emphasis(words: list[str]) -> list[str]:
    # Section titles lose the *...* that marked them in the source.
    return [w.strip("*_") for w in words]


def convert(chapter_dir: Path, work_title: str) -> dict:
    files = sorted(chapter_dir.glob("*.md"))
    if not files:
        raise SystemExit(f"no .md files in {chapter_dir}")

    chapters = []
    for path in files:
        number, doc = convert_chapter(path)
        if number is None:
            m = FILE_NUMBER.search(path.stem)
            number = int(m.group(1)) if m else None
        src = _strip_emphasis(_source_words(path))
        out = _strip_emphasis(_written_words(doc))
        if src != out:
            raise SystemExit(f"{path.name}: converted text does not match the source")
        chapters.append((number if number is not None else 10**9, path.name, doc))

    chapters.sort(key=lambda c: (c[0], c[1]))
    documents = []
    for idx, (_, _, doc) in enumerate(chapters, 1):
        doc["order_index"] = idx
        for s_idx, sec in enumerate(doc["sections"], 1):
            sec["order_index"] = s_idx
            for b_idx, blk in enumerate(sec["blocks"], 1):
                blk["order_index"] = b_idx
        documents.append(doc)

    return {"work": {"title": work_title, "documents": documents}}


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
    parser.add_argument("--entities", type=Path, default=None, help="author's entity manifest (YAML)")
    args = parser.parse_args()

    data = convert(args.chapter_dir, args.title or args.chapter_dir.name)
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
