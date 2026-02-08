# Littera Desktop App -- Design Reference

This document describes the visual design system used in the Littera desktop
application (Tauri + vanilla JS + ProseMirror). Consult it when implementing
new features so that additions feel native to the existing interface.

Source of truth: `/desktop/src/style.css` (1084 lines).

---

## 1. Color Palette

All colors are defined as CSS custom properties on `:root`.

### Background layers (dark-to-light depth)

| Variable         | Value                        | Usage                                                |
|------------------|------------------------------|------------------------------------------------------|
| `--bg`           | `#1a1a2e`                    | Page/body background, deepest layer                  |
| `--bg-sidebar`   | `#16162a`                    | Sidebar background, darkest surface                  |
| `--bg-content`   | `#1e1e36`                    | Main content area background                         |

The palette is a deep indigo-navy family. Surfaces are distinguished by subtle
lightness shifts, never by hue changes.

### Foreground / text

| Variable    | Value      | Usage                                                         |
|-------------|------------|---------------------------------------------------------------|
| `--fg`      | `#e0e0e0`  | Primary body text                                             |
| `--fg-dim`  | `#a0a0b8`  | Secondary text, italic emphasis, breadcrumb-current, h4       |
| `--muted`   | `#6b6b80`  | Tertiary text, placeholders, timestamps, section headers      |
| (literal)   | `#fff`     | Used sparingly for bold/strong text and hovered sidebar items |

### Accent / interactive

| Variable         | Value                        | Usage                                                    |
|------------------|------------------------------|----------------------------------------------------------|
| `--accent`       | `#7c8fa8`                    | Primary interactive color: links, app title, active tab, h3, blockquote border, selected-node outline |
| `--accent-hover` | `#94a8c4`                    | Hover state for accent items, h1/h2 headings, link text  |

The accent is a desaturated steel-blue. It never screams. Hover lightens it
slightly toward periwinkle; there is no color-shift on hover.

### State / selection

| Variable           | Value                           | Usage                                     |
|--------------------|---------------------------------|--------------------------------------------|
| `--selected`       | `rgba(124, 143, 168, 0.15)`    | Hover/selected background on list items    |
| `--selected-border`| `rgba(124, 143, 168, 0.4)`     | Left-border on selected sidebar item, focus ring on rename input |
| `--border`         | `rgba(255, 255, 255, 0.08)`    | Universal divider lines, scrollbar thumb   |

### Badge system

| Variable      | Value                        | Usage                                          |
|---------------|------------------------------|-------------------------------------------------|
| `--badge-bg`  | `rgba(124, 143, 168, 0.2)`  | Background for lang/entity badges, action btns  |
| `--badge-fg`  | `#94a8c4`                    | Text color inside badges                        |

### Error

| Variable  | Value   | Usage                                            |
|-----------|---------|--------------------------------------------------|
| `--error` | `#c45`  | Shorthand for `#cc4455`. Delete-hover, error banners |

### Hardcoded colors (not in variables)

| Value                          | Where used                                                   |
|--------------------------------|--------------------------------------------------------------|
| `#252540`                      | Popup/overlay backgrounds: bubble-toolbar, slash-menu, mention-popup, link-input |
| `rgba(0, 0, 0, 0.3)`          | Code block background in editor                              |
| `rgba(255, 255, 255, 0.06)`   | Inline code background                                       |
| `rgba(255, 255, 255, 0.08)`   | Hover bg on toolbar buttons                                  |
| `rgba(255, 255, 255, 0.15)`   | Hovered block-boundary border                                |
| `rgba(204, 68, 85, 0.15)`     | Error banner background (--error at 15% opacity)             |
| `rgba(124, 143, 168, 0.3)`    | Mention-pill border                                          |

**If you add a new popup or overlay, use `#252540` as its background.**
It sits exactly between `--bg-content` and `--fg-dim` in perceived brightness.

---

## 2. Typography

### Font stacks

