# Littera Rust Rewrite Plan

Rewrite Littera from Python + embedded PostgreSQL to Rust + libSQL.
Produces a single binary for CLI/TUI, and a single Tauri .app for Desktop.
Structured as a learn-Rust-by-building project.

---

## Why

- Single binary distribution (no Python runtime, no PG binary)
- CLI + TUI ship as one ~15MB executable
- Desktop ships as one Tauri .app (~20MB) with no sidecar process
- libSQL embeds as a library (no external database process)
- Compile-time guarantees catch bugs Python can't

## What stays the same

- The data model: Work > Document > Section > Block
- The schema (adapted from PG to libSQL/SQLite dialect)
- The CLI command surface (`littera doc add`, `littera entity list`, etc.)
- The Desktop frontend JS (ProseMirror editor, render.js, state.js)
- The HTTP API contract (same routes, same JSON shapes)
- The design principles in MANIFESTO.md

## What changes

| Layer | Python | Rust |
|-------|--------|------|
| CLI framework | Typer | clap (derive macros) |
| TUI framework | Textual | ratatui + crossterm |
| Desktop shell | Tauri + Python sidecar | Tauri (Rust IS the backend) |
| Database | embedded PostgreSQL | libSQL (compiled in) |
| JSON | stdlib json | serde + serde_json |
| HTTP (desktop) | BaseHTTPRequestHandler | axum (embedded in Tauri) |
| Morphology | inflect + custom | english crate + custom port |
| Testing | pytest + subprocess | assert_cmd + built-in #[test] |

## Test reuse strategy

The existing test suites are the safety net for the rewrite. They validate
behavior, not implementation.

### Reusable as-is (black-box)

**CLI tests (108 tests in `tests/test_*.py`):**
These invoke `python -m littera` via subprocess and check stdout. To reuse
them during the rewrite:

1. Keep the Python test files as they are
2. Point them at the Rust binary instead: `LITTERA_BIN=./target/release/littera`
3. Change `run()` helper to invoke the Rust binary
4. Tests pass when the Rust CLI produces identical output

This is the primary correctness gate. Each phase below ends when the
relevant subset of CLI tests passes against the Rust binary.

**Desktop Playwright tests (63 tests in `desktop/tests/*.spec.js`):**
These mock the sidecar HTTP API via route interception. Once the Rust
backend serves the same routes with the same JSON shapes, the mocks can
be replaced with the real backend and the tests still pass. During
development, mocks continue to work unchanged.

### Must be ported

**Linguistics unit tests** (`test_linguistics.py`, `test_linguistics_en.py`,
`test_polish_morphology.py` — 47 tests): These call Python functions
directly. Port to Rust `#[test]` functions with the same test cases.

**TUI state tests** (`tests/tui/*.py` — 14 tests): These test Python
dataclasses and dispatch. Port to Rust tests for the equivalent structs
and reducer.

---

## Crate dependencies

```toml
[dependencies]
clap = { version = "4", features = ["derive"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1", features = ["v4", "serde"] }
libsql = "0.6"                   # or rusqlite if sync not needed
tokio = { version = "1", features = ["full"] }
ratatui = "0.30"
crossterm = "0.29"

# Desktop only (behind feature flag)
axum = "0.8"
tauri = "2"

# Linguistics
english = "1"                    # morphology engine

[dev-dependencies]
assert_cmd = "2"                 # black-box CLI testing
predicates = "3"                 # assertion helpers
tempfile = "3"                   # tmpdir for test databases
```

---

## Project structure

