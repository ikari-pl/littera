/**
 * commands.js — Command registry for the command palette.
 *
 * Each command: { id, label, shortcut, category, action }
 * action is a function that receives (ctx) where ctx = { store, handlers, api }.
 * Commands with action: null are handled by existing keydown listeners.
 */

export const commands = [
  // Navigation
  {
    id: "nav-work-root",
    label: "Go to Work root",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onBreadcrumbClick(0),
  },
  {
    id: "nav-entities",
    label: "Switch to Entities view",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onTabClick("entities"),
  },
  {
    id: "nav-outline",
    label: "Switch to Outline view",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onTabClick("outline"),
  },
  {
    id: "nav-switch-work",
    label: "Switch Work",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onSwitchWork(),
  },

  // Editor
  {
    id: "editor-save",
    label: "Save",
    category: "Editor",
    shortcut: "Cmd+S",
    action: null, // handled by existing keydown
  },
  {
    id: "editor-zen",
    label: "Toggle distraction-free mode",
    category: "Editor",
    shortcut: "Cmd+Shift+F",
    action: (ctx) => {
      const state = ctx.store.getState();
      if (state.editing) ctx.store.dispatch({ type: "toggle-zen" });
    },
  },

  // Structure
  {
    id: "add-document",
    label: "Add document",
    category: "Structure",
    shortcut: null,
    action: (ctx) => ctx.handlers.onAddItem(),
  },
  {
    id: "add-section",
    label: "Add section",
    category: "Structure",
    shortcut: null,
    action: (ctx) => ctx.handlers.onAddItem(),
  },

  // Entity
  {
    id: "add-entity",
    label: "Add entity",
    category: "Entity",
    shortcut: null,
    action: (ctx) => ctx.handlers.onAddEntity(),
  },
];
