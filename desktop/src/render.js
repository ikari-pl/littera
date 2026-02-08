/**
 * render.js — Pure DOM rendering functions.
 *
 * Each function takes state (or a slice of it) and updates the DOM.
 * No fetches, no side effects beyond DOM mutation.
 */

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
  renderError(state);

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
    err.textContent = state.pickerError;
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
      `<div class="picker-spinner"></div>`;
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
      </div>
      <nav id="breadcrumb"></nav>
      <div id="sidebar-actions"></div>
      <ul id="sidebar-list"></ul>
      <div id="tab-bar">
        <button id="tab-outline" class="tab tab-active">Outline</button>
        <button id="tab-entities" class="tab">Entities</button>
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
  const outlineTab = document.getElementById("tab-outline");
  const entitiesTab = document.getElementById("tab-entities");

  outlineTab.classList.toggle("tab-active", state.view === "outline");
  entitiesTab.classList.toggle("tab-active", state.view === "entities");

  // Re-bind (simple approach for read-only phase)
  outlineTab.onclick = () => handlers.onTabClick("outline");
  entitiesTab.onclick = () => handlers.onTabClick("entities");
}

// ---------------------------------------------------------------------------
// Sidebar item list
// ---------------------------------------------------------------------------

function renderSidebarActions(state, handlers) {
  const el = document.getElementById("sidebar-actions");
  if (!el) return;
  el.innerHTML = "";

  if (state.view === "entities") {
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
    const li = document.createElement("li");
    li.className = "sidebar-loading";
    li.textContent = "Loading\u2026";
    el.appendChild(li);
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
    } else {
      li.textContent = item.title || "(untitled)";
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
    el.innerHTML = '<div class="content-placeholder">Loading\u2026</div>';
    return;
  }

  // Entity detail view
  if (state.view === "entities" && state.entityDetail) {
    const detailWithId = { ...state.entityDetail, _entityId: state.selectedEntityId };
    renderEntityDetail(el, detailWithId, handlers);
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
  if (detail.labels && detail.labels.length > 0) {
    const section = document.createElement("div");
    section.className = "entity-section";
    section.innerHTML = "<h3>Labels</h3>";

    for (const label of detail.labels) {
      const row = document.createElement("div");
      row.className = "entity-label-row";
      row.innerHTML = `<span class="lang-badge">${escapeHtml(label.language)}</span> ${escapeHtml(label.base_form)}`;
      if (label.aliases) {
        row.innerHTML += ` <span class="entity-aliases">(${escapeHtml(label.aliases)})</span>`;
      }
      section.appendChild(row);
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
    section.innerHTML = "<h3>Mentions</h3>";

    for (const m of detail.mentions) {
      const row = document.createElement("div");
      row.className = "mention-row";
      row.innerHTML =
        `<span class="mention-path">${escapeHtml(m.document)} / ${escapeHtml(m.section)}</span>` +
        ` <span class="lang-badge">${escapeHtml(m.language)}</span>` +
        `<div class="mention-preview">${escapeHtml(m.preview)}</div>`;
      section.appendChild(row);
    }
    el.appendChild(section);
  }
}

// ---------------------------------------------------------------------------
// Error banner
// ---------------------------------------------------------------------------

function renderError(state) {
  let el = document.getElementById("error-banner");
  if (state.error) {
    if (!el) {
      el = document.createElement("div");
      el.id = "error-banner";
      document.body.prepend(el);
    }
    el.textContent = state.error;
    el.style.display = "block";
  } else if (el) {
    el.style.display = "none";
  }
}
