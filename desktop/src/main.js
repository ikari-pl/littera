/**
 * main.js — Bootstrap, store wiring, navigation logic, editor lifecycle.
 *
 * Initializes the store, connects Tauri IPC for the sidecar port,
 * subscribes the renderer, and implements the navigation flow.
 * Phase 2C: ProseMirror editor lifecycle, save, dirty tracking.
 * Phase 2D: Work directory picker on launch.
 */

import { initialState, reduce, createStore } from "./state.js";
import { render } from "./render.js";
import * as api from "./api.js";
import {
  createEditor,
  loadSection,
  findDirtyBlocks,
  blockNodeToMarkdown,
} from "./editor.bundle.js";

const { invoke } = window.__TAURI__.core;

const store = createStore(reduce, initialState);

// ---------------------------------------------------------------------------
// Preview text helper — strips markdown mention syntax for sidebar display
// ---------------------------------------------------------------------------

function previewText(sourceText) {
  return (sourceText || "")
    .replace(/\{@([^|]+)\|entity:[^}]+\}/g, "$1")  // {@Label|entity:uuid} → Label
    .replace(/\n/g, " ")
    .slice(0, 60);
}

// ---------------------------------------------------------------------------
// Editor instance (lives outside store — mutable singleton)
// ---------------------------------------------------------------------------

let editorView = null;
let pendingBlocks = null; // blocks to load once editor container is ready

// ---------------------------------------------------------------------------
// Dirty navigation guard
// ---------------------------------------------------------------------------

function checkDirtyBeforeNav() {
  const state = store.getState();
  if (state.editing && state.dirty) {
    return window.confirm("You have unsaved changes. Discard them?");
  }
  return true;
}

// ---------------------------------------------------------------------------
// Picker handlers
// ---------------------------------------------------------------------------

const pickerHandlers = {
  async onSelectWork(path) {
    store.dispatch({ type: "picker-loading" });
    try {
      const port = await invoke("open_work", { path });
      store.dispatch({ type: "init", port });
      await loadLevel();
    } catch (err) {
      store.dispatch({ type: "picker-error", message: String(err) });
    }
  },

  async onBrowseWork() {
    try {
      const path = await invoke("pick_folder");
      if (path) {
        await pickerHandlers.onSelectWork(path);
      }
    } catch (err) {
      store.dispatch({ type: "picker-error", message: String(err) });
    }
  },

  async onNewWork() {
    try {
      const path = await invoke("pick_folder");
      if (!path) return;
      store.dispatch({ type: "picker-loading" });
      await invoke("init_work", { path });
      const port = await invoke("open_work", { path });
      store.dispatch({ type: "init", port });
      await loadLevel();
    } catch (err) {
      store.dispatch({ type: "picker-error", message: String(err) });
    }
  },

  async onSetWorkspace() {
    try {
      const path = await invoke("pick_folder");
      if (!path) return;
      const data = await invoke("set_workspace", { path });
      store.dispatch({ type: "set-picker-data", data });
    } catch (err) {
      store.dispatch({ type: "picker-error", message: String(err) });
    }
  },
};

// ---------------------------------------------------------------------------
// Event handlers (passed to render functions)
// ---------------------------------------------------------------------------

