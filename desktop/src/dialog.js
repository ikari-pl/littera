/**
 * dialog.js — In-app prompt, confirm, help, and toast overlays.
 * Replaces window.prompt / window.confirm for immersive desktop UX.
 */

const HELP_HTML = `
  <h2>Littera</h2>
  <p class="help-lead">Local-first writing with durable structure.</p>

  <h3>Structure</h3>
  <pre class="help-tree">Work
  └─ Document     (chapter, essay, article)
       └─ Section (scene, argument, part)
            └─ Block   (smallest text unit)</pre>
  <p>Blocks hold text. Everything else is navigation and meaning.</p>

  <h3>Meaning</h3>
  <ul>
    <li><strong>Entity</strong> — a person, place, concept, or idea (global)</li>
    <li><strong>Mention</strong> — binds an entity into a block (<code>@</code> in the editor)</li>
    <li><strong>Alignment</strong> — links two blocks (e.g. translation)</li>
    <li><strong>Review</strong> — a scoped note about quality or intent</li>
  </ul>

  <h3>Writing shortcuts</h3>
  <table class="help-keys">
    <tr><td>Cmd+S</td><td>Save</td></tr>
    <tr><td>Cmd+K</td><td>Link selection</td></tr>
    <tr><td>Cmd+Shift+P</td><td>Command palette</td></tr>
    <tr><td>Cmd+Shift+F</td><td>Distraction-free (zen) mode</td></tr>
    <tr><td>Shift+Enter</td><td>New block</td></tr>
    <tr><td>/</td><td>Slash commands</td></tr>
    <tr><td>@</td><td>Mention an entity</td></tr>
    <tr><td>?</td><td>This help</td></tr>
  </table>
  <p class="help-foot">Double-click a document or section title in the sidebar to rename.</p>
`;

function ensureStylesOnce() {
  // Styles live in style.css (.app-dialog-*).
}

function makeBackdrop(className) {
  const backdrop = document.createElement("div");
  backdrop.className = className;
  document.body.appendChild(backdrop);
  return backdrop;
}

/**
 * @param {{ title: string, message?: string, defaultValue?: string, placeholder?: string }} opts
 * @returns {Promise<string|null>}
 */
export function showPrompt({ title, message = "", defaultValue = "", placeholder = "" }) {
  ensureStylesOnce();
  return new Promise((resolve) => {
    const backdrop = makeBackdrop("app-dialog-backdrop");
    backdrop.innerHTML = `
      <div class="app-dialog" role="dialog" aria-modal="true">
        <h3 class="app-dialog-title"></h3>
        <p class="app-dialog-message"></p>
        <input class="app-dialog-input" type="text" />
        <div class="app-dialog-actions">
          <button type="button" class="app-dialog-btn app-dialog-btn-secondary" data-act="cancel">Cancel</button>
          <button type="button" class="app-dialog-btn" data-act="ok">OK</button>
        </div>
      </div>
    `;
    const titleEl = backdrop.querySelector(".app-dialog-title");
    const msgEl = backdrop.querySelector(".app-dialog-message");
    const input = backdrop.querySelector(".app-dialog-input");
    titleEl.textContent = title;
    if (message) msgEl.textContent = message;
    else msgEl.remove();
    input.value = defaultValue;
    input.placeholder = placeholder;

    const finish = (value) => {
      backdrop.remove();
      resolve(value);
    };

    backdrop.querySelector('[data-act="ok"]').addEventListener("click", () => {
      finish(input.value);
    });
    backdrop.querySelector('[data-act="cancel"]').addEventListener("click", () => finish(null));
    backdrop.addEventListener("mousedown", (e) => {
      if (e.target === backdrop) finish(null);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        finish(input.value);
      } else if (e.key === "Escape") {
        e.preventDefault();
        finish(null);
      }
    });
    requestAnimationFrame(() => {
      input.focus();
      input.select();
    });
  });
}

/**
 * @param {{ title: string, message: string }} opts
 * @returns {Promise<boolean>}
 */
