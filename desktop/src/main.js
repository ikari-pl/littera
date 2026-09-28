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
import { showPrompt, showConfirm, showHelp, showToast, showPicker } from "./dialog.js";
import {
  createEditor,
  loadSection,
  findDirtyBlocks,
  blockNodeToMarkdown,
} from "./editor.bundle.js";

const { invoke } = window.__TAURI__.core;

const store = createStore(reduce, initialState);

// ---------------------------------------------------------------------------
// Error auto-dismiss timer
// ---------------------------------------------------------------------------

let errorDismissTimer = null;

function scheduleErrorDismiss(delay = 5000) {
  if (errorDismissTimer) clearTimeout(errorDismissTimer);
  errorDismissTimer = setTimeout(() => {
    store.dispatch({ type: "clear-error" });
    errorDismissTimer = null;
  }, delay);
}

// ---------------------------------------------------------------------------
// Retry wrapper for transient sidecar failures
// ---------------------------------------------------------------------------

async function withRetry(fn, retries = 2, delay = 1000) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const isTransient = isTransientError(err);
      if (attempt < retries && isTransient) {
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw err;
    }
  }
}

function isTransientError(err) {
  const msg = err.message || '';
  return msg.includes('Failed to fetch') ||
         msg.includes('NetworkError') ||
         msg.includes('ECONNREFUSED') ||
         msg.includes('HTTP 502') ||
         msg.includes('HTTP 503');
}

// ---------------------------------------------------------------------------
// Theme management
// ---------------------------------------------------------------------------

function applyTheme(theme) {
  if (theme === null) {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", prefersDark ? "dark" : "light");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
}

function saveThemePreference(theme) {
  if (theme === null) {
    localStorage.removeItem("littera-theme");
  } else {
    localStorage.setItem("littera-theme", theme);
  }
}

// Initialize theme from localStorage
const savedTheme = localStorage.getItem("littera-theme");
if (savedTheme) {
  store.dispatch({ type: "set-theme", theme: savedTheme });
}
applyTheme(savedTheme);

// Follow system preference changes when theme is set to "system" (null)
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  const state = store.getState();
  if (state.theme === null) applyTheme(null);
});

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