| Context          | Stack                                           |
|------------------|-------------------------------------------------|
| Body / UI        | `system-ui, -apple-system, sans-serif`          |
| Code (inline)    | `"SF Mono", "Fira Code", monospace`             |

The app uses the OS system font exclusively. There are no custom web fonts.
This is intentional: Littera is a writing tool and the system font keeps the
chrome invisible while the writer's prose takes center stage.

### Size scale

| Token / selector                        | Size        | Weight | Usage                                |
|-----------------------------------------|-------------|--------|--------------------------------------|
| `body`                                  | (default)   | 400    | Base; line-height 1.6                |
| `.block-text`, editor `.ProseMirror`    | `1rem`      | 400    | Body prose; line-height 1.7          |
| `#sidebar-header h1`                    | `1.1rem`    | 500    | App title in sidebar                 |
| `.picker-header h1`, loading h1         | `1.6rem`    | 500    | Picker screen title                  |
| `.entity-header h2`                     | `1.4rem`    | 500    | Entity detail heading                |
| editor `h1`                             | `1.5rem`    | 600    | Document heading                     |
| editor `h2`, `.block-text h2`           | `1.3rem`    | 600    | Section heading                      |
| editor `h3`, `.block-text h3`           | `1.1rem`    | 600    | Subsection heading                   |
| `.block-text h4`                        | `1rem`      | 600    | Minor heading                        |
| `.sidebar-item`, `.picker-btn`          | `0.9rem`    | 400    | UI controls, sidebar text            |
| `.content-placeholder`, `.picker-header p` | `0.95rem` | 400  | Secondary UI text                    |
| `.entity-section h3`                    | `0.85rem`   | 400    | Section labels (uppercase)           |
| `#breadcrumb`                           | `0.8rem`    | 400    | Navigation breadcrumb                |
| `.tab`                                  | `0.8rem`    | 400    | Tab bar labels                       |
| `.block-lang`, `.picker-section h2`     | `0.75rem`   | 400    | Small metadata tags                  |
| `.lang-badge`, `.entity-badge`          | `0.7rem`    | 400    | Badges (uppercase, letter-spaced)    |
| `.entity-action-btn`                    | `0.7rem`    | 400    | Small action buttons (uppercase)     |

### Letter spacing

| Context                                                    | Value      |
|------------------------------------------------------------|------------|
| `#sidebar-header h1`                                       | `0.05em`   |
| `.picker-header h1`, `#picker-loading h1`                  | `0.06em`   |
| `.entity-section h3`, `.picker-section h2`                 | `0.06em`   |
| `.lang-badge`, `.entity-badge`, `.entity-action-btn`       | `0.03em`   |

Letter spacing is used exclusively on uppercase labels and the app title.
Never apply it to body text or prose headings.

### Line heights

| Context                   | Value |
|---------------------------|-------|
| `body`                    | 1.6   |
| `.block-text`, editor     | 1.7   |
| Editor `pre` (code block) | 1.2   |
| Entity note               | 1.6   |

---

## 3. Component Patterns

### 3.1 Buttons

**Action button (small, badge-like):**
Used for "Edit", "Add" within section headers.

```css
.entity-action-btn {
  background: var(--badge-bg);          /* rgba(124,143,168,0.2) */
  border: 1px solid var(--border);      /* rgba(255,255,255,0.08) */
  color: var(--accent);                 /* #7c8fa8 */
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  transition: background 0.1s;
}
.entity-action-btn:hover {
  background: var(--selected);          /* rgba(124,143,168,0.15) */
  color: var(--accent-hover);           /* #94a8c4 */
}
```

**Sidebar icon button (square, 26x26):**
Used for the "+" add button in the sidebar actions bar.

```css
.sidebar-action-btn {
  background: var(--badge-bg);
  border: 1px solid var(--border);
  color: var(--accent);
  font-size: 0.9rem;
  width: 26px;
  height: 26px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.1s;
}
```

