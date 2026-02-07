/**
 * state.js — Elm-style state management for Littera desktop.
 *
 * Ported from tui/state.py's reducer pattern.
 * Pure functions: reduce(state, action) → newState.
 */

export const initialState = {
  view: "outline",        // "outline" | "entities"
  path: [],               // [{kind, id, title}, ...]
  items: [],              // current sidebar list items
  selectedId: null,
  detail: null,           // content area data
  entities: [],
  selectedEntityId: null,
  entityDetail: null,
  sidecarPort: null,
  loading: false,
  error: null,
  // Editor state
  editing: false,          // true when ProseMirror is active
  editorSectionId: null,   // section currently being edited
  savedDoc: null,          // ProseMirror doc at last save (for dirty tracking)
  dirty: false,            // unsaved changes exist
};

export function reduce(state, action) {
  switch (action.type) {
    case "init":
      return { ...state, sidecarPort: action.port };

    case "set-items":
      return { ...state, items: action.items, loading: false };

    case "select":
      return { ...state, selectedId: action.id };

    case "push":
      return {
        ...state,
        path: [...state.path, action.element],
        selectedId: null,
        items: [],
        detail: null,
        editing: false,
        editorSectionId: null,
        savedDoc: null,
        dirty: false,
      };

    case "pop": {
      const newPath = state.path.slice(0, -1);
      return {
        ...state,
        path: newPath,
        selectedId: null,
        items: [],
        detail: null,
        editing: false,
        editorSectionId: null,
        savedDoc: null,
        dirty: false,
      };
    }

    case "pop-to": {
      // Pop to a specific depth (breadcrumb click)
      const newPath = state.path.slice(0, action.depth);
      return {
        ...state,
        path: newPath,
        selectedId: null,
        items: [],
        detail: null,
        editing: false,
        editorSectionId: null,
        savedDoc: null,
        dirty: false,
      };
    }

    case "set-detail":
      return { ...state, detail: action.detail, loading: false };

    case "set-view":
      return { ...state, view: action.view };

    case "set-entities":
      return { ...state, entities: action.entities, loading: false };

    case "select-entity":
      return { ...state, selectedEntityId: action.id };

    case "set-entity-detail":
      return { ...state, entityDetail: action.detail, loading: false };

    case "loading":
      return { ...state, loading: true };

    case "error":
      return { ...state, error: action.message, loading: false };

    case "clear-error":
      return { ...state, error: null };

    case "editor-open":
      return {
        ...state,
        editing: true,
        editorSectionId: action.sectionId,
        savedDoc: action.doc,
        dirty: false,
      };

    case "editor-close":
      return {
        ...state,
        editing: false,
        editorSectionId: null,
        savedDoc: null,
        dirty: false,
      };

    case "editor-mark-dirty":
      return { ...state, dirty: true };

    case "editor-mark-saved":
      return { ...state, savedDoc: action.doc, dirty: false };

    default:
      return state;
  }
}

export function createStore(reducer, initial) {
  let state = initial;
  const listeners = [];
  return {
    getState: () => state,
    dispatch(action) {
      state = reducer(state, action);
      for (const fn of listeners) fn(state);
    },
    subscribe(fn) {
      listeners.push(fn);
      return () => {
        const idx = listeners.indexOf(fn);
        if (idx >= 0) listeners.splice(idx, 1);
      };
    },
  };
}
