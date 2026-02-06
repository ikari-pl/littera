# Phase 2 — Desktop App (Detailed Plan)

## Goal

Build an immersive, WYSIWYG-leaning writing environment backed by Littera's model.

The desktop app is where Littera becomes **transformative rather than merely powerful** (Manifesto). It must feel calm and focused while preserving the structural and semantic model invisibly beneath the surface.

## Dependencies

- Requires Phase 1A (CLI + schema) and Phase 1B (TUI) to be complete. **Both are done.**
- Any new behavior discovered during desktop work must land in the CLI first.

---

## 1. Architecture Decision: Framework

### Constraints

Littera's core is Python + embedded PostgreSQL. The desktop app must:

- Start and manage the embedded PG instance (bootstrap lifecycle)
- Communicate with the Python data layer (queries, actions, migrations)
- Render a rich text editor in a native-feeling window
- Work offline, permanently — no network dependency
- Bundle cleanly on macOS (primary), with Linux/Windows as secondary targets

### Options Evaluated

| Criteria | Tauri v2 | Electron | Native (Swift/AppKit) |
|---|---|---|---|
| Bundle size | ~5 MB | ~150 MB | ~2 MB |
| Memory (idle) | ~40 MB | ~500 MB | ~30 MB |
| Backend language | Rust | Node.js | Swift |
| Python integration | Sidecar process | child_process.spawn | NSTask / Process |
| Rich text editors | Web-based (ProseMirror, Tiptap) | Web-based (ProseMirror, Tiptap) | NSTextView or WebView |
| Cross-platform | macOS, Windows, Linux | macOS, Windows, Linux | macOS only |
| WebView consistency | WebKit (macOS/Linux), Chromium (Windows) | Chromium everywhere | N/A (native) |
| Ecosystem maturity | Stable but young (v2 Oct 2024) | Very mature (10+ years) | Mature (Apple only) |
| Added language to stack | Rust | JavaScript/TypeScript | Swift |

### Recommendation: Tauri v2

**Rationale:**

1. **Lightweight and local-first aligned.** Littera is built for durability, not convenience. A 5 MB bundle that uses the system WebView fits the philosophy better than shipping 150 MB of Chromium.

2. **Sidecar pattern is clean.** Littera already has a Python process that manages embedded PG. Tauri's sidecar support is first-class — the Python backend runs as a managed subprocess, communicating over localhost HTTP or stdio JSON-RPC. This is not a hack; it's the documented architecture for non-Rust backends.

3. **Rust is boring in the right way.** The Tauri shell is thin glue: window management, sidecar lifecycle, IPC forwarding. It does not contain business logic. Rust's compile-time guarantees make this glue layer robust without being clever.

4. **Web editor ecosystem is available.** ProseMirror / Tiptap run in any WebView. The WYSIWYG editing layer is framework-agnostic.

5. **Cross-platform matters eventually.** Native Swift would lock us to macOS. Tauri gives us Linux and Windows for free.

**Trade-offs accepted:**

- WebView rendering differs between macOS (WebKit) and Windows (Chromium). CSS must be tested on both.
- Tauri's ecosystem is younger than Electron's. Documentation has gaps. We accept this because the shell layer is intentionally thin.
- Rust is a new language in the stack. Mitigated by keeping the Rust layer minimal (no business logic).

### Decision to be finalized in: `littera-gkn`

This recommendation should be validated with a proof-of-concept spike before committing. See Section 6.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────┐
│                 Tauri Shell                  │
│  (Rust: window mgmt, sidecar, IPC bridge)   │
├─────────────────────────────────────────────┤
│              WebView (Frontend)              │
│  TypeScript + Tiptap/ProseMirror editor     │
│  State: reducer pattern (port from TUI)     │
│  Styling: CSS (calm, immersive)             │
├────────────────┬────────────────────────────┤
│   IPC bridge   │   localhost HTTP / JSON    │
├────────────────┴────────────────────────────┤
│            Python Sidecar                   │
│  littera.desktop.server (new module)        │
│  - Exposes CLI operations as HTTP/JSON-RPC  │
│  - Manages embedded PG lifecycle            │
│  - Runs queries and actions                 │
│  - Applies migrations                       │
├─────────────────────────────────────────────┤
│           Embedded PostgreSQL               │
│  (same Zonky-based binary as CLI/TUI)       │
└─────────────────────────────────────────────┘
```

### Key Principle: Python owns all data access

The Rust shell and TypeScript frontend **never** touch PostgreSQL directly. All reads and writes go through the Python sidecar, which reuses the existing `littera.db` and `littera.cli` modules. This ensures:

- CLI remains authoritative (Invariant)
- No UI-only state (Invariant)
- Migrations are applied consistently
- Business logic lives in one place (Python)

---

## 3. Python Sidecar: `littera.desktop.server`

New module: `src/littera/desktop/server.py`

A lightweight HTTP server (or JSON-RPC over stdio) that exposes Littera operations to the frontend.

### API Surface (initial)

```
# Structure (read)
GET  /api/documents                    → list documents
GET  /api/documents/:id/sections       → list sections
GET  /api/sections/:id/blocks          → list blocks
GET  /api/blocks/:id                   → block detail (text, language, mentions)