**Picker button (large, full-width):**
Used on the work-picker screen for primary and secondary actions.

```css
.picker-btn {
  flex: 1;
  padding: 0.7rem 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--badge-bg);
  color: var(--fg);
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.1s, border-color 0.1s;
  font-family: inherit;
}
.picker-btn:hover {
  background: var(--selected);
  border-color: var(--selected-border);
}
/* Secondary variant: transparent bg, dimmer text */
.picker-btn-secondary {
  background: transparent;
  color: var(--fg-dim);
}
```

**Link button (text only):**

```css
.picker-btn-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 0.8rem;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
}
.picker-btn-link:hover {
  color: var(--accent-hover);
  text-decoration: underline;
}
```

**Toolbar button (bubble toolbar):**

```css
.bt-btn {
  background: none;
  border: none;
  color: var(--fg-dim);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 3px;
  cursor: pointer;
  min-width: 28px;
  text-align: center;
}
.bt-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--fg);
}
.bt-btn.active {
  background: var(--selected);
  color: var(--accent-hover);
}
```

### 3.2 Badges

All badges share the same visual language: small, uppercase, muted.

```css
/* Base badge (inline with text) */
.lang-badge, .entity-badge {
  font-size: 0.7rem;
  color: var(--badge-fg);              /* #94a8c4 */
  background: var(--badge-bg);         /* rgba(124,143,168,0.2) */
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  margin-right: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* Larger variant for entity detail header */
.entity-badge-lg {
  font-size: 0.8rem;
  padding: 0.2rem 0.6rem;
}

/* Block language tag (slightly different sizing) */
.block-lang {
  font-size: 0.75rem;
  color: var(--badge-fg);
  background: var(--badge-bg);
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 3px;
  margin-bottom: 0.5rem;
}
```

### 3.3 Mention pill (inline in editor)

```css
.mention-pill {
  display: inline-block;
  background: var(--badge-bg);
  color: var(--badge-fg);
  font-size: 0.85em;
  padding: 0.05em 0.5em;
  border-radius: 10px;           /* Full pill shape -- exception to the 3-4px rule */
  vertical-align: baseline;
  cursor: pointer;
  user-select: none;
  border: 1px solid rgba(124, 143, 168, 0.3);
}
```

### 3.4 Sidebar items

Sidebar items use a left-border accent for selection state and a
hover-reveal pattern for the delete button.

```css
.sidebar-item {
  padding: 0.5rem 0.8rem;
  border-radius: 4px;
  font-size: 0.9rem;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background 0.1s;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.sidebar-item:hover {
  background: var(--selected);
  color: #fff;
}
.sidebar-item.selected {
  background: var(--selected);
  border-left-color: var(--selected-border);
  color: #fff;
}
```

### 3.5 Delete buttons (hover-reveal pattern)

This pattern is used in two places: sidebar items and mention rows. The
button is invisible until the parent row is hovered.

```css
.sidebar-delete-btn {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 0.9rem;
  cursor: pointer;
  margin-left: auto;
  padding: 0 0.3rem;
  opacity: 0;                          /* Hidden by default */
  transition: opacity 0.1s, color 0.1s;
  flex-shrink: 0;
}
.sidebar-item:hover .sidebar-delete-btn {
  opacity: 1;                          /* Revealed on parent hover */
}
.sidebar-delete-btn:hover {
  color: var(--error);                 /* Red on direct hover */
}
```

To replicate this pattern for any new list row:
1. The row must be `display: flex`.
2. The delete button uses `margin-left: auto` to push it to the right edge.
3. It starts at `opacity: 0` and becomes `opacity: 1` when the *row* is hovered.
4. On direct hover, its color shifts to `var(--error)`.

### 3.6 Popup menus (slash-menu, mention-popup)

All popup overlays share the same visual container:

```css
/* Shared popup container style */
.popup-container {
  position: absolute;
  z-index: 50;
  background: #252540;
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  padding: 4px;
  overflow-y: auto;
}
```