```
littera-rs/
  Cargo.toml
  src/
    main.rs                      # CLI entry point (clap)
    lib.rs                       # shared library root
    db/
      mod.rs                     # libSQL connection, migrations
      schema.sql                 # embedded SQL (include_str!)
    model/
      mod.rs                     # Work, Document, Section, Block, Entity, ...
    cli/
      mod.rs                     # clap App definition
      doc.rs                     # document subcommands
      section.rs                 # section subcommands
      block.rs                   # block subcommands
      entity.rs                  # entity subcommands
      io.rs                      # import/export
    tui/
      mod.rs                     # ratatui app loop
      state.rs                   # AppState, actions, reducer
      views/                     # render functions (outline, entities, editor, ...)
      queries.rs                 # DB reads for view state
      actions.rs                 # DB writes
    desktop/
      mod.rs                     # axum server (same routes as Python sidecar)
      handlers.rs                # request handlers
    linguistics/
      mod.rs                     # surface_form() dispatcher
      en.rs                      # English morphology (port from Python)
  tests/
    cli_integration.rs           # assert_cmd black-box tests
    db_integration.rs            # real libSQL tests
    linguistics.rs               # morphology unit tests
  desktop/                       # frontend JS (copied from Python version)
    src/
      main.js
      render.js
      state.js
      api.js
      ...
    tests/                       # Playwright tests (reused as-is)
```

---

## Phases

Each phase teaches specific Rust concepts and ends with a testable
milestone. Work through them in order.

### Phase 0: Scaffold and schema (Rust basics)

**You will learn:** project setup, modules, `include_str!`, basic types,
String vs &str, the `?` operator.

**Do:**
1. `cargo init littera-rs`
2. Set up the module tree (`db/`, `model/`, `cli/`)
3. Adapt `db/schema.sql` from PG to SQLite dialect:
   - `UUID` becomes `TEXT`
   - `JSONB` becomes `TEXT` (JSON stored as text, parsed via serde)
   - `SERIAL` becomes `INTEGER PRIMARY KEY`
   - `NOW()` becomes `datetime('now')`
   - Keep all FK constraints with CASCADE
4. Write `db/mod.rs`: open libSQL connection, run migrations via
   `include_str!("schema.sql")`
5. Define model structs in `model/mod.rs`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: String,
    pub work_id: String,
    pub title: String,
    pub order_index: Option<i32>,
}
```

**Test gate:** `cargo test` — database opens, schema creates all 9 tables,
a document can be inserted and read back.

**Rust concepts introduced:**
- Cargo, crates, modules (`mod`, `pub`, `use`)
- Structs with `derive` macros
- `String` vs `&str` (ownership basics)
- `Result<T, E>` and the `?` operator
- `include_str!` for embedding files

---

### Phase 1: CLI foundation (ownership, borrowing, enums)

**You will learn:** clap derive macros, ownership/borrowing through
function calls, enums for subcommands, pattern matching.

**Do:**
1. Define CLI structure with clap:

```rust
#[derive(Parser)]
#[command(name = "littera")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Doc {
        #[command(subcommand)]
        action: DocAction,
    },
    // ...
}
```

2. Implement document CRUD: `doc add`, `doc list`, `doc delete`,
   `doc rename`, `doc move`
3. Implement section CRUD (same pattern)
4. Implement block CRUD + `block set-language`

**Test gate:** Adapt the Python `test_invariants.py` helper to invoke
the Rust binary. Run the document/section/block subset of CLI tests.
They should produce identical output.

**Rust concepts introduced:**
- Enums with data (algebraic data types)
- Pattern matching (`match`)
- Borrowing (`&`, `&mut`) through DB connection passing
- Lifetime elision (the compiler handles it — notice you didn't write `'a`)
- Error handling patterns (`anyhow` or custom error enum)

---

### Phase 2: Entities and mentions (traits, generics)

**You will learn:** traits, generic functions, iterators, closures.

**Do:**
1. Implement entity commands: `entity add`, `entity list`, `entity delete`
2. Entity labels: `entity label-add`, `entity label-delete`
3. Entity properties: `entity property-set`, `entity property-delete`
   - Properties are JSONB in PG, stored as JSON TEXT in libSQL
   - Use `serde_json::Value` for dynamic JSON manipulation
4. Entity notes: `entity note-show`, `entity note-set`
5. Mentions: `mention add`, `mention list`, `mention delete`

**Introduce a trait for DB operations:**

```rust
trait Queryable {
    fn find_by_id(conn: &Connection, id: &str) -> Result<Self>
    where
        Self: Sized;
    fn list_all(conn: &Connection) -> Result<Vec<Self>>
    where
        Self: Sized;
}
```

This is optional — don't force it if plain functions feel cleaner.
Rust rewards simplicity over abstraction.

