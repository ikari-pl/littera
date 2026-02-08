/**
 * slash-menu.js — Slash command palette (ProseMirror Plugin + PluginView).
 *
 * Type "/" at the start of an empty paragraph → command list appears.
 * Subsequent characters filter the list. Select a command to transform
 * the current block (heading, code block, HR, etc.).
 */

import { Plugin, PluginKey } from "prosemirror-state";
import { setBlockType, wrapIn } from "prosemirror-commands";
import { positionPopup } from "./popup-utils.js";
import { schema } from "./schema.js";

export const slashMenuKey = new PluginKey("slashMenu");

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

const COMMANDS = [
  { label: "Heading 1", keywords: "h1 title", icon: "H1" },
  { label: "Heading 2", keywords: "h2 subtitle", icon: "H2" },
  { label: "Heading 3", keywords: "h3", icon: "H3" },
  { label: "Code Block", keywords: "code fence", icon: "</>" },
  { label: "Horizontal Rule", keywords: "hr divider separator line", icon: "—" },
  { label: "Quote", keywords: "blockquote", icon: "\"" },
  { label: "Plain Text", keywords: "paragraph text", icon: "¶" },
];

function executeCommand(view, command, slashState) {
  const { from, to } = slashState;
  const state = view.state;
  const label = command.label;

  if (label === "Horizontal Rule") {
    // Replace the entire paragraph node with HR + new empty paragraph.
    // `from` is inside the paragraph content, so resolve to find node bounds.
    const $from = state.doc.resolve(from);
    const paraPos = $from.before($from.depth);   // before paragraph node
    const paraEnd = $from.after($from.depth);     // after paragraph node

    const hrNode = schema.nodes.horizontal_rule.create();
    const newPara = schema.nodes.paragraph.create();
    let tr = state.tr.replaceWith(paraPos, paraEnd, [hrNode, newPara]);
    // HR nodeSize=1, paragraph open=+1 → cursor at paraPos+2
    tr = tr.setSelection(
      state.selection.constructor.near(tr.doc.resolve(paraPos + 2))
    );
    view.dispatch(tr);
    return;
  }

  // Delete the "/" and filter text, then change block type
  const tr = state.tr.delete(from, to);
  view.dispatch(tr);

  if (label === "Heading 1") {
    setBlockType(schema.nodes.heading, { level: 1 })(view.state, view.dispatch);
  } else if (label === "Heading 2") {
    setBlockType(schema.nodes.heading, { level: 2 })(view.state, view.dispatch);
  } else if (label === "Heading 3") {
    setBlockType(schema.nodes.heading, { level: 3 })(view.state, view.dispatch);
  } else if (label === "Code Block") {
    setBlockType(schema.nodes.code_block)(view.state, view.dispatch);
  } else if (label === "Quote") {
    wrapIn(schema.nodes.blockquote)(view.state, view.dispatch);
  } else if (label === "Plain Text") {
    setBlockType(schema.nodes.paragraph)(view.state, view.dispatch);
  }
}

function filterCommands(filter) {
  if (!filter) return COMMANDS;
  const lower = filter.toLowerCase();
  return COMMANDS.filter(
    (c) =>
      c.label.toLowerCase().includes(lower) ||
      c.keywords.toLowerCase().includes(lower)
  );
}

// ---------------------------------------------------------------------------
// PluginView
// ---------------------------------------------------------------------------

class SlashMenuView {
  constructor(editorView) {
    this.view = editorView;
    this.selectedIndex = 0;
    this.filteredCommands = COMMANDS;

    this.dom = document.createElement("div");
    this.dom.className = "slash-menu";
    this.dom.style.display = "none";

    const container = editorView.dom.parentElement;
    container.appendChild(this.dom);
  }