Menu items inside popups follow this pattern:

```css
.popup-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--fg);
}
.popup-item:hover,
.popup-item.selected {
  background: var(--selected);
}
```

The `.selected` class is managed by keyboard navigation (ArrowUp/ArrowDown)
and mirrors the hover style exactly. There is no focus ring on popup items.

### 3.7 Form inputs

**Sidebar rename input (inline):**

```css
.sidebar-rename-input {
  background: transparent;
  border: 1px solid var(--selected-border);
  color: var(--fg);
  font-size: 0.9rem;
  padding: 0.3rem 0.5rem;
  width: 100%;
  outline: none;
  border-radius: 3px;
  font-family: inherit;
}
.sidebar-rename-input:focus {
  border-color: var(--accent);
}
```

**Link URL input (floating):**

```css
.link-input {
  position: absolute;
  z-index: 50;
  background: #252540;
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  color: var(--fg);
  font-size: 0.85rem;
  font-family: system-ui, sans-serif;
  padding: 6px 10px;
  width: 280px;
  outline: none;
}
.link-input:focus {
  border-color: var(--accent);
}
.link-input::placeholder {
  color: var(--muted);
}
```

All inputs: `outline: none`, border transitions to `var(--accent)` on focus,
`font-family: inherit` (or explicit system-ui).

### 3.8 Section headers (entity detail)

Used for "Labels", "Note", "Mentions (N)" sections:

```css
.entity-section h3 {
  font-size: 0.85rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.5rem;
}
```

When a section header has an action button beside it:

```css
.entity-section-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}
```

### 3.9 Error banner

Fixed to top of viewport, full width, centered text:

```css
#error-banner {
  display: none;
  background: rgba(204, 68, 85, 0.15);
  color: var(--error);
  padding: 0.6rem 1rem;
  font-size: 0.85rem;
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  text-align: center;
}
```

---

## 4. Spacing System

The app does not use a formal spacing scale (4px, 8px, etc.) but follows
consistent patterns:

### Padding

| Context                      | Value                 |
|------------------------------|-----------------------|
| Content area                 | `2rem 2.5rem`         |
| Zen mode content             | `3rem 2.5rem`         |
| Sidebar header               | `1rem 1.2rem 0.6rem`  |
| Breadcrumb                   | `0 1.2rem 0.6rem`     |
| Sidebar actions              | `0 0.8rem 0.4rem`     |
| Sidebar list                 | `0 0.4rem`            |
| Sidebar item                 | `0.5rem 0.8rem`       |
| Picker page                  | `3rem 2rem`           |
| Picker item                  | `0.6rem 0.8rem`       |
| Tab                          | `0.6rem 0`            |
| Popup menu padding           | `4px`                 |
| Popup menu item              | `6px 10px`            |
| Toolbar button               | `4px 8px`             |

### Margins (vertical rhythm)

| Context                      | Value                 |
|------------------------------|-----------------------|
| Block bottom margin          | `1.5rem`              |
| Block bottom padding         | `1.5rem`              |
| Editor block (littera-block) | `1rem` bottom margin + padding |
| Entity section               | `1.5rem` bottom       |
| Paragraph bottom margin      | `0.8em`               |
| h2 margin                    | `1rem 0 0.5rem`       |
| h3 margin                    | `0.8rem 0 0.4rem`     |
| Picker header bottom         | `2rem`                |
| Picker section bottom        | `1.5rem`              |

### Gaps (flexbox/grid)

| Context                      | Value                 |
|------------------------------|-----------------------|
| Sidebar item gap             | `0.3rem`              |
| Entity header gap            | `0.8rem`              |
| Section header gap           | `0.6rem`              |
| Mention row gap              | `0.5rem`              |
| Popup item gap               | `8px`                 |
| Toolbar button gap           | `2px`                 |
| Picker actions gap           | `0.8rem`              |

