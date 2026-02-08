/**
 * render.js — Pure DOM rendering functions.
 *
 * Each function takes state (or a slice of it) and updates the DOM.
 * No fetches, no side effects beyond DOM mutation.
 */

import { commands } from "./commands.js";

// ---------------------------------------------------------------------------
// Main render entry point — branches on phase
// ---------------------------------------------------------------------------

export function render(state, handlers) {
  if (state.phase === "picker") {
    renderPicker(state, handlers);
    return;
  }

  if (state.phase === "loading") {
    renderLoading();
    return;
  }

  // phase === "ready"
  ensureAppLayout();
  renderBreadcrumb(state, handlers);
  renderTabs(state, handlers);
  renderSidebar(state, handlers);
  renderContent(state, handlers);
  renderError(state, handlers);
  renderCommandPalette(state, handlers);
  renderInflectDialog(state, handlers);
  renderThemeToggle(state, handlers);

  // Bind switch-work button
  const switchBtn = document.getElementById("switch-work-btn");
  if (switchBtn && handlers.onSwitchWork) {
    switchBtn.onclick = () => handlers.onSwitchWork();
  }

  // Zen mode: toggle class on #app to hide sidebar/chrome via CSS
  const app = document.getElementById("app");
  app.classList.toggle("zen-mode", state.zenMode);
}

// ---------------------------------------------------------------------------
// Picker screen
// ---------------------------------------------------------------------------

function renderPicker(state, handlers) {
  const app = document.getElementById("app");

  // Only rebuild if picker isn't already rendered
  if (!app.querySelector("#picker")) {
    app.innerHTML = "";
    const picker = document.createElement("div");
    picker.id = "picker";
    app.appendChild(picker);
  }

  const picker = app.querySelector("#picker");
  picker.innerHTML = "";

  // Header
  const header = document.createElement("div");
  header.className = "picker-header";
  header.innerHTML = `<h1>Littera</h1><p>Select a work to open</p>`;
  picker.appendChild(header);

  // Error banner
  if (state.pickerError) {
    const err = document.createElement("div");
    err.className = "picker-error";

    const errText = document.createElement("span");
    errText.textContent = state.pickerError;
    err.appendChild(errText);

    if (handlers && handlers.onRetryPicker) {
      const retryBtn = document.createElement("button");
      retryBtn.className = "picker-error-retry";
      retryBtn.textContent = "Try Again";
      retryBtn.addEventListener("click", () => handlers.onRetryPicker());
      err.appendChild(retryBtn);
    }

    picker.appendChild(err);
  }

  // Action buttons
  const actions = document.createElement("div");
  actions.className = "picker-actions";

  const openBtn = document.createElement("button");
  openBtn.className = "picker-btn";
  openBtn.textContent = "Open Work\u2026";
  openBtn.addEventListener("click", () => handlers.onBrowseWork());
  actions.appendChild(openBtn);

  const newBtn = document.createElement("button");
  newBtn.className = "picker-btn picker-btn-secondary";
  newBtn.textContent = "New Work\u2026";
  newBtn.addEventListener("click", () => handlers.onNewWork());
  actions.appendChild(newBtn);

  picker.appendChild(actions);

  // Recent works
  const data = state.pickerData;
  if (data && data.recent && data.recent.length > 0) {
    const section = document.createElement("div");
    section.className = "picker-section";

    const h2 = document.createElement("h2");
    h2.textContent = "Recent Works";
    section.appendChild(h2);

    const list = document.createElement("ul");
    list.className = "picker-list";

    for (const work of data.recent) {
      const li = document.createElement("li");
      li.className = "picker-work-item";
      li.addEventListener("click", () => handlers.onSelectWork(work.path));

      const name = document.createElement("span");
      name.className = "picker-work-name";
      name.textContent = work.name;
      li.appendChild(name);

      const path = document.createElement("span");
      path.className = "picker-work-path";
      path.textContent = work.path;
      li.appendChild(path);

      list.appendChild(li);
    }
    section.appendChild(list);
    picker.appendChild(section);
  }

  // Workspace works
  if (data && data.workspace_works && data.workspace_works.length > 0) {
    const section = document.createElement("div");
    section.className = "picker-section";

    const h2 = document.createElement("h2");
    h2.textContent = "Workspace";
    section.appendChild(h2);

    const list = document.createElement("ul");
    list.className = "picker-list";

    for (const work of data.workspace_works) {
      const li = document.createElement("li");
      li.className = "picker-work-item";
      li.addEventListener("click", () => handlers.onSelectWork(work.path));

      const name = document.createElement("span");
      name.className = "picker-work-name";
      name.textContent = work.name;
      li.appendChild(name);

      const path = document.createElement("span");
      path.className = "picker-work-path";
      path.textContent = work.path;
      li.appendChild(path);

      list.appendChild(li);
    }
    section.appendChild(list);
    picker.appendChild(section);
  }

  // Workspace config footer
  const footer = document.createElement("div");
  footer.className = "picker-workspace-config";

  if (data && data.workspace) {
    const wsPath = document.createElement("span");
    wsPath.className = "picker-work-path";
    wsPath.textContent = data.workspace;
    footer.appendChild(wsPath);
  }

  const wsBtn = document.createElement("button");
  wsBtn.className = "picker-btn-link";
  wsBtn.textContent = data && data.workspace ? "Change Workspace" : "Set Workspace";
  wsBtn.addEventListener("click", () => handlers.onSetWorkspace());
  footer.appendChild(wsBtn);

  picker.appendChild(footer);
}

