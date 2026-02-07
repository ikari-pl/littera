/**
 * editor.js — ProseMirror EditorView setup, plugins, and keymaps.
 *
 * Exports:
 *   createEditor(container, { onDocChange, fetchEntities }) — mount editor with plugins
 *   loadSection(view, blocks)                               — replace doc from block array
 */

import { EditorState } from "prosemirror-state";
import { EditorView } from "prosemirror-view";
import { history, undo, redo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { baseKeymap, toggleMark } from "prosemirror-commands";
import {
  inputRules,
  textblockTypeInputRule,
} from "prosemirror-inputrules";

import { schema } from "./schema.js";
import { blocksToDoc } from "./markdown.js";
import { MentionView } from "./mention-view.js";
import { bubbleToolbar } from "./bubble-toolbar.js";
import { slashMenu } from "./slash-menu.js";
import { mentionPopup } from "./mention-popup.js";
import { showLinkInput } from "./popup-utils.js";

// ---------------------------------------------------------------------------
// Input rules — Markdown-like shortcuts
// ---------------------------------------------------------------------------

function headingRule(level) {
  return textblockTypeInputRule(
    new RegExp("^(#{1," + level + "})\\s$"),
    schema.nodes.heading,
    (match) => ({ level: match[1].length })
  );
}

function codeBlockRule() {
  return textblockTypeInputRule(/^```$/, schema.nodes.code_block);
}

const litteraInputRules = inputRules({
  rules: [headingRule(3), codeBlockRule()],
});

// ---------------------------------------------------------------------------
// Custom command: create new block after current (Shift+Enter)
// ---------------------------------------------------------------------------

function createBlockAfter(state, dispatch) {
  const { $from } = state.selection;

  // Walk up to find the littera_block node
  let blockDepth = null;
  for (let d = $from.depth; d > 0; d--) {
    if ($from.node(d).type === schema.nodes.littera_block) {
      blockDepth = d;
      break;
    }
  }
  if (blockDepth === null) return false;

  if (dispatch) {
    const blockEnd = $from.end(blockDepth) + 1; // position after the block
    const newBlock = schema.nodes.littera_block.create(
      {
        id: crypto.randomUUID(),
        block_type: "prose",
        language: $from.node(blockDepth).attrs.language || "en",
      },
      [schema.nodes.paragraph.create()]
    );

    const tr = state.tr.insert(blockEnd, newBlock);
    // Move cursor into the new block's first paragraph
    tr.setSelection(
      EditorState.create({ doc: tr.doc, schema }).selection.constructor.near(
        tr.doc.resolve(blockEnd + 2) // inside the new paragraph
      )
    );
    dispatch(tr.scrollIntoView());
  }
  return true;
}

// ---------------------------------------------------------------------------
// promptLink command — Cmd+K toggles link mark or shows URL input
// ---------------------------------------------------------------------------

function promptLink(state, dispatch, view) {
  const linkMark = schema.marks.link;
  const { from, $from, to, empty } = state.selection;
  const isActive = empty
    ? !!(state.storedMarks || $from.marks()).find((m) => m.type === linkMark)
    : state.doc.rangeHasMark(from, to, linkMark);

  if (isActive) {
    return toggleMark(linkMark)(state, dispatch);
  }

  if (view) {
    showLinkInput(view, (href) => {
      toggleMark(linkMark, { href })(view.state, view.dispatch);
    });
  }
  return true;
}

// ---------------------------------------------------------------------------
// createEditor — mount EditorView
// ---------------------------------------------------------------------------

export function createEditor(container, { onDocChange, fetchEntities }) {
  const doc = schema.nodes.doc.create(null, [
    schema.nodes.littera_block.create(
      { id: "placeholder", block_type: "prose", language: "en" },
      [schema.nodes.paragraph.create()]
    ),
  ]);

  const state = EditorState.create({
    doc,
    plugins: [
      history(),
      keymap({
        "Mod-z": undo,
        "Mod-Shift-z": redo,
        "Mod-y": redo,
        "Mod-b": toggleMark(schema.marks.strong),
        "Mod-i": toggleMark(schema.marks.em),
        "Mod-e": toggleMark(schema.marks.code),
        "Mod-k": promptLink,
      }),
      keymap({ "Shift-Enter": createBlockAfter }),
      slashMenu(),
      mentionPopup({ fetchEntities: fetchEntities || (() => Promise.resolve([])) }),
      keymap(baseKeymap),
      bubbleToolbar(),
      litteraInputRules,
    ],
  });

  const view = new EditorView(container, {
    state,
    nodeViews: {
      mention(node) {
        return new MentionView(node);
      },
    },
    dispatchTransaction(tr) {
      const newState = view.state.apply(tr);
      view.updateState(newState);
      if (tr.docChanged && onDocChange) {
        onDocChange();
      }
    },
  });

  return view;
}

// ---------------------------------------------------------------------------
// loadSection — replace editor content from block array
// ---------------------------------------------------------------------------

export function loadSection(view, blocks) {
  const doc = blocksToDoc(blocks);
  const state = EditorState.create({
    doc,
    plugins: view.state.plugins,
  });
  view.updateState(state);
  return doc;
}
