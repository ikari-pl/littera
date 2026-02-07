/**
 * render.js — Pure DOM rendering functions.
 *
 * Each function takes state (or a slice of it) and updates the DOM.
 * No fetches, no side effects beyond DOM mutation.
 */

// ---------------------------------------------------------------------------
// Main render entry point
// ---------------------------------------------------------------------------

export function render(state, handlers) {
  renderBreadcrumb(state, handlers);
  renderTabs(state, handlers);
  renderSidebar(state, handlers);
  renderContent(state);
  renderError(state);
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

function renderSidebar(state, handlers) {
  const el = document.getElementById("sidebar-list");
  el.innerHTML = "";

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

    li.addEventListener("click", () => handlers.onItemClick(item));
    el.appendChild(li);
  }
}

// ---------------------------------------------------------------------------
// Content area
// ---------------------------------------------------------------------------

function renderContent(state) {
  const el = document.getElementById("content");

  if (state.loading) {
    el.innerHTML = '<div class="content-placeholder">Loading\u2026</div>';
    return;
  }

  // Entity detail view
  if (state.view === "entities" && state.entityDetail) {
    renderEntityDetail(el, state.entityDetail);
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

function renderEntityDetail(el, detail) {
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
  noteSection.innerHTML = "<h3>Note</h3>";
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