# Structure (write)
POST /api/documents                    → create document
POST /api/sections                     → create section
POST /api/blocks                       → create block
PUT  /api/blocks/:id                   → update block text
DELETE /api/{documents|sections|blocks}/:id → delete

# Entities
GET  /api/entities                     → list entities
GET  /api/entities/:id                 → entity detail (labels, mentions, note)
POST /api/entities                     → create entity
POST /api/mentions                     → link entity to block

# Metadata
GET  /api/status                       → work info, PG status
```

### Implementation approach

- Use `http.server` or a minimal framework (no large dependencies)
- Reuse `littera.tui.queries` and `littera.tui.actions` directly — they already separate DB reads from writes
- Manage PG lifecycle via existing `bootstrap.py` (including WAL recovery)
- Bind to `127.0.0.1` only — no network exposure

### Alternative: stdio JSON-RPC

If HTTP adds unwanted complexity, communicate over stdin/stdout using JSON-RPC. Tauri's sidecar API supports this natively. Trade-off: harder to debug (no curl), but zero port management.

**Decision deferred to spike.**

---

## 4. Frontend: WYSIWYG-Leaning Editor

### Editor Technology: Tiptap (ProseMirror)

Tiptap provides:

- Block-level editing (maps to Littera blocks)
- Schema-constrained editing (prevents invalid structure)
- Collaborative editing primitives (useful later, not now)
- Extensions for custom node types
- TypeScript-first API

### Mapping Littera Blocks to ProseMirror

| Littera Concept | ProseMirror Concept |
|---|---|
| Block | Top-level node in the document |
| Block type (paragraph, list, code) | Node type |
| Block text (Markdown) | Node content (serialized to/from Markdown) |
| Section boundary | Non-editable divider node or separate editor instance |
| Mention | Mark or inline decoration with entity reference |

### What "WYSIWYG-leaning" means concretely

- **Visible**: formatted text, heading sizes, list indentation, code blocks
- **Invisible but present**: block boundaries (subtle affordances on hover), entity mentions (highlighted on focus), section structure (sidebar or breadcrumb)
- **Never visible during writing**: UUIDs, metadata, internal state
- **Recoverable on demand**: full structural view (outline mode), entity inspector, block properties

### State Management

Port the TUI's reducer pattern to TypeScript:

```typescript
// Same architecture as littera.tui.state
type Action =
  | { type: "outline/push"; element: PathElement }
  | { type: "outline/pop" }
  | { type: "outline/select"; kind: string; id: string }
  | { type: "editor/start"; target: EditTarget; text: string }
  | { type: "editor/exit" }
  // ...