### Editor max-width

| Mode                         | Value                 |
|------------------------------|-----------------------|
| Normal                       | `720px`               |
| Zen mode                     | `680px`               |

---

## 5. Interactive States

### Transitions

Every interactive transition is `0.1s`. No easing function is specified
(default `ease` applies). No transition exceeds 150ms anywhere in the app.

```css
transition: background 0.1s;           /* Most common */
transition: opacity 0.1s, color 0.1s;  /* Delete buttons */
transition: color 0.1s;                /* Tabs */
transition: border-color 0.15s;        /* Block hover borders */
```

### Hover states

| Element              | Default                  | Hover                           |
|----------------------|--------------------------|---------------------------------|
| Sidebar item         | transparent bg           | `var(--selected)` bg, `#fff` text |
| Sidebar delete btn   | `opacity: 0`             | `opacity: 1`, then `var(--error)` on direct hover |
| Tab                  | `var(--muted)` text      | `var(--fg)` text                |
| Action button        | `var(--badge-bg)` bg     | `var(--selected)` bg, `var(--accent-hover)` text |
| Breadcrumb link      | `var(--accent)` text     | `var(--accent-hover)` + underline |
| Picker button        | `var(--badge-bg)` bg     | `var(--selected)` bg + `var(--selected-border)` border |
| Toolbar button       | no bg                    | `rgba(255,255,255,0.08)` bg, `var(--fg)` text |
| Scrollbar thumb      | `var(--border)`          | `var(--muted)`                  |
| Editor block border  | `var(--border)`          | `rgba(255,255,255,0.15)`        |

### Selected / active states

| Element              | Visual treatment                                               |
|----------------------|----------------------------------------------------------------|
| Sidebar item         | `var(--selected)` bg + 2px left border in `var(--selected-border)` + `#fff` text |
| Tab                  | `var(--accent)` text + `inset 0 2px 0 var(--accent)` top shadow |
| Toolbar button       | `var(--selected)` bg + `var(--accent-hover)` text              |
| Popup menu item      | `var(--selected)` bg (same as hover)                           |

### Focus states

| Element              | Focus treatment                                  |
|----------------------|--------------------------------------------------|
| Rename input         | `border-color: var(--accent)`                    |
| Link input           | `border-color: var(--accent)`                    |
| ProseMirror editor   | `outline: none`                                  |
| Selected PM node     | `outline: 2px solid var(--accent)`               |

Focus rings are suppressed on all elements. The only focus indicator is a
border-color change to `var(--accent)` on inputs.

---

## 6. Design Recommendations for New Features

### 6.1 Entity Label Management UI

Labels appear in the entity detail panel under the "Labels" section header.
Currently they are read-only rows. Here is how to add inline add/delete.

**Add label (inline pattern):**

Place an add row at the bottom of the labels list. It should appear
only when hovering the section header area or clicking an "Add" button.

```css
.entity-label-add-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0;
}

.entity-label-add-input {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--fg);
  font-size: 0.85rem;
  padding: 0.25rem 0.5rem;
  flex: 1;
  outline: none;
  font-family: inherit;
}
.entity-label-add-input:focus {
  border-color: var(--accent);
}
.entity-label-add-input::placeholder {
  color: var(--muted);
}

/* Language selector: small, badge-like dropdown */
.entity-label-lang-select {
  background: var(--badge-bg);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--badge-fg);
  font-size: 0.7rem;
  padding: 0.2rem 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  outline: none;
  cursor: pointer;
  font-family: inherit;
  appearance: none;
  -webkit-appearance: none;
}
.entity-label-lang-select:focus {
  border-color: var(--accent);
}
```

The flow: click "Add" button in section header (use `entity-action-btn` style).
A row appears with `[lang-select] [text-input]`. Press Enter to confirm,
Escape to cancel. The row auto-removes on blur if empty.

**Delete label (hover-reveal):**

