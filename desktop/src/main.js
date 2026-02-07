/**
 * main.js — Bootstrap, store wiring, navigation logic.
 *
 * Initializes the store, connects Tauri IPC for the sidecar port,
 * subscribes the renderer, and implements the navigation flow.
 */

import { initialState, reduce, createStore } from "./state.js";
import { render } from "./render.js";
import * as api from "./api.js";

const { invoke } = window.__TAURI__.core;

const store = createStore(reduce, initialState);

// ---------------------------------------------------------------------------
// Event handlers (passed to render functions)
// ---------------------------------------------------------------------------

const handlers = {
  onItemClick(item) {
    const state = store.getState();

    if (state.view === "entities") {
      store.dispatch({ type: "select-entity", id: item.id });
      loadEntityDetail(item.id);
      return;
    }

    // Outline navigation: drill down on click
    const level = currentLevel(state);

    if (level === "documents") {
      store.dispatch({ type: "push", element: { kind: "document", id: item.id, title: item.title } });
      loadLevel();
    } else if (level === "sections") {
      store.dispatch({ type: "push", element: { kind: "section", id: item.id, title: item.title } });
      loadLevel();
    } else if (level === "blocks") {
      // At block level, clicking selects (no deeper drill)
      store.dispatch({ type: "select", id: item.id });
    }
  },

  onBreadcrumbClick(depth) {
    store.dispatch({ type: "pop-to", depth });
    loadLevel();
  },

  onTabClick(view) {
    store.dispatch({ type: "set-view", view });
    if (view === "entities") {
      loadEntities();
    } else {
      loadLevel();
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
      // Root: load documents
      const docs = await api.fetchDocuments(port);
      store.dispatch({ type: "set-items", items: docs });
    } else {
      const last = state.path[state.path.length - 1];

      if (last.kind === "document") {
        const sections = await api.fetchSections(port, last.id);
        store.dispatch({ type: "set-items", items: sections });
      } else if (last.kind === "section") {
        // Load blocks for sidebar AND content area
        const blocks = await api.fetchBlocks(port, last.id);
        store.dispatch({ type: "set-items", items: blocks.map(b => ({
          ...b,
          title: (b.source_text || "").replace(/\n/g, " ").slice(0, 60),
        }))});
        store.dispatch({ type: "set-detail", detail: blocks });
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
// Subscribe renderer
// ---------------------------------------------------------------------------

store.subscribe((state) => {
  render(state, handlers);
});

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

async function init() {
  try {
    const port = await invoke("sidecar_port");
    store.dispatch({ type: "init", port });
    await loadLevel();
  } catch (err) {
    store.dispatch({ type: "error", message: `Sidecar error: ${err}` });
  }
}

init();