// ---------------------------------------------------------------------------
// Loading screen
// ---------------------------------------------------------------------------

function renderLoading() {
  const app = document.getElementById("app");

  if (!app.querySelector("#picker-loading")) {
    app.innerHTML = "";
    const loading = document.createElement("div");
    loading.id = "picker-loading";
    loading.innerHTML =
      `<h1>Littera</h1>` +
      `<p>Starting work database\u2026</p>` +
      `<div class="picker-spinner"></div>` +
      `<p class="picker-loading-hint">This may take a moment on first launch</p>`;
    app.appendChild(loading);
  }
}

// ---------------------------------------------------------------------------
// Ensure app layout (sidebar + content) exists for ready phase
// ---------------------------------------------------------------------------

function ensureAppLayout() {
  const app = document.getElementById("app");
  if (app.querySelector("#sidebar")) return; // already built

  app.innerHTML = `
    <aside id="sidebar">
      <div id="sidebar-header">
        <h1>Littera</h1>
        <div id="sidebar-header-actions">
          <button id="switch-work-btn" title="Switch work">\u21c4</button>
          <button id="theme-toggle">auto</button>
        </div>
      </div>
      <nav id="breadcrumb"></nav>
      <div id="sidebar-actions"></div>
      <ul id="sidebar-list"></ul>
      <div id="tab-bar">
        <button id="tab-outline" class="tab tab-active">Outline</button>
        <button id="tab-entities" class="tab">Entities</button>
        <button id="tab-alignments" class="tab">Align</button>
        <button id="tab-reviews" class="tab">Reviews</button>
      </div>
    </aside>
    <main id="content">
      <div class="content-placeholder">Loading\u2026</div>
    </main>
  `;
}

// ---------------------------------------------------------------------------
// Breadcrumb
// ---------------------------------------------------------------------------

function renderBreadcrumb(state, handlers) {
  const el = document.getElementById("breadcrumb");
  el.innerHTML = "";

  // Root
  const root = document.createElement("span");
  root.className = "breadcrumb-item breadcrumb-clickable";
  root.textContent = "Work";
  root.addEventListener("click", () => handlers.onBreadcrumbClick(0));
  el.appendChild(root);

  for (let i = 0; i < state.path.length; i++) {
    const sep = document.createElement("span");
    sep.className = "breadcrumb-sep";
    sep.textContent = " \u203a ";
    el.appendChild(sep);

    const crumb = document.createElement("span");
    crumb.textContent = state.path[i].title || "(untitled)";

    if (i < state.path.length - 1) {
      crumb.className = "breadcrumb-item breadcrumb-clickable";
      const depth = i + 1;
      crumb.addEventListener("click", () => handlers.onBreadcrumbClick(depth));
    } else {
      crumb.className = "breadcrumb-item breadcrumb-current";
    }
    el.appendChild(crumb);
  }
}

// ---------------------------------------------------------------------------
// Tabs (Outline | Entities)
// ---------------------------------------------------------------------------

function renderTabs(state, handlers) {
  const tabs = ["outline", "entities", "alignments", "reviews"];
  for (const t of tabs) {
    const el = document.getElementById(`tab-${t}`);
    if (el) {
      el.classList.toggle("tab-active", state.view === t);
      el.onclick = () => handlers.onTabClick(t);
    }
  }
}

// ---------------------------------------------------------------------------
// Sidebar item list
// ---------------------------------------------------------------------------

function renderSidebarActions(state, handlers) {
  const el = document.getElementById("sidebar-actions");
  if (!el) return;
  el.innerHTML = "";

  if (state.view === "alignments" || state.view === "reviews") {
    // No sidebar actions for alignment/review views
  } else if (state.view === "entities") {
    const addBtn = document.createElement("button");
    addBtn.className = "sidebar-action-btn";
    addBtn.textContent = "+";
    addBtn.title = "Add entity";
    addBtn.addEventListener("click", () => handlers.onAddEntity());
    el.appendChild(addBtn);
  } else if (!state.editing) {
    const level = currentLevel(state);
    if (level === "documents" || level === "sections") {
      const addBtn = document.createElement("button");
      addBtn.className = "sidebar-action-btn";
      addBtn.textContent = "+";
      addBtn.title = level === "documents" ? "Add document" : "Add section";
      addBtn.addEventListener("click", () => handlers.onAddItem());
      el.appendChild(addBtn);
    }
  }
}