**Test gate:** Full entity/mention CLI tests pass against Rust binary.

**Rust concepts introduced:**
- Traits (Rust's interfaces)
- `where` clauses and trait bounds
- Iterators (`.map()`, `.filter()`, `.collect()`)
- Closures (`|x| x.name`)
- `serde_json::Value` for dynamic JSON
- `Option<T>` patterns (`.unwrap_or()`, `.map()`, `if let`)

---

### Phase 3: Alignments, reviews, import/export (error handling, file I/O)

**You will learn:** custom error types, file I/O, serialization
roundtrips, the `From` trait for error conversion.

**Do:**
1. Alignment commands: `alignment add`, `alignment list`,
   `alignment delete`, `alignment gaps`
2. Review commands: `review add`, `review list`, `review delete`
3. Export: `export json`, `export markdown`
4. Import: `import json` (with entity deduplication and ID mapping)

**Define a project-wide error type:**

```rust
#[derive(Debug)]
enum LitteraError {
    Db(libsql::Error),
    Io(std::io::Error),
    Json(serde_json::Error),
    NotFound(String),
    Conflict(String),
}
```

Implement `From<libsql::Error>` for `LitteraError`, etc., so `?`
works transparently across error types.

**Test gate:** All 108 CLI tests pass. The Rust binary is a drop-in
replacement for `python -m littera`.

**Rust concepts introduced:**
- Custom error types with `enum`
- `From` trait for error conversion
- `std::fs` (File, read_to_string, write)
- `serde::Serialize` / `Deserialize` for roundtrip
- `impl From<X> for Y` pattern
- The `thiserror` crate (optional, reduces boilerplate)

---

### Phase 4: Linguistics engine (modules, testing, pure functions)

**You will learn:** module organization, comprehensive `#[test]` suites,
pure functions, string processing in Rust.

**Do:**
1. Port `en.py` to `linguistics/en.rs`:
   - Irregular verb table (`HashMap` or `phf` for compile-time maps)
   - Irregular comparison table
   - Regular inflection rules (_regular_past, _regular_3sg, etc.)
   - `surface_form()` public API — same signature, same behavior
2. Port the test cases from `test_linguistics_en.py` to Rust `#[test]`
3. Evaluate the `english` crate — use it if it covers your cases,
   fall back to manual port where it doesn't

**Test gate:** All 47 linguistics tests pass as Rust `#[test]` functions.

**Rust concepts introduced:**
- `HashMap` and `phf` (compile-time hash maps)
- String slicing (`&str`, `.ends_with()`, `.chars()`)
- Exhaustive pattern matching
- Test organization (`#[cfg(test)]` modules)
- `assert_eq!` with custom messages
- Documentation tests (`///` doc comments with examples)

---

### Phase 5: TUI (async, event loops, state machines)

**You will learn:** async/await, `tokio`, event-driven architecture,
`enum` as state machine, mutable state management.

**Do:**
1. Port `state.py` to `tui/state.rs`:
   - Actions as an enum (not separate structs — Rust enums are sum types)
   - `AppState` struct with view-specific sub-states
   - `reduce(state: &mut AppState, action: Action)` — same logic

```rust
enum Action {
    GotoOutline,
    GotoEntities,
    OutlineSelect { kind: String, id: String },
    OutlinePush(PathElement),
    OutlinePop,
    StartEdit { target: EditTarget, text: String, return_to: View },
    ExitEditor,
    // ...
}
```

2. Port `queries.rs` and `actions.rs` (DB reads and writes)
3. Build the ratatui app loop:
   - `crossterm` event polling in a loop
   - Render functions per view (outline, entities, editor, etc.)
   - Key bindings mapped to actions
4. Port the 14 TUI state tests

**Test gate:** TUI state tests pass. App launches, navigates, edits.

**Rust concepts introduced:**
- `enum` variants with data (Rust's killer feature)
- `&mut self` (interior mutability patterns)
- `crossterm` event polling (non-async) or `tokio::select!` (async)
- Rendering: `ratatui::Frame`, `Layout`, `Block`, `List`, `Paragraph`
- The builder pattern (ratatui widgets use it extensively)

---

### Phase 6: Desktop backend (async, axum, Tauri integration)

**You will learn:** async HTTP servers, Tauri command system,
shared state with `Arc<Mutex<>>`, the `tower` middleware stack.

**Do:**
1. Port `server.py` routes to axum handlers in `desktop/mod.rs`:

```rust
async fn get_documents(
    State(db): State<Arc<Mutex<Connection>>>,
) -> Json<Vec<DocumentResponse>> {
    // same query, same JSON shape
}
```

2. Wire axum into the Tauri app:
   - Spawn axum on `localhost:PORT` in a `tokio::spawn` task
   - Pass the port to the frontend JS via Tauri's IPC
   - Frontend `api.js` works unchanged (same HTTP calls)
3. Alternatively, use Tauri commands instead of HTTP:
   - `#[tauri::command]` functions called from JS
   - Skip HTTP entirely for desktop (cleaner, faster)
   - Keep axum as an option for headless/server mode

**Test gate:** Playwright tests pass against the Rust-backed desktop app.
The frontend JS doesn't know the backend changed.

**Rust concepts introduced:**
- `async fn`, `.await`, `tokio::spawn`
- `Arc<Mutex<T>>` for shared state across handlers
- axum extractors (`State`, `Path`, `Json`)
- `#[tauri::command]` for IPC
- Feature flags (`#[cfg(feature = "desktop")]`)

---

### Phase 7: Polish and ship

**Do:**
1. Single binary for CLI + TUI: `cargo build --release`
2. Tauri bundling: `cargo tauri build` produces `.app` / `.dmg`
3. Cross-compile for Linux/Windows (via `cross` or GitHub Actions)
4. Remove Python sidecar, embedded PG, PyInstaller — none needed
5. Update README, DEVELOPMENT.md

**Final test gate:** All 171 tests pass (108 CLI + 14 TUI + 47 linguistics
+ 63 Playwright, ported or reused). Single binary runs on a clean machine
with no dependencies.

---

## Schema migration: PG to libSQL

```sql
-- PG:  id UUID PRIMARY KEY DEFAULT gen_random_uuid()
-- SQL:  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' ||
--        hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) ||
--        '-' || substr('89ab', abs(random()) % 4 + 1, 1) ||
--        substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))))
-- Or: generate UUIDs in Rust and pass them explicitly (simpler).

-- PG:  properties JSONB
-- SQL:  properties TEXT  -- store JSON, parse in Rust via serde

-- PG:  created_at TIMESTAMPTZ DEFAULT NOW()
-- SQL:  created_at TEXT DEFAULT (datetime('now'))

-- PG:  SERIAL
-- SQL:  INTEGER PRIMARY KEY AUTOINCREMENT

-- Everything else maps 1:1.
```

**Recommendation:** Generate UUIDs in Rust (`uuid::Uuid::new_v4()`) and
pass them as TEXT. Don't rely on SQLite to generate them — it's simpler
and matches the current Python approach.

---

## Migration path (run both in parallel)

You don't have to big-bang this. Each phase produces a working binary
that handles a subset of commands.

1. Build Rust binary alongside Python codebase (separate repo or
   `littera-rs/` subdirectory)
2. CLI tests have a `LITTERA_BIN` env var — point it at Rust binary
3. As each phase passes its tests, that functionality is validated
4. When all CLI tests pass against Rust, it's ready
5. Desktop: swap sidecar from Python to Rust (or merge into Tauri)
6. Retire Python codebase

The Python version keeps working until the Rust version is complete.
No flag day required.

---

## Time estimate

Not providing one. Each phase is self-contained. Work through them
at learning pace. The test gates tell you when each phase is done.

---

## Open questions

- **libsql vs rusqlite?** libsql adds optional Turso sync but is slower
  for local-only use. Start with libsql per plan; switch to rusqlite if
  performance matters (it probably won't at Littera's scale).
- **Tauri commands vs axum?** For desktop, Tauri commands are cleaner
  (no HTTP overhead). But axum allows running headless. Could support both
  behind a feature flag.
- **Polish morphology?** No Rust crate for Polish. Will need manual port.
  Scope it as a separate phase after the core rewrite.
