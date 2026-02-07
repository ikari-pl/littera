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
import { schema } from "./schema.js";

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

export const litteraParser = new MarkdownParser(schema, md, {
  blockquote: { block: "paragraph" }, // flatten blockquotes to paragraphs
  paragraph: { block: "paragraph" },
  heading: {
    block: "heading",
    getAttrs(tok) {
      return { level: +tok.tag.slice(1) };
    },
  },
  code_block: { block: "code_block" },
  fence: { block: "code_block" },
  hr: { node: "paragraph" }, // no HR node, treat as paragraph break
  bullet_list: { block: "paragraph" },
  ordered_list: { block: "paragraph" },
  list_item: { block: "paragraph" },
  hardbreak: { node: "text", getAttrs: () => null },
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
  softbreak: { node: "text", getAttrs: () => null },
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
// blocksToDoc — API block array → ProseMirror doc
// ---------------------------------------------------------------------------

export function blocksToDoc(blocks) {
  const blockNodes = blocks.map((block) => {
    // Parse the block's markdown into a temporary doc
    const parsed = litteraParser.parse(block.source_text || "");

    // Extract the inner content nodes (paragraphs, headings, etc.)
    let children = [];
    parsed.content.forEach((child) => {
      children.push(child);
    });

    // If parsing produced nothing, add an empty paragraph
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
