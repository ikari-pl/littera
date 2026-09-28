/**
 * commands.js — Command registry for the command palette.
 *
 * Each command: { id, label, shortcut, category, action }
 * action is a function that receives (ctx) where ctx = { store, handlers, api }.
 */

export const commands = [
  // Help
  {
    id: "show-help",
    label: "Show help & shortcuts",
    category: "Help",
    shortcut: "Cmd+/",
    action: (ctx) => ctx.handlers.onShowHelp(),
  },

  // Navigation
  {
    id: "nav-work-root",
    label: "Go to Work root",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onBreadcrumbClick(0),
  },
  {
    id: "nav-outline",
    label: "Switch to Outline view",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onTabClick("outline"),
  },
  {
    id: "nav-entities",
    label: "Switch to Entities view",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onTabClick("entities"),
  },
  {
    id: "nav-alignments",
    label: "Switch to Alignments view",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onTabClick("alignments"),
  },
  {
    id: "nav-reviews",
    label: "Switch to Reviews view",
    category: "Navigation",
    shortcut: null,
    action: (ctx) => ctx.handlers.onTabClick("reviews"),
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
    action: (ctx) => ctx.handlers.onSave(),
  },
  {
    id: "editor-zen",
    label: "Toggle distraction-free mode",
    category: "Editor",
    shortcut: "Cmd+Shift+F",
    action: (ctx) => {
      const state = ctx.store.getState();
      if (state.editing) {
        const entering = !state.zenMode;
        ctx.store.dispatch({ type: "toggle-zen" });
        if (entering && ctx.handlers.onZenEntered) {
          ctx.handlers.onZenEntered();
        }
      }
    },
  },

  // Structure — labels are level-aware via dynamicLabel when filtered
  {
    id: "add-document",
    label: "Add document",
    category: "Structure",
    shortcut: null,
    when: (state) => !state.editing && state.view === "outline" && state.path.length === 0,
    action: (ctx) => ctx.handlers.onAddItem(),
  },
  {
    id: "add-section",
    label: "Add section",
    category: "Structure",
    shortcut: null,
    when: (state) =>
      !state.editing &&
      state.view === "outline" &&
      state.path.length > 0 &&
      state.path[state.path.length - 1].kind === "document",
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

  // Alignments / Reviews
  {
    id: "add-alignment",
    label: "Add alignment",
    category: "Semantics",
    shortcut: null,
    action: (ctx) => ctx.handlers.onAddAlignment(),
  },
  {
    id: "add-review",
    label: "Add review",
    category: "Semantics",
    shortcut: null,
    action: (ctx) => ctx.handlers.onAddReview(),
  },

  // Linguistics
  {
    id: "inflect-word",
    label: "Inflect word",
    category: "Linguistics",
    shortcut: null,
    action: (ctx) => ctx.handlers.onOpenInflectDialog(),
  },

  // Export / Import
  {
    id: "export-json",
    label: "Export JSON",
    category: "Export",
    shortcut: null,
    action: (ctx) => ctx.handlers.onExportJSON(),
  },
  {
    id: "export-markdown",
    label: "Export Markdown",
    category: "Export",
    shortcut: null,
    action: (ctx) => ctx.handlers.onExportMarkdown(false),
  },
  {
    id: "export-compile",
    label: "Compile manuscript (Markdown)",
    category: "Export",
    shortcut: null,
    action: (ctx) => ctx.handlers.onExportMarkdown(true),
  },
  {
    id: "import-json",
    label: "Import JSON…",
    category: "Export",
    shortcut: null,
    action: (ctx) => ctx.handlers.onImportJSON(),
  },
];

/** Filter commands by query; respect optional when(state) predicates. */
export function visibleCommands(state, query = "") {
  const q = query.toLowerCase().trim();
  return commands.filter((c) => {
    if (typeof c.action !== "function") return false;
    if (typeof c.when === "function" && !c.when(state)) return false;
    if (!q) return true;
    return c.label.toLowerCase().includes(q);
  });
}
