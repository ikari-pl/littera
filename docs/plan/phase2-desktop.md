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
| Rich text editors | Web-based (ProseMirror) | Web-based (ProseMirror) | NSTextView or WebView |
| Cross-platform | macOS, Windows, Linux | macOS, Windows, Linux | macOS only |
| WebView consistency | WebKit (macOS/Linux), Chromium (Windows) | Chromium everywhere | N/A (native) |
| Ecosystem maturity | Stable but young (v2 Oct 2024) | Very mature (10+ years) | Mature (Apple only) |
| Added language to stack | Rust | JavaScript/TypeScript | Swift |

### Recommendation: Tauri v2

**Rationale:**

1. **Lightweight and local-first aligned.** Littera is built for durability, not convenience. A 5 MB bundle that uses the system WebView fits the philosophy better than shipping 150 MB of Chromium.

2. **Sidecar pattern is clean.** Littera already has a Python process that manages embedded PG. Tauri's sidecar support is first-class — the Python backend runs as a managed subprocess, communicating over localhost HTTP or stdio JSON-RPC. This is not a hack; it's the documented architecture for non-Rust backends.

3. **Rust is boring in the right way.** The Tauri shell is thin glue: window management, sidecar lifecycle, IPC forwarding. It does not contain business logic. Rust's compile-time guarantees make this glue layer robust without being clever.

4. **Web editor ecosystem is available.** ProseMirror runs in any WebView. The editing layer is framework-agnostic.

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
+---------------------------------------------+
|                 Tauri Shell                  |
|  (Rust: window mgmt, sidecar, IPC bridge)   |
+---------------------------------------------+
|              WebView (Frontend)              |
|  TypeScript + custom ProseMirror editor     |
|  State: reducer pattern (port from TUI)     |
|  Styling: CSS (calm, immersive)             |
+----------------+----------------------------+
|   IPC bridge   |   localhost HTTP / JSON    |
+----------------+----------------------------+
|            Python Sidecar                   |
|  littera.desktop.server (new module)        |
|  - Exposes CLI operations as HTTP/JSON-RPC  |
|  - Manages embedded PG lifecycle            |
|  - Runs queries and actions                 |
|  - Applies migrations                       |
+---------------------------------------------+
|           Embedded PostgreSQL               |
|  (same Zonky-based binary as CLI/TUI)       |
+---------------------------------------------+
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
GET  /api/documents                    -> list documents
GET  /api/documents/:id/sections       -> list sections
GET  /api/sections/:id/blocks          -> list blocks (ordered, with text)
GET  /api/blocks/:id                   -> block detail (text, language, mentions)

# Structure (write)
POST /api/documents                    -> create document
POST /api/sections                     -> create section
POST /api/blocks                       -> create block
PUT  /api/blocks/:id                   -> update block text
PUT  /api/blocks/batch                 -> update multiple dirty blocks
DELETE /api/{documents|sections|blocks}/:id -> delete

# Entities
GET  /api/entities                     -> list entities
GET  /api/entities/:id                 -> entity detail (labels, mentions, note)
POST /api/entities                     -> create entity
POST /api/mentions                     -> link entity to block

# Metadata
GET  /api/status                       -> work info, PG status
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

## 4. Editor: Custom ProseMirror (Not Tiptap)

### Why custom, not Tiptap

Tiptap is a convenience layer over ProseMirror (extensions, Vue/React bindings, plugins). For Littera's narrow, controlled editing needs, going straight to ProseMirror is simpler:

- **Fewer abstractions to fight.** Tiptap's extension system adds indirection. For a fixed schema with known block types, direct ProseMirror configuration is more explicit and testable.
- **Full control over Markdown serialization.** Tiptap's Markdown extensions (community and official) all lose formatting in round-trips. With a custom serializer, we define exactly what our Markdown looks like.
- **Mention pills with custom syntax.** We need inline atom nodes that serialize to `{@Label|entity:uuid}` and round-trip perfectly. At the ProseMirror level this is ~50 lines of serializer + parser. With Tiptap it requires fighting the extension system.
- **Boring code.** ProseMirror core is stable, well-documented, and maintained by one person (Marijn Haverbeke) with a track record of decades. No framework churn.

The editor is approximately: ProseMirror core + `prosemirror-markdown` + our schema + our serializer. No Tiptap, no Milkdown, no third-party Markdown bridge.

### Markdown Round-Trip Strategy

**All ProseMirror-based editors normalize Markdown.** The document model is semantic, not syntactic. Known normalizations we accept:

- `_emphasis_` becomes `*emphasis*` (same `em` mark)
- Setext headings (`===`) become ATX (`#`)
- List markers normalize to a single style (`-`)
- Extra blank lines collapse

**This is acceptable** because meaning is preserved. We define our canonical Markdown subset and the serializer produces it deterministically. What goes into the DB is the serializer's output, not the user's original formatting.

### Continuous Document from Discrete Blocks

The editor displays a section's blocks as a **single continuous document** while keeping each block independently managed in the database.

#### Schema: `isolating` top-level nodes

```
doc -> littera_block+ -> (paragraph | heading | bullet_list | code_block)+
```

Each `littera_block` node carries `{id, block_type, language}` as attributes. The critical property is **`isolating: true`**, which gives us:

- **Typing flows naturally** within a block — feels like a continuous document
- **Backspace at block start won't merge** with the previous block
- **Text selection CAN span blocks** — click-drag works naturally across boundaries
- **Enter creates a new paragraph *within* the block** (isolating keeps `splitBlock` contained)
- **New block creation is an explicit command** (Shift+Enter or Mod+Enter)

This is the pattern BlockNote uses (`blockContainer` with `isolating: true`) and is explicitly recommended by ProseMirror's author over multi-instance approaches.

```typescript
const litteraSchema = new Schema({
  nodes: {
    doc: { content: "littera_block+" },

    littera_block: {
      content: "block+",
      attrs: {
        id:         { default: null },
        block_type: { default: "prose" },
        language:   { default: "en" },
      },
      isolating: true,    // prevents edits crossing block boundaries
      defining: true,     // preserves wrapper on replace operations
      toDOM(node) {
        return ["section", {
          class: "littera-block",
          "data-block-id": node.attrs.id,
        }, 0]
      },
    },

    paragraph: { content: "inline*", group: "block", /* ... */ },
    heading:   { content: "inline*", group: "block", attrs: { level: {} } },
    code_block: { content: "text*", group: "block", /* ... */ },
    // ... bullet_list, ordered_list
    text: { group: "inline" },
    mention: {
      inline: true,
      group: "inline",
      atom: true,        // non-editable, cursor skips over it
      attrs: {
        id:    { default: "" },
        label: { default: "" },
      },
    },
  },
  marks: { strong: {}, em: {}, code: {}, link: {} },
})
```

#### Why NOT multiple ProseMirror instances

ProseMirror's author explicitly advises against stacking multiple EditorViews:

- Cross-block text selection breaks (can't select across `contentEditable` boundaries)
- Clipboard operations across blocks break
- Undo/redo requires a custom stack (each instance has its own history)
- Arrow-key navigation between instances requires manual focus management

Single instance with `isolating: true` gives us all the boundary enforcement with none of these problems.

#### Dirty tracking via structural sharing

ProseMirror uses immutable documents with structural sharing. If a block node hasn't changed, it's the **exact same JS object reference**. This makes dirty detection trivial:

```typescript
function findDirtyBlocks(oldDoc, newDoc): string[] {
  const dirty: string[] = []
  const max = Math.max(oldDoc.childCount, newDoc.childCount)
  for (let i = 0; i < max; i++) {
    const oldChild = i < oldDoc.childCount ? oldDoc.child(i) : null
    const newChild = i < newDoc.childCount ? newDoc.child(i) : null
    if (oldChild !== newChild) {
      const id = newChild?.attrs?.id || oldChild?.attrs?.id
      if (id) dirty.push(id)
    }
  }
  return dirty
}
```

On save, only serialize and persist the dirty blocks. On load, reconstruct the doc from the ordered block list.

#### Block boundary UX

- **Visual**: Blocks are separated by subtle spacing or a faint rule. On hover, a block shows a gentle highlight or a drag handle in the left gutter.
- **Enter**: Creates a new paragraph within the current block.
- **Shift+Enter** (or Mod+Enter): Creates a new `littera_block` after the current one, with a fresh UUID.
- **Backspace at block start**: Stops at the block boundary (does not merge). If the block is empty, deletes it entirely.
- **Drag handle**: Reorder blocks within the section.

### Mention Pills

Mentions render as **inline atom nodes** — non-editable pills that display the entity label and store the entity UUID.

#### In the editor

A styled `<span>` with a background color, rendered via a ProseMirror NodeView:

```
"Written by {@Albert Camus|entity:550e8400-...} in 1942."
              ^^^^^^^^^^^^^
              Renders as: [Albert Camus] (styled pill)
```

#### In storage (Markdown)

```markdown
Written by {@Albert Camus|entity:550e8400-e29b-41d4-a716-446655440000} in 1942.
```

This syntax was chosen because:

- `{@` is distinctive and doesn't collide with standard Markdown
- The pipe separates display label from reference
- `entity:uuid` is self-describing
- It reads naturally in raw Markdown
- Round-trips perfectly (custom serializer + custom markdown-it inline rule)

#### Implementation

Serializer (~5 lines):

```typescript
mention(state, node) {
  state.write(`{@${node.attrs.label}|entity:${node.attrs.id}}`)
}
```

Parser (markdown-it inline rule, ~25 lines): Recognizes `{@...}`, extracts label and UUID, emits a `mention` token that maps to the ProseMirror mention node.

NodeView: Renders as a `<span class="mention-pill">` with `contenteditable="false"`. Styled via CSS (subtle background, border-radius, non-editable).

### State Management

Port the TUI's reducer pattern to TypeScript:

```typescript
// Same architecture as littera.tui.state
type Action =
  | { type: "outline/push"; element: PathElement }
  | { type: "outline/pop" }
  | { type: "outline/select"; kind: string; id: string }
  | { type: "editor/open"; sectionId: string; blocks: Block[] }
  | { type: "editor/save-dirty" }
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
- Block boundaries: subtle spacing, drag handle on hover in left gutter
- Section breaks as horizontal rules between block groups

### Entity Awareness (Non-Intrusive)

- Mentions rendered as inline pills (subtle background, no border)
- Hovering a mention pill shows entity type and label in a tooltip
- Entity inspector panel (toggleable, like outline)
- Linking an entity: select text, press Cmd+L, type entity name, confirm

### Navigation

- Keyboard-driven (Cmd+P for document switching, Cmd+Shift+O for outline)
- Mouse-friendly but keyboard-first
- Same conceptual model as TUI: Work > Document > Section > Block
- Section view is the primary editing unit (all blocks in a section rendered as continuous document)

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
- [ ] Section view: render blocks as continuous formatted text (read-only ProseMirror)
- [ ] Entity list and detail panel

**Exit criteria:** Can navigate the full hierarchy and view all content as formatted text.

### Phase 2C: Block Editing (2-3 sessions)

**Goal:** Implement the core writing experience.

- [ ] ProseMirror schema with `littera_block` isolating nodes
- [ ] Custom Markdown serializer and parser (prosemirror-markdown + markdown-it)
- [ ] Dirty block tracking via structural sharing
- [ ] Save dirty blocks via `PUT /api/blocks/batch`
- [ ] New block creation (Shift+Enter)
- [ ] Block reordering (drag handle)
- [ ] Create document / section via UI
- [ ] Undo/redo (ProseMirror's built-in history plugin)

**Exit criteria:** Can write and edit content through the desktop app, with changes persisted to PG and visible in CLI/TUI.

### Phase 2D: Mentions and Entities (1-2 sessions)

**Goal:** Semantic layer in the editor.

- [ ] Mention node type with `{@label|entity:uuid}` Markdown syntax
- [ ] Mention pill NodeView (styled, non-editable atom)
- [ ] Entity linking flow (select text, Cmd+L, type name, confirm)
- [ ] Entity creation from editor
- [ ] Mention tooltips on hover

**Exit criteria:** Can link entities to blocks and see mentions as inline pills.

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
| `desktop/src/editor/` | ProseMirror editor (schema, serializer, parser, NodeViews) |
| `desktop/src/state/` | TypeScript state management (reducer, actions) |
| `desktop/src/views/` | UI components (outline, entity panel, breadcrumb) |

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Model erosion via WYSIWYG | High | All writes go through Python sidecar, which enforces CLI semantics. ProseMirror schema constrains structure. |
| UI-only state | High | Frontend state is a pure function of API responses + user input. No DB writes from frontend. |
| Markdown round-trip normalization | Medium | We own the serializer. Accept deterministic normalization (emphasis, headings, list markers). Define our canonical subset. |
| WebView rendering inconsistency | Medium | Primary target is macOS (WebKit). Test on Windows (Chromium) before shipping. |
| Sidecar latency | Medium | Local HTTP on loopback is ~1ms. Batch dirty block saves. |
| Mention syntax conflicts | Low | `{@...}` doesn't collide with any standard Markdown. Parser is strict about format. |
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
- Blocks within a section display as a continuous document but persist independently.
- Entity mentions render as inline pills and round-trip through `{@label|entity:uuid}` Markdown syntax.
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
