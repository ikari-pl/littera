/**
 * mention-popup.js — @ entity mention popup (ProseMirror Plugin + PluginView).
 *
 * Type "@" anywhere → popup appears with entity list.
 * Type more characters to filter. Select entity to insert mention node.
 */

import { Plugin, PluginKey } from "prosemirror-state";
import { positionPopup } from "./popup-utils.js";
import { schema } from "./schema.js";

export const mentionPopupKey = new PluginKey("mentionPopup");

// ---------------------------------------------------------------------------
// Plugin state: detect "@query" at cursor
// ---------------------------------------------------------------------------

function detectMention(state) {
  const sel = state.selection;
  if (!sel.empty) return { active: false };

  const $cursor = sel.$cursor;
  if (!$cursor) return { active: false };

  // Must be in a text-containing node (not code_block)
  const parent = $cursor.parent;
  if (parent.type.spec.code) return { active: false };

  // Get text before cursor within the current textblock
  const textBefore = parent.textBetween(
    0,
    $cursor.parentOffset,
    null,
    "\ufffc" // object replacement char for non-text nodes
  );

  // Scan backwards for "@" — stop at whitespace or start
  const atIdx = textBefore.lastIndexOf("@");
  if (atIdx === -1) return { active: false };

  // Check no spaces between @ and cursor
  const query = textBefore.slice(atIdx + 1);
  if (/\s/.test(query)) return { active: false };

  // Compute document positions for the @...query range
  const parentStart = $cursor.start($cursor.depth);
  const from = parentStart + atIdx;
  const to = parentStart + $cursor.parentOffset;

  return {
    active: true,
    query,
    from, // position of "@"
    to, // position after the query text (cursor pos)
  };
}

// ---------------------------------------------------------------------------
// PluginView
// ---------------------------------------------------------------------------

class MentionPopupView {
  constructor(editorView, fetchEntities) {
    this.view = editorView;
    this.fetchEntities = fetchEntities;
    this.entities = null; // cached entity list
    this.loading = false;
    this.selectedIndex = 0;
    this.filteredEntities = [];

    this.dom = document.createElement("div");
    this.dom.className = "mention-popup";
    this.dom.style.display = "none";

    const container = editorView.dom.parentElement;
    container.appendChild(this.dom);
  }

  async _ensureEntities() {
    if (this.entities !== null || this.loading) return;
    this.loading = true;
    try {
      this.entities = await this.fetchEntities();
    } catch (e) {
      this.entities = [];
    }
    this.loading = false;
    // Re-trigger an update by dispatching an empty transaction
    this.view.dispatch(this.view.state.tr);
  }

  update(view) {
    const pluginState = mentionPopupKey.getState(view.state);
    if (!pluginState || !pluginState.active) {
      this.dom.style.display = "none";
      this.selectedIndex = 0;
      return;
    }

    // Ensure entities are loaded
    if (this.entities === null) {
      this._ensureEntities();
      return;
    }

    // Filter entities by query
    const query = pluginState.query.toLowerCase();
    this.filteredEntities = query
      ? this.entities.filter((e) => e.label.toLowerCase().includes(query))
      : this.entities;

    if (this.filteredEntities.length === 0) {
      this.dom.style.display = "none";
      return;
    }

    this.selectedIndex = Math.min(
      this.selectedIndex,
      this.filteredEntities.length - 1
    );

    this._render();
    this.dom.style.display = "block";

    // Position at the "@" character
    const coords = view.coordsAtPos(pluginState.from);
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
    this.filteredEntities.forEach((entity, i) => {
      const item = document.createElement("div");
      item.className =
        "mention-item" + (i === this.selectedIndex ? " selected" : "");

      const label = document.createElement("span");
      label.className = "mention-item-label";
      label.textContent = entity.label;
      item.appendChild(label);

      if (entity.entity_type) {
        const badge = document.createElement("span");
        badge.className = "mention-item-type";
        badge.textContent = entity.entity_type;
        item.appendChild(badge);
      }

      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        const state = mentionPopupKey.getState(this.view.state);
        if (state && state.active) {
          this._insertMention(entity, state);
        }
        this.view.focus();
      });

      this.dom.appendChild(item);
    });
  }

  _insertMention(entity, pluginState) {
    const { from, to } = pluginState;
    const mentionNode = schema.nodes.mention.create({
      id: entity.id,
      label: entity.label,
    });
    const tr = this.view.state.tr.replaceWith(from, to, mentionNode);
    this.view.dispatch(tr);
  }

  destroy() {
    this.dom.remove();
  }
}

// ---------------------------------------------------------------------------
// Plugin export
// ---------------------------------------------------------------------------

export function mentionPopup({ fetchEntities }) {
  return new Plugin({
    key: mentionPopupKey,

    state: {
      init() {
        return { active: false };
      },
      apply(_tr, _value, _oldState, newState) {
        return detectMention(newState);
      },
    },

    props: {
      handleKeyDown(view, event) {
        const pluginState = mentionPopupKey.getState(view.state);
        if (!pluginState || !pluginState.active) return false;

        const popupView = view._mentionPopupView;
        if (!popupView || popupView.filteredEntities.length === 0) return false;

        if (event.key === "ArrowDown") {
          event.preventDefault();
          const max = popupView.filteredEntities.length - 1;
          popupView.selectedIndex = Math.min(
            popupView.selectedIndex + 1,
            max
          );
          popupView._render();
          return true;
        }

        if (event.key === "ArrowUp") {
          event.preventDefault();
          popupView.selectedIndex = Math.max(
            popupView.selectedIndex - 1,
            0
          );
          popupView._render();
          return true;
        }

        if (event.key === "Enter") {
          event.preventDefault();
          const entity =
            popupView.filteredEntities[popupView.selectedIndex];
          if (entity) {
            popupView._insertMention(entity, pluginState);
          }
          return true;
        }

        if (event.key === "Escape") {
          event.preventDefault();
          // Delete the @query text to dismiss
          const { from, to } = pluginState;
          const tr = view.state.tr.delete(from, to);
          view.dispatch(tr);
          return true;
        }

        return false;
      },
    },

    view(editorView) {
      const popupView = new MentionPopupView(editorView, fetchEntities);
      editorView._mentionPopupView = popupView;
      return popupView;
    },
  });
}