const handlers = {
  // Picker handlers (merged in)
  ...pickerHandlers,

  onItemClick(item) {
    const state = store.getState();

    if (state.view === "entities") {
      if (!checkDirtyBeforeNav()) return;
      store.dispatch({ type: "select-entity", id: item.id });
      loadEntityDetail(item.id);
      return;
    }

    const level = currentLevel(state);

    if (level === "documents") {
      if (!checkDirtyBeforeNav()) return;
      store.dispatch({ type: "push", element: { kind: "document", id: item.id, title: item.title } });
      loadLevel();
    } else if (level === "sections") {
      if (!checkDirtyBeforeNav()) return;
      store.dispatch({ type: "push", element: { kind: "section", id: item.id, title: item.title } });
      loadLevel();
    } else if (level === "blocks") {
      store.dispatch({ type: "select", id: item.id });
    }
  },

  onBreadcrumbClick(depth) {
    if (!checkDirtyBeforeNav()) return;
    // If viewing entities, switch back to outline before navigating
    const state = store.getState();
    if (state.view === "entities") {
      store.dispatch({ type: "set-view", view: "outline" });
    }
    store.dispatch({ type: "pop-to", depth });
    loadLevel();
  },

  onTabClick(view) {
    if (!checkDirtyBeforeNav()) return;
    // Close editor before switching views to clear editing state
    const state = store.getState();
    if (state.editing) {
      store.dispatch({ type: "editor-close" });
    }
    store.dispatch({ type: "set-view", view });
    if (view === "entities") {
      loadEntities();
    } else {
      loadLevel();
    }
  },

  async onAddItem() {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    const level = currentLevel(state);

    if (level === "documents") {
      const title = window.prompt("Document title:");
      if (!title) return;
      try {
        await api.createDocument(port, title);
        await loadLevel();
      } catch (err) {
        store.dispatch({ type: "error", message: err.message });
      }
    } else if (level === "sections") {
      const last = state.path[state.path.length - 1];
      const title = window.prompt("Section title:");
      if (!title) return;
      try {
        await api.createSection(port, last.id, title);
        await loadLevel();
      } catch (err) {
        store.dispatch({ type: "error", message: err.message });
      }
    }
  },

  async onDeleteItem(item) {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    const level = currentLevel(state);
    const label = item.title || "(untitled)";
    if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) return;

    try {
      if (level === "documents") {
        await api.deleteDocument(port, item.id);
      } else if (level === "sections") {
        await api.deleteSection(port, item.id);
      } else if (level === "blocks") {
        await api.deleteBlock(port, item.id);
      }
      await loadLevel();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onAddEntity() {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    const entityType = window.prompt("Entity type (e.g. concept):", "concept");
    if (!entityType) return;
    const label = window.prompt("Entity name:");
    if (!label) return;

    try {
      await api.createEntity(port, entityType, label);
      await loadEntities();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onDeleteEntity(entity) {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    if (!window.confirm(`Delete entity "${entity.label}"? This cannot be undone.`)) return;

    try {
      await api.deleteEntity(port, entity.id);
      store.dispatch({ type: "set-entity-detail", detail: null });
      store.dispatch({ type: "select-entity", id: null });
      await loadEntities();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onDeleteMention(mention) {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    if (!window.confirm("Delete this mention? The text in the block will remain but the entity link will be removed.")) return;

    try {
      await api.deleteMention(port, mention.id);
      await loadEntityDetail(state.selectedEntityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onEditEntityNote(entityId) {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    const current = state.entityDetail?.note || "";
    const note = window.prompt("Entity note:", current);
    if (note === null) return;

    try {
      await api.saveEntityNote(port, entityId, note);
      await loadEntityDetail(entityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },
};

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

function currentLevel(state) {
  if (state.path.length === 0) return "documents";
  const last = state.path[state.path.length - 1];
  if (last.kind === "document") return "sections";
  if (last.kind === "section") return "blocks";
  return "documents";
}

async function loadLevel() {
  const state = store.getState();
  const port = state.sidecarPort;
  if (!port) return;

  store.dispatch({ type: "loading" });

  try {
    if (state.path.length === 0) {
      const docs = await api.fetchDocuments(port);
      store.dispatch({ type: "set-items", items: docs });
    } else {
      const last = state.path[state.path.length - 1];

      if (last.kind === "document") {
        const sections = await api.fetchSections(port, last.id);
        store.dispatch({ type: "set-items", items: sections });
      } else if (last.kind === "section") {
        const blocks = await api.fetchBlocks(port, last.id);

        // Sidebar items
        store.dispatch({ type: "set-items", items: blocks.map(b => ({
          ...b,
          title: previewText(b.source_text),
        }))});
        store.dispatch({ type: "set-detail", detail: blocks });

        // Open editor
        if (editorView) {
          // Editor already exists — just reload content
          const doc = loadSection(editorView, blocks);
          store.dispatch({ type: "editor-open", sectionId: last.id, doc });
        } else {
          // Stage blocks; subscriber will create editor + load after render
          pendingBlocks = blocks;
          store.dispatch({ type: "editor-open", sectionId: last.id, doc: null });
        }
      }
    }
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

async function loadEntities() {
  const port = store.getState().sidecarPort;
  if (!port) return;

  store.dispatch({ type: "loading" });
  try {
    const entities = await api.fetchEntities(port);
    store.dispatch({ type: "set-entities", entities });
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

async function loadEntityDetail(entityId) {
  const port = store.getState().sidecarPort;
  if (!port) return;

  try {
    const detail = await api.fetchEntity(port, entityId);
    store.dispatch({ type: "set-entity-detail", detail });
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

// ---------------------------------------------------------------------------
// Store subscriber — renders + manages editor lifecycle
// ---------------------------------------------------------------------------

store.subscribe((state) => {
  render(state, handlers);

  // Editor lifecycle is only relevant in the ready phase
  if (state.phase !== "ready") return;

  // Create editor when entering editing mode
  if (state.editing && !editorView) {
    const container = document.getElementById("prosemirror-editor");
    if (container) {
      editorView = createEditor(container, {
        onDocChange() {
          store.dispatch({ type: "editor-mark-dirty" });
        },
        fetchEntities: () => api.fetchEntities(store.getState().sidecarPort),
        onMentionClick(entityId) {
          store.dispatch({ type: "editor-close" });
          store.dispatch({ type: "set-view", view: "entities" });
          store.dispatch({ type: "select-entity", id: entityId });
          loadEntities();
          loadEntityDetail(entityId);
        },
      });

      // Load staged blocks
      if (pendingBlocks) {
        const doc = loadSection(editorView, pendingBlocks);
        store.dispatch({ type: "editor-mark-saved", doc });
        pendingBlocks = null;
      }
    }
  }

  // Destroy editor when leaving editing mode
  if (!state.editing && editorView) {
    editorView.destroy();
    editorView = null;
    pendingBlocks = null;
  }
});

// ---------------------------------------------------------------------------
// Warn on window/tab close with unsaved changes
// ---------------------------------------------------------------------------

window.addEventListener("beforeunload", (e) => {
  const state = store.getState();
  if (state.editing && state.dirty) {
    e.preventDefault();
  }
});

// ---------------------------------------------------------------------------
// Cmd+S save handler
// ---------------------------------------------------------------------------

document.addEventListener("keydown", async (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "s") {
    e.preventDefault();

    const state = store.getState();
    if (!state.editing || !state.dirty || !editorView) return;

    const port = state.sidecarPort;
    const savedDoc = state.savedDoc;
    const currentDoc = editorView.state.doc;

    try {
      if (!savedDoc) {
        // First save — treat all blocks as batch update
        await saveAllBlocks(port, currentDoc, state.editorSectionId);
      } else {
        const { updates, creates, deletes } = findDirtyBlocks(savedDoc, currentDoc);

        if (updates.length > 0) {
          const batch = updates.map((u) => ({
            id: u.id,
            source_text: blockNodeToMarkdown(u.node),
          }));
          await api.saveBlocksBatch(port, batch);
        }

        for (const c of creates) {
          await api.createBlock(port, state.editorSectionId, {
            id: c.id,
            block_type: c.node.attrs.block_type,
            language: c.node.attrs.language,
            source_text: blockNodeToMarkdown(c.node),
          });
        }

        for (const d of deletes) {
          await api.deleteBlock(port, d.id);
        }
      }

      store.dispatch({ type: "editor-mark-saved", doc: currentDoc });

      // Refresh sidebar previews from the saved doc
      const items = [];
      currentDoc.forEach((blockNode) => {
        const md = blockNodeToMarkdown(blockNode);
        items.push({
          id: blockNode.attrs.id,
          block_type: blockNode.attrs.block_type,
          language: blockNode.attrs.language,
          source_text: md,
          title: previewText(md),
        });
      });
      store.dispatch({ type: "set-items", items });
    } catch (err) {
      store.dispatch({ type: "error", message: `Save failed: ${err.message}` });
    }
  }
});

async function saveAllBlocks(port, doc, sectionId) {
  const batch = [];
  doc.forEach((child) => {
    batch.push({
      id: child.attrs.id,
      source_text: blockNodeToMarkdown(child),
    });
  });
  if (batch.length > 0) {
    await api.saveBlocksBatch(port, batch);
  }
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

async function init() {
  try {
    const data = await invoke("get_picker_data");
    store.dispatch({ type: "set-picker-data", data });
  } catch (err) {
    store.dispatch({ type: "picker-error", message: `Failed to load: ${err}` });
  }
}

init();
