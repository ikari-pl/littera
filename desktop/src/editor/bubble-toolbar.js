/**
 * bubble-toolbar.js — Floating selection toolbar (ProseMirror PluginView).
 *
 * Shows Bold / Italic / Code / Link / H1 / H2 / H3 when text is selected.
 * Hides when selection is empty, in a code_block, or another popup is active.
 */

import { Plugin, PluginKey } from "prosemirror-state";
import { toggleMark, setBlockType } from "prosemirror-commands";
import { positionPopup, showLinkInput } from "./popup-utils.js";
import { schema } from "./schema.js";
import { slashMenuKey } from "./slash-menu.js";
import { mentionPopupKey } from "./mention-popup.js";

export const bubbleToolbarKey = new PluginKey("bubbleToolbar");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function markActive(state, markType) {
  const { from, $from, to, empty } = state.selection;
  if (empty) {
    return !!(state.storedMarks || $from.marks()).find(
      (m) => m.type === markType
    );
  }
  return state.doc.rangeHasMark(from, to, markType);
}

function blockTypeActive(state, nodeType, attrs) {
  const { $from } = state.selection;
  // Walk up to find the innermost block node
  for (let d = $from.depth; d > 0; d--) {
    const node = $from.node(d);
    if (node.type === nodeType) {
      if (attrs && attrs.level !== undefined) {
        return node.attrs.level === attrs.level;
      }
      return true;
    }
  }
  return false;
}

function inCodeBlock(state) {
  const { $from } = state.selection;
  for (let d = $from.depth; d > 0; d--) {
    if ($from.node(d).type === schema.nodes.code_block) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// PluginView
// ---------------------------------------------------------------------------

class BubbleToolbarView {
  constructor(editorView) {
    this.view = editorView;

    this.dom = document.createElement("div");
    this.dom.className = "bubble-toolbar";
    this.dom.style.display = "none";

    this.buttons = [];
    this._buildButtons();

    // Append to the editor's parent (which has position:relative)
    const container = editorView.dom.parentElement;
    container.appendChild(this.dom);
  }

  _buildButtons() {
    const items = [
      { label: "B", title: "Bold (Cmd+B)", action: "bold", style: "font-weight:700" },
      { label: "I", title: "Italic (Cmd+I)", action: "italic", style: "font-style:italic" },
      { label: "</>", title: "Code (Cmd+E)", action: "code", style: "font-family:monospace;font-size:0.7rem" },
      { label: "Link", title: "Link (Cmd+K)", action: "link", style: "" },
      { sep: true },
      { label: "H1", title: "Heading 1", action: "h1", style: "" },
      { label: "H2", title: "Heading 2", action: "h2", style: "" },
      { label: "H3", title: "Heading 3", action: "h3", style: "" },
    ];

    for (const item of items) {
      if (item.sep) {
        const sep = document.createElement("span");
        sep.className = "bt-btn-sep";
        this.dom.appendChild(sep);
        continue;
      }

      const btn = document.createElement("button");
      btn.className = "bt-btn";
      btn.textContent = item.label;
      btn.title = item.title;
      if (item.style) btn.style.cssText = item.style;
      btn.dataset.action = item.action;

      btn.addEventListener("mousedown", (e) => {
        e.preventDefault(); // Prevent focus loss
        this._execute(item.action);
      });

      this.dom.appendChild(btn);
      this.buttons.push({ btn, action: item.action });
    }
  }

  _execute(action) {
    const view = this.view;
    const state = view.state;

    switch (action) {
      case "bold":
        toggleMark(schema.marks.strong)(state, view.dispatch);
        break;
      case "italic":
        toggleMark(schema.marks.em)(state, view.dispatch);
        break;
      case "code":
        toggleMark(schema.marks.code)(state, view.dispatch);
        break;
      case "link":
        this._toggleLink();
        break;
      case "h1":
        setBlockType(schema.nodes.heading, { level: 1 })(state, view.dispatch);
        break;
      case "h2":
        setBlockType(schema.nodes.heading, { level: 2 })(state, view.dispatch);
        break;
      case "h3":
        setBlockType(schema.nodes.heading, { level: 3 })(state, view.dispatch);
        break;
    }

    view.focus();
  }

  _toggleLink() {
    const view = this.view;
    const linkMark = schema.marks.link;
    if (markActive(view.state, linkMark)) {
      toggleMark(linkMark)(view.state, view.dispatch);
      return;
    }
    showLinkInput(view, (href) => {
      toggleMark(linkMark, { href })(view.state, view.dispatch);
    });
  }

  update(view) {
    const state = view.state;
    const { from, to, empty } = state.selection;

    // Hide if: empty selection, in code block, or another popup is active
    if (empty || inCodeBlock(state)) {
      this.dom.style.display = "none";
      return;
    }

    const slash = slashMenuKey.getState(state);
    const mention = mentionPopupKey.getState(state);
    if ((slash && slash.active) || (mention && mention.active)) {
      this.dom.style.display = "none";
      return;
    }

    // Show toolbar
    this.dom.style.display = "flex";

    // Update active states
    for (const { btn, action } of this.buttons) {
      let active = false;
      switch (action) {
        case "bold": active = markActive(state, schema.marks.strong); break;
        case "italic": active = markActive(state, schema.marks.em); break;
        case "code": active = markActive(state, schema.marks.code); break;
        case "link": active = markActive(state, schema.marks.link); break;
        case "h1": active = blockTypeActive(state, schema.nodes.heading, { level: 1 }); break;
        case "h2": active = blockTypeActive(state, schema.nodes.heading, { level: 2 }); break;
        case "h3": active = blockTypeActive(state, schema.nodes.heading, { level: 3 }); break;
      }
      btn.classList.toggle("active", active);
    }

    // Position relative to selection
    const fromCoords = view.coordsAtPos(from);
    const toCoords = view.coordsAtPos(to);
    const rect = {
      top: Math.min(fromCoords.top, toCoords.top),
      bottom: Math.max(fromCoords.bottom, toCoords.bottom),
      left: Math.min(fromCoords.left, toCoords.left),
      right: Math.max(fromCoords.right, toCoords.right),
    };

    const container = view.dom.parentElement;
    positionPopup(this.dom, rect, container);
  }

  destroy() {
    this.dom.remove();
  }
}

// ---------------------------------------------------------------------------
// Plugin export
// ---------------------------------------------------------------------------

export function bubbleToolbar() {
  return new Plugin({
    key: bubbleToolbarKey,
    view(editorView) {
      return new BubbleToolbarView(editorView);
    },
  });
}