Apply the same hover-reveal delete pattern used elsewhere:

```css
.entity-label-row {
  display: flex;
  align-items: center;
  padding: 0.3rem 0;
  font-size: 0.9rem;
}

.entity-label-delete-btn {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 0.85rem;
  cursor: pointer;
  margin-left: auto;
  padding: 0 0.3rem;
  opacity: 0;
  transition: opacity 0.1s, color 0.1s;
  flex-shrink: 0;
}
.entity-label-row:hover .entity-label-delete-btn {
  opacity: 1;
}
.entity-label-delete-btn:hover {
  color: var(--error);
}
```

### 6.2 Command Palette (Cmd+K)

Model this after the existing slash-menu and mention-popup, but as a
global overlay rather than editor-local popup.

**Overlay structure:**

```
+--------------------------------------------------+
|  body (dimmed backdrop)                           |
|  +--------------------------------------------+  |
|  | .command-palette                            |  |
|  | +----------------------------------------+ |  |
|  | | .command-palette-input                  | |  |
|  | +----------------------------------------+ |  |
|  | | .command-item          [keybind hint]   | |  |
|  | | .command-item.selected [keybind hint]   | |  |
|  | | .command-item          [keybind hint]   | |  |
|  | +----------------------------------------+ |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
```

**Suggested CSS:**

```css
.command-palette-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 200;
  display: flex;
  justify-content: center;
  padding-top: 20vh;             /* Positioned in upper third */
}

.command-palette {
  background: #252540;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  width: 480px;
  max-height: 360px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.command-palette-input {
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--fg);
  font-size: 0.95rem;
  padding: 12px 16px;
  outline: none;
  font-family: system-ui, -apple-system, sans-serif;
}
.command-palette-input::placeholder {
  color: var(--muted);
}

.command-palette-list {
  overflow-y: auto;
  padding: 4px;
}

.command-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--fg);
}
.command-item:hover,
.command-item.selected {
  background: var(--selected);
}

.command-item-label {
  flex: 1;
}

.command-item-shortcut {
  font-size: 0.7rem;
  color: var(--muted);
  font-family: system-ui, sans-serif;
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid var(--border);
}

/* Category separator within command list */
.command-category {
  font-size: 0.7rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 6px 12px 2px;
}
```

**Behavior notes:**
- Open with Cmd+K (or Ctrl+K on Linux). Close with Escape or clicking backdrop.
- Keyboard navigation: ArrowUp/ArrowDown to move `.selected`, Enter to execute.
- Reuse the same keyboard handling pattern from `slash-menu.js` and
  `mention-popup.js` (selectedIndex + re-render).
- Filter items by typing. Match against label and keywords (same approach as
  `filterCommands` in slash-menu).
- The command palette should use `z-index: 200` (above the error banner at 100
  and popups at 50).

### 6.3 Light Theme

The existing dark theme uses an indigo-navy base with desaturated steel-blue
accents. A light equivalent should maintain the same quiet, serious aesthetic:
warm grays and slate blues, no pure white backgrounds, no saturated colors.

```css
/* Light theme -- apply via <html data-theme="light"> or a .light-theme class */

:root[data-theme="light"] {
  --bg:              #f0eeeb;      /* Warm off-white (not pure white) */
  --bg-sidebar:      #e8e5e1;      /* Slightly warmer/darker sidebar */
  --bg-content:      #f5f3f0;      /* Lightest surface for content */
  --fg:              #2c2c34;      /* Near-black with blue undertone */
  --fg-dim:          #5c5c6c;      /* Medium gray, readable */
  --muted:           #9090a0;      /* Light gray for tertiary text */
  --accent:          #5a6f88;      /* Steel-blue, darker than dark-theme accent for contrast */
  --accent-hover:    #475b72;      /* Darker on hover (inverted from dark theme) */
  --border:          rgba(0, 0, 0, 0.10);
  --selected:        rgba(90, 111, 136, 0.10);
  --selected-border: rgba(90, 111, 136, 0.35);
  --error:           #b33a4a;      /* Slightly deeper red for light bg contrast */
  --badge-bg:        rgba(90, 111, 136, 0.12);
  --badge-fg:        #5a6f88;

  /* Hardcoded overrides needed */
  /* Popup bg: #f0eeeb instead of #252540 */
  /* Inline code bg: rgba(0, 0, 0, 0.05) instead of rgba(255,255,255,0.06) */
  /* Code block bg: rgba(0, 0, 0, 0.04) instead of rgba(0,0,0,0.3) */
  /* Strong text: var(--fg) instead of #fff */
  /* Hovered sidebar item text: var(--fg) instead of #fff */
}
```