function renderSidebar(state, handlers) {
  const el = document.getElementById("sidebar-list");
  el.innerHTML = "";

  renderSidebarActions(state, handlers);

  if (state.loading) {
    for (let i = 0; i < 5; i++) {
      const li = document.createElement("li");
      li.className = "skeleton skeleton-sidebar-item";
      el.appendChild(li);
    }
    return;
  }

  const items = state.view === "entities" ? state.entities : state.items;
  const selectedId = state.view === "entities" ? state.selectedEntityId : state.selectedId;

  if (items.length === 0) {
    const li = document.createElement("li");
    li.className = "sidebar-empty";
    li.textContent = state.view === "entities" ? "No entities" : "No items";
    el.appendChild(li);
    return;
  }

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "sidebar-item";
    if (item.id === selectedId) li.classList.add("selected");

    if (state.view === "entities") {
      const badge = document.createElement("span");
      badge.className = "entity-badge";
      badge.textContent = item.entity_type;
      li.appendChild(badge);

      const label = document.createElement("span");
      label.textContent = item.label;
      li.appendChild(label);
    } else if (item.id === state.editingItemId) {
      // Inline rename input
      const input = document.createElement("input");
      input.type = "text";
      input.className = "sidebar-rename-input";
      input.value = item.title || "";
      let cancelled = false;
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          handlers.onRenameItem(item, input.value);
        } else if (e.key === "Escape") {
          e.preventDefault();
          cancelled = true;
          handlers.onCancelRename();
        }
      });
      input.addEventListener("blur", () => {
        if (!cancelled) {
          handlers.onRenameItem(item, input.value);
        }
      });
      li.appendChild(input);
      // Auto-focus after DOM insertion
      requestAnimationFrame(() => {
        input.focus();
        input.select();
      });
    } else {
      const titleSpan = document.createElement("span");
      titleSpan.className = "sidebar-item-title";
      titleSpan.textContent = item.title || "(untitled)";
      titleSpan.addEventListener("dblclick", (e) => {
        e.stopPropagation();
        handlers.onStartRename(item);
      });
      li.appendChild(titleSpan);
      if (item.language) {
        const badge = document.createElement("span");
        badge.className = "lang-badge";
        badge.textContent = item.language;
        li.insertBefore(badge, li.firstChild);
      }
    }

    // Delete button
    if (state.view === "entities") {
      const delBtn = document.createElement("button");
      delBtn.className = "sidebar-delete-btn";
      delBtn.textContent = "\u00d7";
      delBtn.title = "Delete";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        handlers.onDeleteEntity(item);
      });
      li.appendChild(delBtn);
    } else if (!state.editing) {
      const delBtn = document.createElement("button");
      delBtn.className = "sidebar-delete-btn";
      delBtn.textContent = "\u00d7";
      delBtn.title = "Delete";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        handlers.onDeleteItem(item);
      });
      li.appendChild(delBtn);
    }

    li.addEventListener("click", () => handlers.onItemClick(item));
    el.appendChild(li);
  }
}

// ---------------------------------------------------------------------------
// Content area
// ---------------------------------------------------------------------------

function renderContent(state, handlers) {
  const el = document.getElementById("content");

  // When editing, ProseMirror owns the #content area — don't touch it
  if (state.editing) {
    // Ensure the editor container exists
    if (!el.querySelector("#prosemirror-editor")) {
      el.innerHTML = "";
      const editorDiv = document.createElement("div");
      editorDiv.id = "prosemirror-editor";
      el.appendChild(editorDiv);
    }
    // Render dirty indicator
    renderDirtyIndicator(el, state.dirty);
    return;
  }

  // Not editing — remove dirty indicator if present
  const indicator = el.querySelector(".dirty-indicator");
  if (indicator) indicator.remove();

  if (state.loading) {
    el.innerHTML = '';
    if (state.view === 'entities') {
      const header = document.createElement('div');
      header.className = 'skeleton-entity-header';
      header.innerHTML = '<div class="skeleton skeleton-badge"></div><div class="skeleton skeleton-title"></div>';
      el.appendChild(header);
      for (let i = 0; i < 3; i++) {
        const line = document.createElement('div');
        line.className = 'skeleton skeleton-text' + (i === 2 ? ' skeleton-text-short' : '');
        el.appendChild(line);
      }
    } else {
      for (let i = 0; i < 3; i++) {
        const block = document.createElement('div');
        block.className = 'skeleton skeleton-block';
        el.appendChild(block);
      }
    }
    return;
  }

  // Entity detail view
  if (state.view === "entities" && state.entityDetail) {
    const detailWithId = { ...state.entityDetail, _entityId: state.selectedEntityId, _addingLabel: state.addingLabel, _addingProperty: state.addingProperty };
    renderEntityDetail(el, detailWithId, handlers);
    return;
  }

  // Alignment list view
  if (state.view === "alignments") {
    renderAlignmentList(el, state, handlers);
    return;
  }

  // Review list view
  if (state.view === "reviews") {
    renderReviewList(el, state, handlers);
    return;
  }

  // Section blocks view (when path ends at a section)
  if (state.detail && Array.isArray(state.detail)) {
    renderBlocks(el, state.detail);
    return;
  }

  // Default placeholder
  const level = currentLevel(state);
  let hint = "Select an item to view";
  if (level === "documents") hint = "Select a document to browse its sections";
  else if (level === "sections") hint = "Select a section to view its content";

  el.innerHTML = `<div class="content-placeholder">${hint}</div>`;
}

function renderDirtyIndicator(container, dirty) {
  let indicator = container.querySelector(".dirty-indicator");
  if (dirty) {
    if (!indicator) {
      indicator = document.createElement("div");
      indicator.className = "dirty-indicator";
      indicator.textContent = "Unsaved changes";
      container.appendChild(indicator);
    }
  } else if (indicator) {
    indicator.remove();
  }
}

function currentLevel(state) {
  if (state.path.length === 0) return "documents";
  const last = state.path[state.path.length - 1];
  if (last.kind === "document") return "sections";
  if (last.kind === "section") return "blocks";
  return "documents";
}

// ---------------------------------------------------------------------------
// Block rendering (basic Markdown-like formatting)
// ---------------------------------------------------------------------------

function renderBlocks(el, blocks) {
  el.innerHTML = "";

  if (blocks.length === 0) {
    el.innerHTML = '<div class="content-placeholder">No blocks in this section</div>';
    return;
  }

  for (const block of blocks) {
    const blockEl = document.createElement("div");
    blockEl.className = "block";

    if (block.language && block.language !== "en") {
      const langTag = document.createElement("div");
      langTag.className = "block-lang";
      langTag.textContent = block.language;
      blockEl.appendChild(langTag);
    }

    const textEl = document.createElement("div");
    textEl.className = "block-text";
    textEl.innerHTML = formatText(block.source_text || "");
    blockEl.appendChild(textEl);

    el.appendChild(blockEl);
  }
}

