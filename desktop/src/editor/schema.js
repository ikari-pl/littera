/**
 * schema.js — ProseMirror schema for Littera block editing.
 *
 * Hierarchy: doc → littera_block+ → (paragraph | heading | code_block)+
 *
 * Each littera_block maps to a row in the blocks table and carries
 * {id, block_type, language} as attrs. The `isolating` flag prevents
 * backspace from merging blocks — block boundaries are sacred in Littera.
 */

import { Schema } from "prosemirror-model";

export const schema = new Schema({
  nodes: {
    doc: {
      content: "littera_block+",
    },

    littera_block: {
      content: "block+",
      group: "top",
      isolating: true,
      defining: true,
      attrs: {
        id: { default: null },
        block_type: { default: "prose" },
        language: { default: "en" },
      },
      parseDOM: [
        {
          tag: "section[data-block-id]",
          getAttrs(dom) {
            return {
              id: dom.getAttribute("data-block-id"),
              block_type: dom.getAttribute("data-block-type") || "prose",
              language: dom.getAttribute("data-language") || "en",
            };
          },
        },
      ],
      toDOM(node) {
        return [
          "section",
          {
            class: "littera-block",
            "data-block-id": node.attrs.id,
            "data-block-type": node.attrs.block_type,
            "data-language": node.attrs.language,
          },
          0,
        ];
      },
    },

    paragraph: {
      content: "inline*",
      group: "block",
      parseDOM: [{ tag: "p" }],
      toDOM() {
        return ["p", 0];
      },
    },

    heading: {
      content: "inline*",
      group: "block",
      attrs: { level: { default: 1 } },
      defining: true,
      parseDOM: [
        { tag: "h1", attrs: { level: 1 } },
        { tag: "h2", attrs: { level: 2 } },
        { tag: "h3", attrs: { level: 3 } },
      ],
      toDOM(node) {
        return ["h" + node.attrs.level, 0];
      },
    },

    code_block: {
      content: "text*",
      group: "block",
      code: true,
      defining: true,
      marks: "",
      parseDOM: [{ tag: "pre", preserveWhitespace: "full" }],
      toDOM() {
        return ["pre", ["code", 0]];
      },
    },

    horizontal_rule: {
      group: "block",
      parseDOM: [{ tag: "hr" }],
      toDOM() {
        return ["hr"];
      },
    },

    text: {
      group: "inline",
    },

    mention: {
      group: "inline",
      inline: true,
      atom: true,
      attrs: {
        id: {},
        label: { default: "" },
      },
      toDOM(node) {
        return [
          "span",
          {
            class: "mention-pill",
            "data-entity-id": node.attrs.id,
            contenteditable: "false",
          },
          node.attrs.label,
        ];
      },
      parseDOM: [
        {
          tag: "span.mention-pill",
          getAttrs(dom) {
            return {
              id: dom.getAttribute("data-entity-id"),
              label: dom.textContent,
            };
          },
        },
      ],
    },
  },

  marks: {
    strong: {
      parseDOM: [
        { tag: "strong" },
        { tag: "b", getAttrs: (node) => node.style.fontWeight !== "normal" && null },
        { style: "font-weight=bold" },
        {
          style: "font-weight",
          getAttrs: (value) => /^(bold(er)?|[5-9]\d{2,})$/.test(value) && null,
        },
      ],
      toDOM() {
        return ["strong", 0];
      },
    },

    em: {
      parseDOM: [{ tag: "em" }, { tag: "i" }, { style: "font-style=italic" }],
      toDOM() {
        return ["em", 0];
      },
    },

    code: {
      parseDOM: [{ tag: "code" }],
      toDOM() {
        return ["code", 0];
      },
    },

    link: {
      attrs: {
        href: {},
        title: { default: null },
      },
      inclusive: false,
      parseDOM: [
        {
          tag: "a[href]",
          getAttrs(dom) {
            return {
              href: dom.getAttribute("href"),
              title: dom.getAttribute("title"),
            };
          },
        },
      ],
      toDOM(node) {
        return ["a", { href: node.attrs.href, title: node.attrs.title }, 0];
      },
    },
  },
});