async function checkDirtyBeforeNav() {
  const state = store.getState();
  if (state.editing && state.dirty) {
    return showConfirm({
      title: "Unsaved changes",
      message: "You have unsaved changes. Discard them?",
    });
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

  async onRetryPicker() {
    store.dispatch({ type: "clear-error" });
    try {
      const data = await invoke("get_picker_data");
      store.dispatch({ type: "set-picker-data", data });
    } catch (err) {
      store.dispatch({ type: "picker-error", message: `Failed to load: ${err}` });
    }
  },
};

// ---------------------------------------------------------------------------
// Event handlers (passed to render functions)
// ---------------------------------------------------------------------------

const handlers = {
  // Picker handlers (merged in)
  ...pickerHandlers,

  // Dismiss error banner
  onDismissError() {
    if (errorDismissTimer) {
      clearTimeout(errorDismissTimer);
      errorDismissTimer = null;
    }
    store.dispatch({ type: "clear-error" });
  },

  // Command palette handlers
  onClosePalette() {
    store.dispatch({ type: "close-command-palette" });
  },

  onExecuteCommand(cmd) {
    store.dispatch({ type: "close-command-palette" });
    if (cmd.action) {
      cmd.action({ store, handlers, api });
    }
  },

  async onSwitchWork() {
    // Check for unsaved changes
    if (!(await checkDirtyBeforeNav())) return;

    // Close editor if active
    const state = store.getState();
    if (state.editing) {
      store.dispatch({ type: "editor-close" });
      if (editorView) {
        editorView.destroy();
        editorView = null;
        pendingBlocks = null;
      }
    }

    // Close the sidecar (stop Python + PG)
    try {
      await invoke("close_work");
    } catch (err) {
      console.warn("close_work failed:", err);
    }

    // Return to picker
    store.dispatch({ type: "return-to-picker" });

    // Refresh picker data (recents may have changed)
    try {
      const data = await invoke("get_picker_data");
      store.dispatch({ type: "set-picker-data", data });
    } catch (err) {
      store.dispatch({ type: "picker-error", message: `Failed to load: ${err}` });
    }
  },

  onThemeToggle() {
    const state = store.getState();
    // Cycle: system (null) → light → dark → system (null)
    let next;
    if (state.theme === null) next = "light";
    else if (state.theme === "light") next = "dark";
    else next = null;
    store.dispatch({ type: "set-theme", theme: next });
    applyTheme(next);
    saveThemePreference(next);
  },

  async onItemClick(item) {
    const state = store.getState();

    if (state.view === "entities") {
      if (!(await checkDirtyBeforeNav())) return;
      store.dispatch({ type: "select-entity", id: item.id });
      loadEntityDetail(item.id);
      return;
    }

    const level = currentLevel(state);

    if (level === "documents") {
      if (!(await checkDirtyBeforeNav())) return;
      store.dispatch({ type: "push", element: { kind: "document", id: item.id, title: item.title } });
      loadLevel();
    } else if (level === "sections") {
      if (!(await checkDirtyBeforeNav())) return;
      store.dispatch({ type: "push", element: { kind: "section", id: item.id, title: item.title } });
      loadLevel();
    } else if (level === "blocks") {
      store.dispatch({ type: "select", id: item.id });
    }
  },

  async onBreadcrumbClick(depth) {
    if (!(await checkDirtyBeforeNav())) return;
    // If viewing entities, switch back to outline before navigating
    const state = store.getState();
    if (state.view === "entities") {
      store.dispatch({ type: "set-view", view: "outline" });
    }
    store.dispatch({ type: "pop-to", depth });
    loadLevel();
  },

  async onTabClick(view) {
    if (!(await checkDirtyBeforeNav())) return;
    const state = store.getState();
    if (state.editing) {
      store.dispatch({ type: "editor-close" });
    }
    store.dispatch({ type: "set-view", view });
    if (view === "entities") {
      loadEntities();
    } else if (view === "alignments") {
      loadAlignments();
    } else if (view === "reviews") {
      loadReviews();
    } else {
      loadLevel();
    }
  },

  onStartRename(item) {
    store.dispatch({ type: "start-rename", id: item.id });
  },

  onCancelRename() {
    store.dispatch({ type: "stop-rename" });
  },

  async onRenameItem(item, newTitle) {
    store.dispatch({ type: "stop-rename" });
    if (!newTitle || newTitle === item.title) return;
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;
    const level = currentLevel(state);
    try {
      if (level === "documents") {
        await api.renameDocument(port, item.id, newTitle);
      } else if (level === "sections") {
        await api.renameSection(port, item.id, newTitle);
      }
      await loadLevel();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onAddItem() {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    const level = currentLevel(state);

    if (level === "documents") {
      const title = await showPrompt({ title: "New document", placeholder: "Document title" });
      if (!title) return;
      try {
        await api.createDocument(port, title);
        await loadLevel();
      } catch (err) {
        store.dispatch({ type: "error", message: err.message });
      }
    } else if (level === "sections") {
      const last = state.path[state.path.length - 1];
      const title = await showPrompt({ title: "New section", placeholder: "Section title" });
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
    const ok = await showConfirm({
      title: "Delete",
      message: `Delete "${label}"? This cannot be undone.`,
    });
    if (!ok) return;

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

    const entityType = await showPrompt({
      title: "New entity",
      message: "Entity type",
      defaultValue: "concept",
      placeholder: "e.g. concept, person, place",
    });
    if (!entityType) return;
    const label = await showPrompt({ title: "New entity", placeholder: "Entity name" });
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

    const ok = await showConfirm({
      title: "Delete entity",
      message: `Delete entity "${entity.label}"? This cannot be undone.`,
    });
    if (!ok) return;

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

    const ok = await showConfirm({
      title: "Delete mention",
      message:
        "Delete this mention? The text in the block will remain but the entity link will be removed.",
    });
    if (!ok) return;

    try {
      await api.deleteMention(port, mention.id);
      await loadEntityDetail(state.selectedEntityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  onStartAddLabel() {
    store.dispatch({ type: "start-add-label" });
  },

  onCancelAddLabel() {
    store.dispatch({ type: "stop-add-label" });
  },

  async onAddLabel(entityId, language, baseForm) {
    store.dispatch({ type: "stop-add-label" });
    if (!baseForm) return;
    const port = store.getState().sidecarPort;
    try {
      await api.addEntityLabel(port, entityId, language, baseForm, null);
      await loadEntityDetail(entityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onDeleteLabel(labelId) {
    const state = store.getState();
    const port = state.sidecarPort;
    try {
      await api.deleteLabel(port, labelId);
      await loadEntityDetail(state.selectedEntityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  onStartAddProperty() {
    store.dispatch({ type: "start-add-property" });
  },

  onCancelAddProperty() {
    store.dispatch({ type: "stop-add-property" });
  },

  async onAddProperty(entityId, key, value) {
    store.dispatch({ type: "stop-add-property" });
    if (!key || !value) return;
    const port = store.getState().sidecarPort;
    try {
      await api.setEntityProperties(port, entityId, { [key]: value });
      await loadEntityDetail(entityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onDeleteProperty(entityId, key) {
    const port = store.getState().sidecarPort;
    try {
      await api.deleteEntityProperty(port, entityId, key);
      await loadEntityDetail(entityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onEditEntityNote(entityId) {
    const state = store.getState();
    const port = state.sidecarPort;
    if (!port) return;

    const current = state.entityDetail?.note || "";
    const note = await showPrompt({
      title: "Entity note",
      defaultValue: current,
      placeholder: "Work-scoped note",
    });
    if (note === null) return;

    try {
      await api.saveEntityNote(port, entityId, note);
      await loadEntityDetail(entityId);
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onAddAlignment() {
    const port = store.getState().sidecarPort;
    if (!port) return;
    try {
      const blocks = await api.fetchBlocks(port);
      const options = (blocks || []).map((b) => ({
        id: b.id,
        label: `${b.document} \u203a ${b.section}: [${b.language}] ${b.preview || "(empty)"}`,
      }));
      const sourceId = await showPicker({
        title: "Align — source block",
        options,
        emptyText: "No blocks yet. Add writing first.",
      });
      if (!sourceId) return;
      const targetOptions = options.filter((o) => o.id !== sourceId);
      const targetId = await showPicker({
        title: "Align — target block",
        options: targetOptions,
        emptyText: "Need at least two blocks to align.",
      });
      if (!targetId) return;
      const type =
        (await showPrompt({
          title: "Alignment type",
          defaultValue: "translation",
          placeholder: "translation / adaptation / summary",
        })) || "translation";
      const result = await api.createAlignment(port, sourceId, targetId, type);
      if (result && result.error) {
        store.dispatch({ type: "error", message: result.error });
        return;
      }
      await loadAlignments();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onDeleteAlignment(alignmentId) {
    const port = store.getState().sidecarPort;
    if (!port) return;
    const ok = await showConfirm({
      title: "Delete alignment",
      message: "Delete this alignment? This cannot be undone.",
    });
    if (!ok) return;
    try {
      await api.deleteAlignment(port, alignmentId);
      await loadAlignments();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onShowAlignmentGaps() {
    const port = store.getState().sidecarPort;
    if (!port) return;
    try {
      const data = await api.fetchAlignmentGaps(port);
      store.dispatch({ type: "set-alignment-gaps", data });
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  onHideAlignmentGaps() {
    store.dispatch({ type: "clear-alignment-gaps" });
  },

  onOpenInflectDialog() {
    store.dispatch({ type: "open-inflect-dialog" });
  },

  onCloseInflectDialog() {
    store.dispatch({ type: "close-inflect-dialog" });
  },

  async onInflectWord(word, language, features) {
    const port = store.getState().sidecarPort;
    if (!port) return;
    try {
      const featureObj = {};
      if (features) {
        for (const f of features.split(",")) {
          const trimmed = f.trim();
          if (trimmed) featureObj[trimmed] = true;
        }
      }
      const data = await api.inflectWord(
        port,
        language,
        word,
        Object.keys(featureObj).length > 0 ? featureObj : null,
        null,
      );
      store.dispatch({ type: "set-inflect-result", result: data.result });
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onAddReview() {
    const port = store.getState().sidecarPort;
    if (!port) return;
    const description = await showPrompt({
      title: "New review",
      placeholder: "What needs attention?",
    });
    if (!description) return;
    const severity =
      (await showPrompt({
        title: "Severity",
        defaultValue: "medium",
        placeholder: "low / medium / high",
      })) || "medium";
    try {
      await api.createReview(port, description, { severity });
      await loadReviews();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onEditReview(reviewId) {
    const port = store.getState().sidecarPort;
    if (!port) return;
    const current = store.getState().reviews.find((r) => r.id === reviewId);
    const description = await showPrompt({
      title: "Edit review",
      defaultValue: current ? current.description : "",
      placeholder: "Description",
    });
    if (!description) return;
    const severity =
      (await showPrompt({
        title: "Severity",
        defaultValue: current ? current.severity || "medium" : "medium",
        placeholder: "low / medium / high",
      })) || "medium";
    try {
      const result = await api.updateReview(port, reviewId, { description, severity });
      if (result && result.error) {
        store.dispatch({ type: "error", message: result.error });
        return;
      }
      await loadReviews();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onDeleteReview(reviewId) {
    const port = store.getState().sidecarPort;
    if (!port) return;
    const ok = await showConfirm({
      title: "Delete review",
      message: "Delete this review?",
    });
    if (!ok) return;
    try {
      await api.deleteReview(port, reviewId);
      await loadReviews();
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  onShowHelp() {
    showHelp();
  },

  onZenEntered() {
    showToast("Cmd+Shift+F to exit distraction-free mode");
  },

  async onImportJSON() {
    const port = store.getState().sidecarPort;
    if (!port) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json,.json";
    input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        const ok = await showConfirm({
          title: "Import JSON",
          message: `Import "${file.name}" into this work? Existing data may be merged or overwritten depending on IDs.`,
        });
        if (!ok) return;
        await api.importJSON(port, data);
        showToast("Import complete");
        await loadLevel();
      } catch (err) {
        store.dispatch({ type: "error", message: err.message || String(err) });
      }
    });
    input.click();
  },

  async onSave() {
    await performSave();
  },

  async onExportJSON() {
    const port = store.getState().sidecarPort;
    if (!port) return;
    try {
      const data = await api.exportJSON(port);
      downloadText("export.json", JSON.stringify(data, null, 2), "application/json");
    } catch (err) {
      store.dispatch({ type: "error", message: err.message });
    }
  },

  async onExportMarkdown(compile) {
    const port = store.getState().sidecarPort;
    if (!port) return;
    try {
      const data = await api.exportMarkdown(port, { compile });
      const name = compile ? "manuscript.md" : "export.md";
      downloadText(name, data.markdown || "", "text/markdown");
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

function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function refreshWordCount() {
  const state = store.getState();
  const port = state.sidecarPort;
  if (!port) return;
  let documentId = null;
  let sectionId = null;
  let scope = "work";
  for (const elem of state.path) {
    if (elem.kind === "document") {
      documentId = elem.id;
      scope = "document";
    } else if (elem.kind === "section") {
      sectionId = elem.id;
      scope = "section";
    }
  }
  try {
    const stats = await api.fetchWordCount(port, { documentId, sectionId });
    store.dispatch({ type: "set-word-count", wordCount: { ...stats, scope } });
  } catch {
    // Word count is chrome, not a blocking load.
  }
}

async function loadLevel() {
  const state = store.getState();
  const port = state.sidecarPort;
  if (!port) return;

  store.dispatch({ type: "loading" });
  refreshWordCount();

  try {
    if (state.path.length === 0) {
      const docs = await withRetry(() => api.fetchDocuments(port));
      store.dispatch({ type: "set-items", items: docs });
    } else {
      const last = state.path[state.path.length - 1];

      if (last.kind === "document") {
        const sections = await withRetry(() => api.fetchSections(port, last.id));
        store.dispatch({ type: "set-items", items: sections });
      } else if (last.kind === "section") {
        const blocks = await withRetry(() => api.fetchBlocks(port, last.id));

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
    const entities = await withRetry(() => api.fetchEntities(port));
    store.dispatch({ type: "set-entities", entities });
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

async function loadEntityDetail(entityId) {
  const port = store.getState().sidecarPort;
  if (!port) return;

  try {
    const detail = await withRetry(() => api.fetchEntity(port, entityId));
    store.dispatch({ type: "set-entity-detail", detail });
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

async function loadAlignments() {
  const port = store.getState().sidecarPort;
  if (!port) return;
  store.dispatch({ type: "loading" });
  try {
    const alignments = await api.fetchAlignments(port);
    store.dispatch({ type: "set-alignments", alignments });
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

async function loadReviews() {
  const port = store.getState().sidecarPort;
  if (!port) return;
  store.dispatch({ type: "loading" });
  try {
    const reviews = await api.fetchReviews(port);
    store.dispatch({ type: "set-reviews", reviews });
  } catch (err) {
    store.dispatch({ type: "error", message: err.message });
  }
}

// ---------------------------------------------------------------------------
// Store subscriber — renders + manages editor lifecycle
// ---------------------------------------------------------------------------

store.subscribe((state) => {
  render(state, handlers);

  // Auto-dismiss errors after 5s
  if (state.error) {
    scheduleErrorDismiss();
  } else if (errorDismissTimer) {
    clearTimeout(errorDismissTimer);
    errorDismissTimer = null;
  }

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
  // Cmd+Shift+P: toggle command palette (Cmd+K stays for editor link)
  if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "p") {
    e.preventDefault();
    const state = store.getState();
    if (state.phase === "ready") {
      store.dispatch({
        type: state.commandPaletteOpen ? "close-command-palette" : "open-command-palette",
      });
    }
    return;
  }

  // Cmd+/ or bare "?" (when not typing): show help
  const helpChord = (e.metaKey || e.ctrlKey) && e.key === "/";
  const helpQuestion =
    e.key === "?" &&
    !e.metaKey &&
    !e.ctrlKey &&
    !e.altKey &&
    !isTypingTarget(e.target);
  if (helpChord || helpQuestion) {
    e.preventDefault();
    e.stopPropagation();
    const open = document.querySelector(".help-dialog-backdrop");
    if (open) {
      open.remove();
    } else if (store.getState().phase === "ready") {
      showHelp();
    }
    return;
  }

  // Cmd+Shift+F: toggle zen mode (only while editing)
  if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "f") {
    e.preventDefault();
    const state = store.getState();
    if (state.editing) {
      const entering = !state.zenMode;
      store.dispatch({ type: "toggle-zen" });
      if (entering) {
        showToast("Cmd+Shift+F to exit distraction-free mode");
      }
    }
    return;
  }

  if ((e.metaKey || e.ctrlKey) && e.key === "s") {
    e.preventDefault();
    await performSave();
  }
});

function isTypingTarget(el) {
  if (!el || el === document.body) return false;
  const tag = (el.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  if (el.closest && el.closest(".ProseMirror")) return true;
  return false;
}

async function performSave() {
  const state = store.getState();
  if (!state.editing || !state.dirty || !editorView) return;

  const port = state.sidecarPort;
  const savedDoc = state.savedDoc;
  const currentDoc = editorView.state.doc;

  try {
    if (!savedDoc) {
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
    refreshWordCount();

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
    const errMsg = isTransientError(err)
      ? "Save failed \u2014 connection lost. Try again with Cmd+S."
      : `Save failed: ${err.message}`;
    store.dispatch({ type: "error", message: errMsg });
  }
}

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