**Variable mapping summary:**

| Variable           | Dark                          | Light                         |
|--------------------|-------------------------------|-------------------------------|
| `--bg`             | `#1a1a2e`                     | `#f0eeeb`                     |
| `--bg-sidebar`     | `#16162a`                     | `#e8e5e1`                     |
| `--bg-content`     | `#1e1e36`                     | `#f5f3f0`                     |
| `--fg`             | `#e0e0e0`                     | `#2c2c34`                     |
| `--fg-dim`         | `#a0a0b8`                     | `#5c5c6c`                     |
| `--muted`          | `#6b6b80`                     | `#9090a0`                     |
| `--accent`         | `#7c8fa8`                     | `#5a6f88`                     |
| `--accent-hover`   | `#94a8c4`                     | `#475b72`                     |
| `--border`         | `rgba(255,255,255,0.08)`      | `rgba(0,0,0,0.10)`           |
| `--selected`       | `rgba(124,143,168,0.15)`      | `rgba(90,111,136,0.10)`      |
| `--selected-border`| `rgba(124,143,168,0.4)`       | `rgba(90,111,136,0.35)`      |
| `--error`          | `#c45` (`#cc4455`)            | `#b33a4a`                     |
| `--badge-bg`       | `rgba(124,143,168,0.2)`       | `rgba(90,111,136,0.12)`      |
| `--badge-fg`       | `#94a8c4`                     | `#5a6f88`                     |

**Additional hardcoded values to override:**

| Dark value                     | Light replacement              | Locations                                  |
|--------------------------------|--------------------------------|--------------------------------------------|
| `#252540` (popup bg)           | `#f0eeeb`                      | bubble-toolbar, slash-menu, mention-popup, link-input, command-palette |
| `#fff` (strong/bold text)      | `var(--fg)`                    | `.block-text strong`, editor `strong`, hovered sidebar items |
| `rgba(255,255,255,0.06)` (inline code) | `rgba(0,0,0,0.05)`   | editor `code`                              |
| `rgba(255,255,255,0.08)` (toolbar hover) | `rgba(0,0,0,0.06)` | `.bt-btn:hover`                            |
| `rgba(255,255,255,0.15)` (block border hover) | `rgba(0,0,0,0.12)` | `.littera-block:hover`               |
| `rgba(0,0,0,0.3)` (code block bg) | `rgba(0,0,0,0.04)`       | editor `pre`                               |
| `rgba(0,0,0,0.3)` (popup shadow) | `rgba(0,0,0,0.12)`        | all popup `box-shadow`                     |
| `rgba(0,0,0,0.4)` (palette backdrop) | `rgba(0,0,0,0.15)`   | `.command-palette-backdrop`                |
| `rgba(124,143,168,0.3)` (pill border) | `rgba(90,111,136,0.25)` | `.mention-pill`                         |

To implement: extract every hardcoded value above into a CSS variable, or
use `[data-theme="light"]` selectors that target each specific rule.

---

## 7. Anti-Patterns to Avoid

These guidelines preserve the quiet, tool-like character of the interface.

### Color

- **No saturated colors.** The palette is entirely desaturated. Even the error
  red (`#cc4455`) is muted. Never introduce a bright blue, green, or orange.
