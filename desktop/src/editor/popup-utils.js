/**
 * popup-utils.js — Shared popup positioning, dismiss, and link input helpers.
 *
 * Mostly plain DOM utilities. showLinkInput takes a ProseMirror view
 * for positioning and focus management.
 */

/**
 * Position a popup element relative to a reference rect, clamped to container.
 *
 * Default placement: centered above the rect, offset by 8px.
 * Falls back to below if insufficient room above.
 *
 * @param {HTMLElement} popup  — The popup DOM element (must have position:absolute)
 * @param {{top: number, bottom: number, left: number, right: number}} rect
 * @param {HTMLElement} container — The bounding container for clamping
 */
export function positionPopup(popup, rect, container) {
  const containerRect = container.getBoundingClientRect();
  const popupRect = popup.getBoundingClientRect();
  const gap = 8;

  // Horizontal: center on the reference rect, clamp to container
  let left = (rect.left + rect.right) / 2 - popupRect.width / 2;
  left = Math.max(containerRect.left + 4, left);
  left = Math.min(containerRect.right - popupRect.width - 4, left);

  // Vertical: prefer above, fall back to below
  let top = rect.top - popupRect.height - gap;
  if (top < containerRect.top) {
    top = rect.bottom + gap;
  }

  // Convert to container-relative coordinates
  popup.style.left = (left - containerRect.left) + "px";
  popup.style.top = (top - containerRect.top) + "px";
}

/**
 * Add a one-time mousedown listener that calls onDismiss if the click
 * is outside the popup element. Returns a cleanup function.
 *
 * @param {HTMLElement} popup
 * @param {() => void} onDismiss
 * @returns {() => void} cleanup
 */
export function dismissOnClickOutside(popup, onDismiss) {
  function handler(e) {
    if (!popup.contains(e.target)) {
      onDismiss();
      document.removeEventListener("mousedown", handler, true);
    }
  }
  // Use capture so we fire before ProseMirror's handlers
  document.addEventListener("mousedown", handler, true);
  return () => document.removeEventListener("mousedown", handler, true);
}

// ---------------------------------------------------------------------------
// Floating link URL input — replaces window.prompt() for Tauri compat
// ---------------------------------------------------------------------------

let activeLinkInput = null;

function dismissLinkInput() {
  if (activeLinkInput) {
    activeLinkInput.remove();
    activeLinkInput = null;
  }
}

/**
 * Show a floating URL input near the current selection.
 *
 * @param {EditorView} view — ProseMirror editor view
 * @param {(href: string) => void} onApply — called with the URL when Enter is pressed
 */
export function showLinkInput(view, onApply) {
  dismissLinkInput();

  const container = view.dom.parentElement;
  const { from, to } = view.state.selection;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "link-input";
  input.placeholder = "Paste or type URL…";
  container.appendChild(input);
  activeLinkInput = input;

  // Position near the selection
  const coords = view.coordsAtPos(from);
  const toCoords = view.coordsAtPos(to);
  const rect = {
    top: coords.top,
    bottom: coords.bottom,
    left: coords.left,
    right: toCoords.right,
  };
  positionPopup(input, rect, container);

  input.focus();

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const href = input.value.trim();
      dismissLinkInput();
      if (href) onApply(href);
      view.focus();
    } else if (e.key === "Escape") {
      e.preventDefault();
      dismissLinkInput();
      view.focus();
    }
  });

  input.addEventListener("blur", () => {
    setTimeout(() => {
      if (activeLinkInput === input) dismissLinkInput();
    }, 150);
  });
}