function formatText(text) {
  // Split into paragraphs on double newlines
  const paragraphs = text.split(/\n{2,}/);
  return paragraphs
    .map((p) => {
      const trimmed = p.trim();
      if (!trimmed) return "";

      // Headings
      const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/m);
      if (headingMatch) {
        const level = headingMatch[1].length;
        return `<h${level + 1}>${escapeHtml(headingMatch[2])}</h${level + 1}>`;
      }

      // Inline formatting then wrap in <p>
      return `<p>${inlineFormat(trimmed)}</p>`;
    })
    .join("\n");
}

function inlineFormat(text) {
  let html = escapeHtml(text);
  // Bold: **text**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic: *text*
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Line breaks within a paragraph
  html = html.replace(/\n/g, "<br>");
  return html;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Entity detail
// ---------------------------------------------------------------------------

function renderEntityDetail(el, detail, handlers) {
  el.innerHTML = "";

  const header = document.createElement("div");
  header.className = "entity-header";

  const badge = document.createElement("span");
  badge.className = "entity-badge entity-badge-lg";
  badge.textContent = detail.entity_type;
  header.appendChild(badge);

  const name = document.createElement("h2");
  name.textContent = detail.label;
  header.appendChild(name);

  el.appendChild(header);

  // Labels
  {
    const section = document.createElement("div");
    section.className = "entity-section";

    const labelHeader = document.createElement("div");
    labelHeader.className = "entity-section-header";
    const labelH3 = document.createElement("h3");
    labelH3.textContent = "Labels";
    labelHeader.appendChild(labelH3);

    if (handlers && handlers.onStartAddLabel) {
      const addBtn = document.createElement("button");
      addBtn.className = "entity-action-btn";
      addBtn.textContent = "Add";
      addBtn.addEventListener("click", () => handlers.onStartAddLabel());
      labelHeader.appendChild(addBtn);
    }
    section.appendChild(labelHeader);

    if (detail.labels && detail.labels.length > 0) {
      for (const label of detail.labels) {
        const row = document.createElement("div");
        row.className = "entity-label-row";

        const langBadge = document.createElement("span");
        langBadge.className = "lang-badge";
        langBadge.textContent = label.language;
        row.appendChild(langBadge);

        const text = document.createTextNode(" " + label.base_form);
        row.appendChild(text);

        if (label.aliases) {
          const aliasSpan = document.createElement("span");
          aliasSpan.className = "entity-aliases";
          aliasSpan.textContent = " (" + label.aliases + ")";
          row.appendChild(aliasSpan);
        }

        if (handlers && handlers.onDeleteLabel) {
          const delBtn = document.createElement("button");
          delBtn.className = "entity-label-delete-btn";
          delBtn.textContent = "\u00d7";
          delBtn.title = "Delete label";
          delBtn.addEventListener("click", () => handlers.onDeleteLabel(label.id));
          row.appendChild(delBtn);
        }

        section.appendChild(row);
      }
    }

    // Inline add row
    if (detail._addingLabel) {
      const addRow = document.createElement("div");
      addRow.className = "entity-label-add-row";

      const langSelect = document.createElement("select");
      langSelect.className = "entity-label-lang-select";
      for (const lang of ["en", "ja", "fr", "de", "es", "it", "pt", "zh", "ko", "ru"]) {
        const opt = document.createElement("option");
        opt.value = lang;
        opt.textContent = lang;
        langSelect.appendChild(opt);
      }
      addRow.appendChild(langSelect);

      const input = document.createElement("input");
      input.type = "text";
      input.className = "entity-label-add-input";
      input.placeholder = "Base form\u2026";

      let cancelled = false;
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          if (handlers.onAddLabel) {
            handlers.onAddLabel(detail._entityId, langSelect.value, input.value.trim());
          }
        } else if (e.key === "Escape") {
          e.preventDefault();
          cancelled = true;
          if (handlers.onCancelAddLabel) {
            handlers.onCancelAddLabel();
          }
        }
      });
      input.addEventListener("blur", () => {
        if (!cancelled && !input.value.trim()) {
          if (handlers.onCancelAddLabel) {
            handlers.onCancelAddLabel();
          }
        }
      });
      addRow.appendChild(input);

      section.appendChild(addRow);

      // Auto-focus after DOM insertion
      requestAnimationFrame(() => input.focus());
    }

    el.appendChild(section);
  }

  // Properties
  {
    const section = document.createElement("div");
    section.className = "entity-section";

    const propHeader = document.createElement("div");
    propHeader.className = "entity-section-header";
    const propH3 = document.createElement("h3");
    propH3.textContent = "Properties";
    propHeader.appendChild(propH3);

    if (handlers && handlers.onStartAddProperty) {
      const addBtn = document.createElement("button");
      addBtn.className = "entity-action-btn";
      addBtn.textContent = "Add";
      addBtn.addEventListener("click", () => handlers.onStartAddProperty());
      propHeader.appendChild(addBtn);
    }
    section.appendChild(propHeader);

    const props = detail.properties || {};
    const keys = Object.keys(props);

    if (keys.length > 0) {
      for (const key of keys) {
        const row = document.createElement("div");
        row.className = "entity-property-row";

        const keyBadge = document.createElement("span");
        keyBadge.className = "entity-property-key";
        keyBadge.textContent = key;
        row.appendChild(keyBadge);

        const valueSpan = document.createElement("span");
        valueSpan.className = "entity-property-value";
        valueSpan.textContent = props[key];
        row.appendChild(valueSpan);

        if (handlers && handlers.onDeleteProperty) {
          const delBtn = document.createElement("button");
          delBtn.className = "entity-property-delete-btn";
          delBtn.textContent = "\u00d7";
          delBtn.title = "Delete property";
          delBtn.addEventListener("click", () => handlers.onDeleteProperty(detail._entityId, key));
          row.appendChild(delBtn);
        }

        section.appendChild(row);
      }
    } else if (!detail._addingProperty) {
      const empty = document.createElement("p");
      empty.className = "entity-note-empty";
      empty.textContent = "(no properties)";
      section.appendChild(empty);
    }

    // Inline add row
    if (detail._addingProperty) {
      const addRow = document.createElement("div");
      addRow.className = "entity-property-add-row";

      const keyInput = document.createElement("input");
      keyInput.type = "text";
      keyInput.className = "entity-property-add-input";
      keyInput.placeholder = "Key\u2026";
      keyInput.style.maxWidth = "120px";

      const valueInput = document.createElement("input");
      valueInput.type = "text";
      valueInput.className = "entity-property-add-input";
      valueInput.placeholder = "Value\u2026";

      let cancelled = false;

      function handleSave() {
        const k = keyInput.value.trim();
        const v = valueInput.value.trim();
        if (handlers.onAddProperty) {
          handlers.onAddProperty(detail._entityId, k, v);
        }
      }

      function handleCancel() {
        cancelled = true;
        if (handlers.onCancelAddProperty) {
          handlers.onCancelAddProperty();
        }
      }

      function onKeydown(e) {
        if (e.key === "Enter") {
          e.preventDefault();
          handleSave();
        } else if (e.key === "Escape") {
          e.preventDefault();
          handleCancel();
        }
      }

      keyInput.addEventListener("keydown", onKeydown);
      valueInput.addEventListener("keydown", onKeydown);

      // Cancel on blur if both empty
      valueInput.addEventListener("blur", () => {
        setTimeout(() => {
          if (!cancelled && !keyInput.value.trim() && !valueInput.value.trim()) {
            // Check if focus is still within the add row
            if (!addRow.contains(document.activeElement)) {
              handleCancel();
            }
          }
        }, 100);
      });

      keyInput.addEventListener("blur", () => {
        setTimeout(() => {
          if (!cancelled && !keyInput.value.trim() && !valueInput.value.trim()) {
            if (!addRow.contains(document.activeElement)) {
              handleCancel();
            }
          }
        }, 100);
      });

      addRow.appendChild(keyInput);
      addRow.appendChild(valueInput);
      section.appendChild(addRow);

      requestAnimationFrame(() => keyInput.focus());
    }

    el.appendChild(section);
  }

  // Note
  const noteSection = document.createElement("div");
  noteSection.className = "entity-section";

  const noteHeader = document.createElement("div");
  noteHeader.className = "entity-section-header";
  const noteH3 = document.createElement("h3");
  noteH3.textContent = "Note";
  noteHeader.appendChild(noteH3);

  if (handlers && handlers.onEditEntityNote) {
    const editBtn = document.createElement("button");
    editBtn.className = "entity-action-btn";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", () => handlers.onEditEntityNote(detail._entityId));
    noteHeader.appendChild(editBtn);
  }
  noteSection.appendChild(noteHeader);

  const noteText = document.createElement("p");
  noteText.className = detail.note ? "entity-note" : "entity-note entity-note-empty";
  noteText.textContent = detail.note || "(no note)";
  noteSection.appendChild(noteText);
  el.appendChild(noteSection);

  // Mentions
  if (detail.mentions && detail.mentions.length > 0) {
    const section = document.createElement("div");
    section.className = "entity-section";

    const mentionH3 = document.createElement("h3");
    mentionH3.textContent = `Mentions (${detail.mentions.length})`;
    section.appendChild(mentionH3);

    for (const m of detail.mentions) {
      const row = document.createElement("div");
      row.className = "mention-row";

      const info = document.createElement("div");
      info.className = "mention-info";
      info.innerHTML =
        `<span class="mention-path">${escapeHtml(m.document)} / ${escapeHtml(m.section)}</span>` +
        ` <span class="lang-badge">${escapeHtml(m.language)}</span>` +
        `<div class="mention-preview">${escapeHtml(m.preview)}</div>`;
      row.appendChild(info);

      if (handlers && handlers.onDeleteMention) {
        const delBtn = document.createElement("button");
        delBtn.className = "mention-delete-btn";
        delBtn.textContent = "\u00d7";
        delBtn.title = "Delete mention";
        delBtn.addEventListener("click", () => handlers.onDeleteMention(m));
        row.appendChild(delBtn);
      }

      section.appendChild(row);
    }
    el.appendChild(section);
  }
}