function reduce(state: AppState, action: Action): AppState { ... }
```

This is a direct port, not a reinvention. The TUI proved the reducer model works for Littera's navigation and editing patterns.

---

## 5. UI/UX Design Principles

### Calm Writing

- Full-screen editor as the default view
- Minimal chrome — title bar, maybe a subtle breadcrumb
- No visible toolbar (formatting via keyboard shortcuts or slash commands)
- Light/dark mode, no other theme complexity

### Structural Affordances (Gentle)

- Outline sidebar (toggleable, hidden by default)
- Breadcrumb showing: Work > Document > Section
- Block boundaries visible only on hover or selection
- Section breaks as subtle horizontal rules

### Entity Awareness (Non-Intrusive)

- Mentions highlighted with a subtle underline or color
- Hovering a mention shows entity type and label in a tooltip
- Entity inspector panel (toggleable, like outline)
- Linking an entity: select text → keyboard shortcut → type entity name

### Navigation

- Keyboard-driven (Cmd+P for document switching, Cmd+Shift+O for outline)
- Mouse-friendly but keyboard-first
- Same conceptual model as TUI: Work → Document → Section → Block

---

## 6. Implementation Roadmap

### Phase 2A: Spike (1-2 sessions)

**Goal:** Validate the architecture with a minimal proof of concept.

- [ ] Create a minimal Tauri app that spawns the Python sidecar
- [ ] Python sidecar: expose `/api/status` and `/api/documents` endpoints
- [ ] Frontend: render document list from API response
- [ ] Verify: PG starts, data loads, window renders

**Exit criteria:** Can open a Littera work dir and see the document list in a desktop window.

**This spike resolves `littera-gkn` (technology decision).**

### Phase 2B: Read-Only Navigation (2-3 sessions)

**Goal:** Port TUI's navigation to the desktop.

- [ ] Full API surface for reading (documents, sections, blocks, entities)
- [ ] TypeScript state management (reducer pattern)
- [ ] Outline sidebar with drill-down navigation
- [ ] Block content rendering (Markdown → formatted text)
- [ ] Entity list and detail panel

**Exit criteria:** Can navigate the full Work → Document → Section → Block hierarchy and view all content.

### Phase 2C: Block Editing (2-3 sessions)

**Goal:** Implement the core writing experience.

- [ ] Tiptap editor integration
- [ ] Block-level editing with Markdown round-trip (parse on load, serialize on save)
- [ ] Save via API (PUT /api/blocks/:id)
- [ ] Undo/redo (editor-level, mirroring TUI pattern)
- [ ] Create document / section / block via UI

**Exit criteria:** Can create and edit content through the desktop app, with changes persisted to PG and visible in CLI/TUI.

### Phase 2D: Mentions and Entities (1-2 sessions)

**Goal:** Semantic layer in the editor.

- [ ] Mention highlighting in editor (ProseMirror marks)
- [ ] Entity linking flow (select text → link to entity)
- [ ] Entity creation from editor
- [ ] Entity tooltips on hover

**Exit criteria:** Can link entities to blocks and see mentions inline.

### Phase 2E: Polish and Immersion (2-3 sessions)

**Goal:** Make it feel like a real writing tool.

- [ ] Full-screen distraction-free mode
- [ ] Keyboard shortcut system
- [ ] Light/dark theme
- [ ] Smooth transitions and loading states
- [ ] Error handling and recovery (including WAL corruption dialog, ported from TUI)
- [ ] Bundling and distribution (macOS .dmg at minimum)

**Exit criteria:** The app is usable for daily writing. A writer can open it, navigate to a section, and write without encountering machinery.

---

## 7. Files to Create

| Path | Purpose |
|---|---|
| `src/littera/desktop/server.py` | Python sidecar HTTP/JSON-RPC server |
| `src/littera/desktop/__init__.py` | Package init |
| `desktop/` | Tauri project root (Rust shell + frontend) |
| `desktop/src-tauri/` | Rust Tauri configuration and sidecar management |
| `desktop/src/` | TypeScript frontend (Tiptap editor, state, views) |

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Model erosion via WYSIWYG | High | All writes go through Python sidecar, which enforces CLI semantics. Editor schema constrains structure. |
| UI-only state | High | Frontend state is a pure function of API responses + user input. No DB writes from frontend. |
| WebView rendering inconsistency | Medium | Primary target is macOS (WebKit). Test on Windows (Chromium) before shipping. |
| Sidecar latency | Medium | Local HTTP on loopback is ~1ms. Batch reads where possible. |
| Tiptap ↔ Markdown fidelity | Medium | Define a strict subset of Markdown that round-trips cleanly. Test extensively. |
| Bundle size (Python sidecar) | Low | PyInstaller or similar for single-binary Python. Acceptable trade-off for local-first. |
| Rust learning curve | Low | Rust layer is <200 lines of glue. No business logic. |

---

## 9. What This Phase Does NOT Include

- Bilingual split-panel editing (Phase 3 / Linguistics)
- Block alignments
- AI-assisted features
- Cloud sync
- Mobile targets
- Collaborative editing

These are explicitly deferred. The desktop app ships as a single-user, single-language, local-only writing environment first.

---

## 10. Exit Criteria

- A writer can open a Littera work, navigate the structure, and write/edit blocks in a calm, immersive environment.
- All changes are visible in CLI and TUI (no divergence).
- No UI-only state exists.
- The app bundles and launches on macOS without requiring manual setup.
- Existing test suite passes (Python backend unchanged in behavior).

---

## Related Issues

- `littera-ign` — Phase 2 epic
- `littera-gkn` — Technology decision (resolved by spike in Phase 2A)
- `littera-468` — WYSIWYG semantics (addressed in Section 4)
- `littera-6ih` — Port TUI patterns (addressed in Sections 4 and 6B)