- **No gradients.** Every surface is a flat color. Background variation comes
  from opacity and lightness shifts within a single hue family.
- **No color as decoration.** Color signals meaning: accent = interactive,
  error = destructive, badge-fg = metadata. If something has no semantic
  role, it should be `--fg`, `--fg-dim`, or `--muted`.

### Shape

- **No large border-radius.** UI chrome uses 3-4px radius. The only exception
  is the mention-pill (10px) which has a specific semantic reason (it looks
  like an inline tag). Buttons, cards, and panels should not exceed 6px.
- **No rounded-everything.** Avoid the trend of `border-radius: 12px` or
  `9999px` on containers and buttons.
- **No drop shadows for depth hierarchy.** Surface depth is communicated via
  background color shifts. Shadows are reserved for floating overlays
  (popups, toolbar, palette).

### Typography

- **No decorative fonts.** The app uses `system-ui` everywhere. Do not
  introduce display fonts, serif fonts, or handwriting fonts.
- **No large type.** The largest text in the app is `1.6rem` (picker title).
  Heading sizes in the editor top out at `1.5rem`. Keep new headings within
  this range.
- **No bold body text.** Body text is weight 400. Weight 500 is used only for
  titles (`h1`, entity name). Weight 600 is for headings and toolbar labels.
  Never use 700+ anywhere.

### Animation

- **No animations beyond 150ms.** The only animation in the app is the
  loading spinner. All interactive transitions are `0.1s`. Do not add
  slide-ins, fades, or bounces.
- **No animation on content.** Text, blocks, and sidebar items appear
  instantly. Never animate list items appearing or content loading.

### Layout

- **No cards with borders.** Sidebar items and list rows have no visible
  border. Selection state is a background fill + left accent. Do not add
  bordered card containers.
- **No icons.** The app uses text characters for all indicators: `+` for add,
  `x` (times) for delete, `H1`/`H2`/`</>` for toolbar labels. The slash-menu
  uses plain text icons (`H1`, `</>`, `--`, `"`). Do not introduce an icon
  library (no Lucide, Heroicons, Font Awesome).
- **No horizontal dividers between actions.** Action buttons sit next to
  section headers without separator lines. Sections are separated by vertical
  whitespace (`margin-bottom: 1.5rem`), not horizontal rules.

### Behavior

- **No toast notifications.** Errors display in the fixed top banner. Success
  states are silent (the dirty indicator disappearing is the confirmation).
- **No confirmation modals.** The current pattern for destructive actions is
  direct execution (delete). If confirmation is needed in the future, use
  an inline pattern (e.g., the delete button text changes to "Sure?" on first
  click) rather than a modal dialog.
- **No tooltips on hover.** Use the native `title` attribute if a hint is
  needed. Do not implement custom tooltip components.

### General

- **Do not add chrome that the writer didn't ask for.** Littera is a writing
  tool. Every pixel of non-prose UI is a cost. When in doubt, leave it out.
- **Do not add configuration UI.** If a setting is needed, it goes in the CLI
  or a config file. The desktop app is for writing, not for configuring.
- **Do not add onboarding.** No welcome screens, feature tours, or tip
  bubbles. The interface should be self-evident.

---

## Appendix: Border Radius Reference

| Context              | Radius |
|----------------------|--------|
| Sidebar item         | `4px`  |
| Badge                | `3px`  |
| Inline code          | `3px`  |
| Popup container      | `6px`  |
| Picker button        | `6px`  |
| Scrollbar thumb      | `3px`  |
| Code block           | `4px`  |
| Mention pill         | `10px` |
| Toolbar button       | `3px`  |
| Action button        | `3px`  |
| Rename input         | `3px`  |

## Appendix: Z-Index Stack

| Layer                | z-index |
|----------------------|---------|
| Popup overlays       | `50`    |
| Error banner         | `100`   |
| Command palette      | `200`   |