// ---------------------------------------------------------------------------
// Alignment list
// ---------------------------------------------------------------------------

function renderAlignmentList(el, state, handlers) {
  el.innerHTML = "";

  const header = document.createElement("div");
  header.className = "entity-section-header";
  const h2 = document.createElement("h2");
  h2.textContent = "Block Alignments";
  h2.style.fontSize = "1.2rem";
  h2.style.fontWeight = "500";
  header.appendChild(h2);

  if (handlers && handlers.onShowAlignmentGaps) {
    const gapBtn = document.createElement("button");
    gapBtn.className = "entity-action-btn";
    gapBtn.textContent = state.alignmentGaps ? "Hide Gaps" : "Show Gaps";
    gapBtn.addEventListener("click", () => {
      if (state.alignmentGaps) {
        handlers.onHideAlignmentGaps();
      } else {
        handlers.onShowAlignmentGaps();
      }
    });
    header.appendChild(gapBtn);
  }

  el.appendChild(header);

  // Gap results panel
  if (state.alignmentGaps) {
    renderAlignmentGaps(el, state.alignmentGaps);
  }

  if (state.loading) {
    el.innerHTML += '<div class="content-placeholder">Loading\u2026</div>';
    return;
  }

  if (state.alignments.length === 0) {
    const empty = document.createElement("p");
    empty.className = "entity-note-empty";
    empty.textContent = "No alignments yet. Create alignments via the CLI: littera alignment add <source> <target>";
    el.appendChild(empty);
    return;
  }

  for (const a of state.alignments) {
    const row = document.createElement("div");
    row.className = "alignment-row";

    const source = document.createElement("div");
    source.className = "alignment-block";
    source.innerHTML = `<span class="lang-badge">${escapeHtml(a.source.language)}</span> ${escapeHtml(a.source.preview)}`;
    row.appendChild(source);

    const arrow = document.createElement("span");
    arrow.className = "alignment-arrow";
    arrow.textContent = "\u2194";
    row.appendChild(arrow);

    const target = document.createElement("div");
    target.className = "alignment-block";
    target.innerHTML = `<span class="lang-badge">${escapeHtml(a.target.language)}</span> ${escapeHtml(a.target.preview)}`;
    row.appendChild(target);

    const typeBadge = document.createElement("span");
    typeBadge.className = "entity-badge";
    typeBadge.textContent = a.alignment_type || "translation";
    row.appendChild(typeBadge);

    if (handlers && handlers.onDeleteAlignment) {
      const delBtn = document.createElement("button");
      delBtn.className = "alignment-delete-btn";
      delBtn.textContent = "\u00d7";
      delBtn.title = "Delete alignment";
      delBtn.addEventListener("click", () => handlers.onDeleteAlignment(a.id));
      row.appendChild(delBtn);
    }

    el.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// Alignment gap results
// ---------------------------------------------------------------------------

function renderAlignmentGaps(el, data) {
  const panel = document.createElement("div");
  panel.className = "alignment-gaps-panel";

  const summary = document.createElement("div");
  summary.className = "alignment-gaps-summary";
  summary.textContent = `${data.total} gap(s) found across ${data.checked} alignment(s)`;
  panel.appendChild(summary);

  if (data.gaps.length === 0) {
    const noGaps = document.createElement("p");
    noGaps.className = "entity-note-empty";
    noGaps.textContent = "No gaps found. All entities have labels in both aligned languages.";
    panel.appendChild(noGaps);
  } else {
    for (const gap of data.gaps) {
      const row = document.createElement("div");
      row.className = "alignment-gap-row";

      const typeBadge = document.createElement("span");
      typeBadge.className = "entity-badge";
      typeBadge.textContent = gap.entity_type;
      row.appendChild(typeBadge);

      const name = document.createElement("span");
      name.className = "alignment-gap-name";
      name.textContent = gap.canonical_label;
      row.appendChild(name);

      const detail = document.createElement("span");
      detail.className = "alignment-gap-detail";
      detail.textContent = `has ${gap.has_language}, missing ${gap.missing_language}`;
      row.appendChild(detail);

      panel.appendChild(row);
    }
  }

  el.appendChild(panel);
}

// ---------------------------------------------------------------------------
// Inflect dialog
// ---------------------------------------------------------------------------

function renderInflectDialog(state, handlers) {
  const existing = document.querySelector(".inflect-dialog-backdrop");

  if (!state.inflectDialogOpen) {
    if (existing) existing.remove();
    return;
  }

  let backdrop = existing;
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "inflect-dialog-backdrop";
    backdrop.addEventListener("mousedown", (e) => {
      if (e.target === backdrop) {
        handlers.onCloseInflectDialog();
      }
    });
    document.body.appendChild(backdrop);
  }

  backdrop.innerHTML = "";

  const dialog = document.createElement("div");
  dialog.className = "inflect-dialog";

  const title = document.createElement("h3");
  title.className = "inflect-dialog-title";
  title.textContent = "Inflect Word";
  dialog.appendChild(title);

  // Word input
  const wordGroup = document.createElement("div");
  wordGroup.className = "inflect-dialog-group";
  const wordLabel = document.createElement("label");
  wordLabel.textContent = "Word";
  wordGroup.appendChild(wordLabel);
  const wordInput = document.createElement("input");
  wordInput.type = "text";
  wordInput.className = "inflect-dialog-input";
  wordInput.placeholder = "e.g. cat";
  wordInput.id = "inflect-word-input";
  wordGroup.appendChild(wordInput);
  dialog.appendChild(wordGroup);

  // Language select
  const langGroup = document.createElement("div");
  langGroup.className = "inflect-dialog-group";
  const langLabel = document.createElement("label");
  langLabel.textContent = "Language";
  langGroup.appendChild(langLabel);
  const langSelect = document.createElement("select");
  langSelect.className = "inflect-dialog-input";
  langSelect.id = "inflect-lang-select";
  for (const lang of ["en", "ja", "fr", "de", "es", "it", "pt", "zh", "ko", "ru"]) {
    const opt = document.createElement("option");
    opt.value = lang;
    opt.textContent = lang;
    langSelect.appendChild(opt);
  }
  langGroup.appendChild(langSelect);
  dialog.appendChild(langGroup);

  // Features input
  const featGroup = document.createElement("div");
  featGroup.className = "inflect-dialog-group";
  const featLabel = document.createElement("label");
  featLabel.textContent = "Features (comma-separated)";
  featGroup.appendChild(featLabel);
  const featInput = document.createElement("input");
  featInput.type = "text";
  featInput.className = "inflect-dialog-input";
  featInput.placeholder = "e.g. plural, possessive";
  featInput.id = "inflect-features-input";
  featGroup.appendChild(featInput);
  dialog.appendChild(featGroup);

  // Inflect button
  const btnRow = document.createElement("div");
  btnRow.className = "inflect-dialog-actions";

  const inflectBtn = document.createElement("button");
  inflectBtn.className = "inflect-dialog-btn";
  inflectBtn.textContent = "Inflect";
  inflectBtn.addEventListener("click", () => {
    const word = wordInput.value.trim();
    const lang = langSelect.value;
    const features = featInput.value.trim();
    if (word) {
      handlers.onInflectWord(word, lang, features);
    }
  });
  btnRow.appendChild(inflectBtn);

  const closeBtn = document.createElement("button");
  closeBtn.className = "inflect-dialog-btn inflect-dialog-btn-secondary";
  closeBtn.textContent = "Close";
  closeBtn.addEventListener("click", () => handlers.onCloseInflectDialog());
  btnRow.appendChild(closeBtn);

  dialog.appendChild(btnRow);

  // Result display
  if (state.inflectResult !== null) {
    const resultEl = document.createElement("div");
    resultEl.className = "inflect-dialog-result";
    const resultLabel = document.createElement("span");
    resultLabel.className = "inflect-dialog-result-label";
    resultLabel.textContent = "Result: ";
    resultEl.appendChild(resultLabel);
    const resultValue = document.createElement("span");
    resultValue.className = "inflect-dialog-result-value";
    resultValue.textContent = state.inflectResult;
    resultEl.appendChild(resultValue);
    dialog.appendChild(resultEl);
  }

  // Keyboard handling
  function onKeydown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      inflectBtn.click();
    } else if (e.key === "Escape") {
      e.preventDefault();
      handlers.onCloseInflectDialog();
    }
  }
  wordInput.addEventListener("keydown", onKeydown);
  featInput.addEventListener("keydown", onKeydown);

  backdrop.appendChild(dialog);

  // Auto-focus word input
  requestAnimationFrame(() => wordInput.focus());
}

