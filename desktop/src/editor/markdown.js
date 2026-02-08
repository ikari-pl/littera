/**
 * markdown.js — Markdown ↔ ProseMirror conversion with Littera mention support.
 *
 * Exports:
 *   litteraParser     — MarkdownParser with custom mention inline rule
 *   litteraSerializer — MarkdownSerializer that round-trips mentions
 *   blocksToDoc       — API block array → ProseMirror doc
 *   blockNodeToMarkdown — Single block node → Markdown string
 */

import { MarkdownParser, MarkdownSerializer } from "prosemirror-markdown";
import markdownit from "markdown-it";
import { Schema } from "prosemirror-model";
import { schema } from "./schema.js";

// ---------------------------------------------------------------------------
// Flat parsing schema — doc → block+ (no littera_block wrapper)
//
// MarkdownParser can't auto-wrap content into intermediate nodes like
// littera_block. If we parse with the real schema (doc → littera_block+),
// paragraphs fail to match and content is silently dropped. So we parse
// with this flat schema, then manually wrap results in littera_block nodes.
// ---------------------------------------------------------------------------

const parseSchema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: schema.spec.nodes.get("paragraph"),
    heading: schema.spec.nodes.get("heading"),
    blockquote: schema.spec.nodes.get("blockquote"),
    code_block: schema.spec.nodes.get("code_block"),
    horizontal_rule: schema.spec.nodes.get("horizontal_rule"),
    text: schema.spec.nodes.get("text"),
    mention: schema.spec.nodes.get("mention"),
  },
  marks: {
    strong: schema.spec.marks.get("strong"),
    em: schema.spec.marks.get("em"),
    code: schema.spec.marks.get("code"),
    link: schema.spec.marks.get("link"),
  },
});

// ---------------------------------------------------------------------------
// Custom markdown-it rule for {@Label|entity:uuid}
// ---------------------------------------------------------------------------

function mentionPlugin(md) {
  md.inline.ruler.before("emphasis", "littera_mention", (state, silent) => {
    const start = state.pos;
    const src = state.src;

    if (src.charCodeAt(start) !== 0x7b /* { */) return false;
    if (src.charCodeAt(start + 1) !== 0x40 /* @ */) return false;

    // Find closing }
    const end = src.indexOf("}", start + 2);
    if (end === -1) return false;

    const inner = src.slice(start + 2, end); // "Label|entity:uuid"
    const pipeIdx = inner.indexOf("|entity:");
    if (pipeIdx === -1) return false;

    const label = inner.slice(0, pipeIdx);
    const entityId = inner.slice(pipeIdx + 8); // skip "|entity:"

    if (silent) return true;

    const token = state.push("mention", "", 0);
    token.attrs = { id: entityId, label };
    state.pos = end + 1;
    return true;
  });
}

const md = markdownit("commonmark", { html: false }).use(mentionPlugin);

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

export const litteraParser = new MarkdownParser(parseSchema, md, {
  blockquote: { block: "blockquote" },
  paragraph: { block: "paragraph" },
  heading: {
    block: "heading",
    getAttrs(tok) {
      return { level: +tok.tag.slice(1) };
    },
  },
  code_block: { block: "code_block" },
  fence: { block: "code_block" },
  hr: { node: "horizontal_rule" },
  bullet_list: { block: "paragraph" },
  ordered_list: { block: "paragraph" },
  list_item: { block: "paragraph" },
  em: { mark: "em" },
  strong: { mark: "strong" },
  code_inline: { mark: "code" },
  link: {
    mark: "link",
    getAttrs(tok) {
      return {
        href: tok.attrGet("href"),
        title: tok.attrGet("title") || null,
      };
    },
  },
  mention: {
    node: "mention",
    getAttrs(tok) {
      return tok.attrs;
    },
  },
});

// ---------------------------------------------------------------------------
// Serializer
// ---------------------------------------------------------------------------

export const litteraSerializer = new MarkdownSerializer(
  {
    // littera_block: just serialize children, add blank line between blocks
    littera_block(state, node) {
      state.renderContent(node);
    },
    blockquote(state, node) {
      state.wrapBlock("> ", null, node, () => state.renderContent(node));
    },
    paragraph(state, node) {
      state.renderInline(node);
      state.closeBlock(node);
    },
    heading(state, node) {
      state.write("#".repeat(node.attrs.level) + " ");
      state.renderInline(node);
      state.closeBlock(node);
    },
    code_block(state, node) {
      state.write("```\n");
      state.text(node.textContent, false);
      state.write("\n```");
      state.closeBlock(node);
    },
    horizontal_rule(state, node) {
      state.write("---");
      state.closeBlock(node);
    },
    text(state, node) {
      state.text(node.text);
    },
    mention(state, node) {
      state.write(`{@${node.attrs.label}|entity:${node.attrs.id}}`);
    },
  },
  {
    strong: {
      open: "**",
      close: "**",
      mixable: true,
      expelEnclosingWhitespace: true,
    },
    em: {
      open: "*",
      close: "*",
      mixable: true,
      expelEnclosingWhitespace: true,
    },
    code: {
      open: "`",
      close: "`",
      escape: false,
    },
    link: {
      open(_state, mark) {
        return "[";
      },
      close(_state, mark) {
        const title = mark.attrs.title ? ` "${mark.attrs.title}"` : "";
        return `](${mark.attrs.href}${title})`;
      },
    },
  }
);

// ---------------------------------------------------------------------------
// Convert parseSchema nodes → real schema nodes
// ---------------------------------------------------------------------------

function convertNode(node) {
  const realType = schema.nodes[node.type.name];
  if (!realType) return node; // shouldn't happen

  if (node.isText) {
    // Re-create text with marks mapped to real schema
    const marks = node.marks.map(
      (m) => schema.marks[m.type.name].create(m.attrs)
    );
    return schema.text(node.text, marks);
  }

  // Recurse into children
  const children = [];
  node.content.forEach((child) => children.push(convertNode(child)));

  return realType.create(node.attrs, children);
}

// ---------------------------------------------------------------------------
// blocksToDoc — API block array → ProseMirror doc
// ---------------------------------------------------------------------------

export function blocksToDoc(blocks) {
  const blockNodes = blocks.map((block) => {
    // Parse with the flat schema (doc → block+), then re-create nodes
    // under the real schema and wrap in a littera_block.
    const parsed = litteraParser.parse(block.source_text || "");

    // Convert parseSchema nodes → real schema nodes
    let children = [];
    parsed.content.forEach((child) => {
      children.push(convertNode(child));
    });

    if (children.length === 0) {
      children = [schema.nodes.paragraph.create()];
    }

    return schema.nodes.littera_block.create(
      {
        id: block.id,
        block_type: block.block_type || "prose",
        language: block.language || "en",
      },
      children
    );
  });

  // If no blocks at all, create one empty block
  if (blockNodes.length === 0) {
    blockNodes.push(
      schema.nodes.littera_block.create(
        { id: crypto.randomUUID(), block_type: "prose", language: "en" },
        [schema.nodes.paragraph.create()]
      )
    );
  }

  return schema.nodes.doc.create(null, blockNodes);
}

// ---------------------------------------------------------------------------
// blockNodeToMarkdown — Single littera_block node → Markdown string
// ---------------------------------------------------------------------------

export function blockNodeToMarkdown(blockNode) {
  // Create a temporary doc containing just this block's inner content
  const tempDoc = schema.nodes.doc.create(null, [blockNode]);
  return litteraSerializer.serialize(tempDoc).trim();
}