export function showConfirm({ title, message }) {
  ensureStylesOnce();
  return new Promise((resolve) => {
    const backdrop = makeBackdrop("app-dialog-backdrop");
    backdrop.innerHTML = `
      <div class="app-dialog" role="dialog" aria-modal="true">
        <h3 class="app-dialog-title"></h3>
        <p class="app-dialog-message"></p>
        <div class="app-dialog-actions">
          <button type="button" class="app-dialog-btn app-dialog-btn-secondary" data-act="no">Cancel</button>
          <button type="button" class="app-dialog-btn" data-act="yes">OK</button>
        </div>
      </div>
    `;
    backdrop.querySelector(".app-dialog-title").textContent = title;
    backdrop.querySelector(".app-dialog-message").textContent = message;

    const finish = (value) => {
      backdrop.remove();
      resolve(value);
    };

    backdrop.querySelector('[data-act="yes"]').addEventListener("click", () => finish(true));
    backdrop.querySelector('[data-act="no"]').addEventListener("click", () => finish(false));
    backdrop.addEventListener("mousedown", (e) => {
      if (e.target === backdrop) finish(false);
    });
    backdrop.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        finish(false);
      } else if (e.key === "Enter") {
        e.preventDefault();
        finish(true);
      }
    });
    requestAnimationFrame(() => {
      backdrop.querySelector('[data-act="yes"]').focus();
    });
  });
}

/**
 * Show the in-app help / cheatsheet. Resolves when closed.
 * @returns {Promise<void>}
 */
export function showHelp() {
  ensureStylesOnce();
  return new Promise((resolve) => {
    const existing = document.querySelector(".help-dialog-backdrop");
    if (existing) {
      existing.remove();
      resolve();
      return;
    }
    const backdrop = makeBackdrop("help-dialog-backdrop");
    backdrop.innerHTML = `
      <div class="help-dialog" role="dialog" aria-modal="true" aria-label="Help">
        <button type="button" class="help-dialog-close" title="Close">\u00d7</button>
        <div class="help-dialog-body"></div>
      </div>
    `;
    backdrop.querySelector(".help-dialog-body").innerHTML = HELP_HTML;

    const finish = () => {
      backdrop.remove();
      resolve();
    };
    backdrop.querySelector(".help-dialog-close").addEventListener("click", finish);
    backdrop.addEventListener("mousedown", (e) => {
      if (e.target === backdrop) finish();
    });
    backdrop.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        finish();
      }
    });
    requestAnimationFrame(() => backdrop.focus());
    backdrop.tabIndex = -1;
    backdrop.focus();
  });
}

/**
 * Transient toast near the bottom of the viewport.
 * @param {string} message
 * @param {{ duration?: number }} [opts]
 */
export function showToast(message, { duration = 3500 } = {}) {
  ensureStylesOnce();
  let el = document.getElementById("app-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "app-toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.add("visible");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => {
    el.classList.remove("visible");
  }, duration);
}

/**
 * @param {{ title: string, options: Array<{ id: string, label: string }>, emptyText?: string }} opts
 * @returns {Promise<string|null>} selected option id
 */
export function showPicker({ title, options, emptyText = "No options" }) {
  ensureStylesOnce();
  return new Promise((resolve) => {
    const backdrop = makeBackdrop("app-dialog-backdrop");
    const dialog = document.createElement("div");
    dialog.className = "app-dialog app-dialog-wide";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");

    const h = document.createElement("h3");
    h.className = "app-dialog-title";
    h.textContent = title;
    dialog.appendChild(h);

    const list = document.createElement("div");
    list.className = "app-picker-list";

    if (!options.length) {
      const empty = document.createElement("p");
      empty.className = "app-dialog-message";
      empty.textContent = emptyText;
      dialog.appendChild(empty);
    } else {
      let selected = 0;
      const items = [];
      for (let i = 0; i < options.length; i++) {
        const opt = options[i];
        const row = document.createElement("button");
        row.type = "button";
        row.className = "app-picker-item";
        row.textContent = opt.label;
        row.addEventListener("click", () => finish(opt.id));
        list.appendChild(row);
        items.push(row);
      }
      dialog.appendChild(list);

      const syncSel = () => {
        items.forEach((el, i) => el.classList.toggle("selected", i === selected));
        items[selected]?.scrollIntoView({ block: "nearest" });
      };
      syncSel();

      backdrop.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          selected = (selected + 1) % items.length;
          syncSel();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          selected = (selected - 1 + items.length) % items.length;
          syncSel();
        } else if (e.key === "Enter") {
          e.preventDefault();
          finish(options[selected].id);
        } else if (e.key === "Escape") {
          e.preventDefault();
          finish(null);
        }
      });
    }

    const actions = document.createElement("div");
    actions.className = "app-dialog-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "app-dialog-btn app-dialog-btn-secondary";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => finish(null));
    actions.appendChild(cancel);
    dialog.appendChild(actions);

    backdrop.appendChild(dialog);

    const finish = (value) => {
      backdrop.remove();
      resolve(value);
    };

    backdrop.addEventListener("mousedown", (e) => {
      if (e.target === backdrop) finish(null);
    });
    requestAnimationFrame(() => {
      backdrop.tabIndex = -1;
      backdrop.focus();
    });
  });
}