  update(view) {
    const pluginState = slashMenuKey.getState(view.state);
    if (!pluginState || !pluginState.active) {
      this.dom.style.display = "none";
      return;
    }

    this.filteredCommands = filterCommands(pluginState.filter);
    if (this.filteredCommands.length === 0) {
      this.dom.style.display = "none";
      return;
    }

    this.selectedIndex = Math.min(
      this.selectedIndex,
      this.filteredCommands.length - 1
    );

    this._render();
    this.dom.style.display = "block";

    // Position at cursor
    const coords = view.coordsAtPos(pluginState.pos);
    const rect = {
      top: coords.top,
      bottom: coords.bottom,
      left: coords.left,
      right: coords.left + 1,
    };
    const container = view.dom.parentElement;
    positionPopup(this.dom, rect, container);
  }

  _render() {
    this.dom.innerHTML = "";
    this.filteredCommands.forEach((cmd, i) => {
      const item = document.createElement("div");
      item.className = "slash-item" + (i === this.selectedIndex ? " selected" : "");

      const icon = document.createElement("span");
      icon.className = "slash-item-icon";
      icon.textContent = cmd.icon;
      item.appendChild(icon);

      const label = document.createElement("span");
      label.textContent = cmd.label;
      item.appendChild(label);

      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        const state = slashMenuKey.getState(this.view.state);
        if (state && state.active) {
          executeCommand(this.view, cmd, state);
        }
        this.view.focus();
      });

      this.dom.appendChild(item);
    });
  }

  destroy() {
    this.dom.remove();
  }
}

// ---------------------------------------------------------------------------
// Plugin state: detect "/" at start of empty paragraph
// ---------------------------------------------------------------------------

function detectSlash(state) {
  const sel = state.selection;
  if (!sel.empty) return { active: false };

  const $cursor = sel.$cursor;
  if (!$cursor) return { active: false };

  // Must be inside a paragraph
  const parent = $cursor.parent;
  if (parent.type !== schema.nodes.paragraph) return { active: false };

  const text = parent.textContent;
  if (!text.startsWith("/")) return { active: false };

  // The paragraph should contain *only* the slash-filter text (no other inline content)
  // This prevents triggering on e.g. "some text /command"
  const parentStart = $cursor.start($cursor.depth);
  if ($cursor.pos !== parentStart + text.length) return { active: false };

  return {
    active: true,
    filter: text.slice(1),
    pos: parentStart,                    // for popup positioning (where "/" is)
    from: parentStart,                   // start of "/" text in paragraph
    to: parentStart + text.length,       // end of typed text
  };
}

// ---------------------------------------------------------------------------
// Plugin export
// ---------------------------------------------------------------------------

export function slashMenu() {
  return new Plugin({
    key: slashMenuKey,

    state: {
      init() {
        return { active: false };
      },
      apply(_tr, _value, _oldState, newState) {
        return detectSlash(newState);
      },
    },

    props: {
      handleKeyDown(view, event) {
        const pluginState = slashMenuKey.getState(view.state);
        if (!pluginState || !pluginState.active) return false;

        const menuView = bubbleView(view);

        if (event.key === "ArrowDown") {
          event.preventDefault();
          if (menuView) {
            const max = menuView.filteredCommands.length - 1;
            menuView.selectedIndex = Math.min(menuView.selectedIndex + 1, max);
            menuView._render();
          }
          return true;
        }

        if (event.key === "ArrowUp") {
          event.preventDefault();
          if (menuView) {
            menuView.selectedIndex = Math.max(menuView.selectedIndex - 1, 0);
            menuView._render();
          }
          return true;
        }

        if (event.key === "Enter") {
          event.preventDefault();
          if (menuView && menuView.filteredCommands.length > 0) {
            const cmd = menuView.filteredCommands[menuView.selectedIndex];
            executeCommand(view, cmd, pluginState);
          }
          return true;
        }

        if (event.key === "Escape") {
          event.preventDefault();
          // Delete the "/" text to dismiss
          const { from, to } = pluginState;
          const tr = view.state.tr.delete(from, to);
          view.dispatch(tr);
          return true;
        }

        return false;
      },
    },

    view(editorView) {
      const menuView = new SlashMenuView(editorView);
      // Stash reference for handleKeyDown to access
      editorView._slashMenuView = menuView;
      return menuView;
    },
  });
}

// Retrieve the SlashMenuView instance from the editor
function bubbleView(view) {
  return view._slashMenuView || null;
}