// ---------------------------------------------------------------------------
// Review list
// ---------------------------------------------------------------------------

function renderReviewList(el, state, handlers) {
  el.innerHTML = "";

  const header = document.createElement("div");
  header.className = "entity-section-header";
  const h2 = document.createElement("h2");
  h2.textContent = "Reviews";
  h2.style.fontSize = "1.2rem";
  h2.style.fontWeight = "500";
  header.appendChild(h2);

  if (handlers && handlers.onAddReview) {
    const addBtn = document.createElement("button");
    addBtn.className = "entity-action-btn";
    addBtn.textContent = "Add";
    addBtn.addEventListener("click", () => handlers.onAddReview());
    header.appendChild(addBtn);
  }

  el.appendChild(header);

  if (state.loading) {
    el.innerHTML += '<div class="content-placeholder">Loading\u2026</div>';
    return;
  }

  if (state.reviews.length === 0) {
    const empty = document.createElement("p");
    empty.className = "entity-note-empty";
    empty.textContent = "No reviews yet.";
    el.appendChild(empty);
    return;
  }

  for (const r of state.reviews) {
    const row = document.createElement("div");
    row.className = "review-row";

    const severity = document.createElement("span");
    severity.className = `review-severity review-severity-${r.severity || "medium"}`;
    severity.textContent = r.severity || "medium";
    row.appendChild(severity);

    if (r.scope) {
      const scope = document.createElement("span");
      scope.className = "entity-badge";
      scope.textContent = r.scope;
      row.appendChild(scope);
    }

    if (r.issue_type) {
      const issueType = document.createElement("span");
      issueType.className = "entity-badge";
      issueType.textContent = r.issue_type;
      row.appendChild(issueType);
    }

    const desc = document.createElement("span");
    desc.className = "review-description";
    desc.textContent = (r.description || "").replace("\n", " ").slice(0, 100);
    row.appendChild(desc);

    if (handlers && handlers.onDeleteReview) {
      const delBtn = document.createElement("button");
      delBtn.className = "review-delete-btn";
      delBtn.textContent = "\u00d7";
      delBtn.title = "Delete review";
      delBtn.addEventListener("click", () => handlers.onDeleteReview(r.id));
      row.appendChild(delBtn);
    }

    el.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// Command Palette (Cmd+K)
// ---------------------------------------------------------------------------

/** Track palette state for keyboard navigation */
let paletteSelectedIndex = 0;
let paletteQuery = "";

/**
 * Filter commands by query string, matching against label.
 * Returns commands grouped by category in display order.
 */
function filterCommands(query) {
  const q = query.toLowerCase().trim();
  if (!q) return commands.filter((c) => c.action !== null);
  return commands.filter(
    (c) => c.action !== null && c.label.toLowerCase().includes(q)
  );
}

function renderCommandPalette(state, handlers) {
  const existing = document.querySelector(".command-palette-backdrop");

  if (!state.commandPaletteOpen) {
    if (existing) existing.remove();
    paletteSelectedIndex = 0;
    paletteQuery = "";
    return;
  }

  // Build or reuse backdrop
  let backdrop = existing;
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "command-palette-backdrop";
    backdrop.addEventListener("mousedown", (e) => {
      // Close when clicking the backdrop itself (not the palette)
      if (e.target === backdrop) {
        handlers.onClosePalette();
      }
    });
    document.body.appendChild(backdrop);
  }

  backdrop.innerHTML = "";

  const palette = document.createElement("div");
  palette.className = "command-palette";

  // Search input
  const input = document.createElement("input");
  input.type = "text";
  input.className = "command-palette-input";
  input.placeholder = "Type a command\u2026";
  input.value = paletteQuery;
  palette.appendChild(input);

  // Filtered command list
  const filtered = filterCommands(paletteQuery);

  // Clamp selected index
  if (paletteSelectedIndex >= filtered.length) {
    paletteSelectedIndex = Math.max(0, filtered.length - 1);
  }

  const list = document.createElement("div");
  list.className = "command-palette-list";

  // Group by category
  let lastCategory = null;
  for (let i = 0; i < filtered.length; i++) {
    const cmd = filtered[i];

    if (cmd.category !== lastCategory) {
      const catEl = document.createElement("div");
      catEl.className = "command-category";
      catEl.textContent = cmd.category;
      list.appendChild(catEl);
      lastCategory = cmd.category;
    }

    const item = document.createElement("div");
    item.className = "command-item";
    if (i === paletteSelectedIndex) item.classList.add("selected");

    const label = document.createElement("span");
    label.className = "command-item-label";
    label.textContent = cmd.label;
    item.appendChild(label);

    if (cmd.shortcut) {
      const shortcut = document.createElement("span");
      shortcut.className = "command-item-shortcut";
      shortcut.textContent = cmd.shortcut;
      item.appendChild(shortcut);
    }

    // Click to execute
    const idx = i;
    item.addEventListener("click", () => {
      handlers.onExecuteCommand(filtered[idx]);
    });

    // Hover updates selection
    item.addEventListener("mouseenter", () => {
      paletteSelectedIndex = idx;
      // Update selected class without full re-render
      const items = list.querySelectorAll(".command-item");
      items.forEach((el, j) => el.classList.toggle("selected", j === idx));
    });

    list.appendChild(item);
  }

  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "command-item";
    empty.style.color = "var(--muted)";
    empty.style.cursor = "default";
    empty.textContent = "No matching commands";
    list.appendChild(empty);
  }

  palette.appendChild(list);
  backdrop.appendChild(palette);

  // Keyboard handling on the input
  input.addEventListener("input", () => {
    paletteQuery = input.value;
    paletteSelectedIndex = 0;
    // Re-render the palette with updated filter
    renderCommandPalette(state, handlers);
  });

  input.addEventListener("keydown", (e) => {
    const currentFiltered = filterCommands(paletteQuery);

    if (e.key === "Escape") {
      e.preventDefault();
      handlers.onClosePalette();
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (currentFiltered.length > 0) {
        paletteSelectedIndex = (paletteSelectedIndex + 1) % currentFiltered.length;
        const items = list.querySelectorAll(".command-item");
        items.forEach((el, j) => el.classList.toggle("selected", j === paletteSelectedIndex));
        // Scroll selected item into view
        const sel = list.querySelector(".command-item.selected");
        if (sel) sel.scrollIntoView({ block: "nearest" });
      }
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (currentFiltered.length > 0) {
        paletteSelectedIndex = (paletteSelectedIndex - 1 + currentFiltered.length) % currentFiltered.length;
        const items = list.querySelectorAll(".command-item");
        items.forEach((el, j) => el.classList.toggle("selected", j === paletteSelectedIndex));
        const sel = list.querySelector(".command-item.selected");
        if (sel) sel.scrollIntoView({ block: "nearest" });
      }
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (currentFiltered.length > 0 && paletteSelectedIndex < currentFiltered.length) {
        handlers.onExecuteCommand(currentFiltered[paletteSelectedIndex]);
      }
      return;
    }
  });

  // Auto-focus input after DOM insertion
  requestAnimationFrame(() => {
    input.focus();
  });
}

// ---------------------------------------------------------------------------
// Error banner
// ---------------------------------------------------------------------------

function renderError(state, handlers) {
  let el = document.getElementById("error-banner");
  if (state.error) {
    if (!el) {
      el = document.createElement("div");
      el.id = "error-banner";
      document.body.prepend(el);
    }
    el.innerHTML = '';

    const text = document.createElement("span");
    text.className = "error-banner-text";
    text.textContent = state.error;
    el.appendChild(text);

    const dismiss = document.createElement("button");
    dismiss.className = "error-banner-dismiss";
    dismiss.textContent = "\u00d7";
    dismiss.title = "Dismiss";
    dismiss.addEventListener("click", (e) => {
      e.stopPropagation();
      if (handlers && handlers.onDismissError) {
        handlers.onDismissError();
      }
    });
    el.appendChild(dismiss);

    el.style.display = "flex";
  } else if (el) {
    el.style.display = "none";
  }
}

// ---------------------------------------------------------------------------
// Theme toggle
// ---------------------------------------------------------------------------

function themeLabel(theme) {
  if (theme === null) return "auto";
  return theme;
}

function renderThemeToggle(state, handlers) {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.textContent = themeLabel(state.theme);
  btn.onclick = () => handlers.onThemeToggle();
}
