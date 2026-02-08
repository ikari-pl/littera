# Development Guide

This document covers everything needed to build, run, and test Littera from source.

---

## Prerequisites

**Python (CLI + TUI)**

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) package manager

**Desktop app (optional)**

- Node.js 18+ and npm (for frontend bundling)
- Rust toolchain via [rustup](https://rustup.rs/) (for Tauri)
- Tauri CLI v2: `cargo install tauri-cli --version "^2"`

**macOS only**: The embedded PostgreSQL binaries are currently macOS-only (arm64 and x86_64). Linux and Windows are not yet supported.

---

## Quick Start

Clone and set up the Python environment:

```
git clone <repo-url> littera
cd littera
uv venv
uv pip install -e .
```

Initialize a work directory (creates `.littera/`, downloads PG binaries on first run):

```
littera init my-novel
cd my-novel
```

Run CLI commands:

```
littera doc add "Chapter One"
littera section add 1 "Opening"
littera block add 1 "It was a dark and stormy night." --lang en
littera doc list
```

Launch the TUI:

```
littera tui
```

The CLI is also accessible via module invocation:

```
python -m littera doc list
```

---

## Database

Littera uses an embedded PostgreSQL instance. No external database server is needed.

### How it works

1. On first `littera init`, the [Zonky](https://github.com/zonkyio/embedded-postgres-binaries) PostgreSQL 18.1.0 binary is downloaded from Maven Central and cached globally at:

   ```
   ~/.cache/littera/embedded-postgres/18.1.0/<os>-<arch>/pg/
   ```

2. The cached binary is symlinked into each work at `.littera/pg/`.

3. Each work gets its own PG data directory at `.littera/pgdata/` and a randomly assigned port (stored in `.littera/config.yml`).

4. PostgreSQL starts automatically when a command needs the database and stops after a configurable lease period (default 30 seconds for CLI, immediate for tests).

### Data location

All data lives under the work directory:

```
my-novel/
  .littera/
    config.yml          # Work config (PG port, work ID)
    pg -> ~/.cache/...  # Symlink to cached PG binaries
    pgdata/             # PostgreSQL data directory
```

### Schema

The canonical schema is in `db/schema.sql` (9 tables). Migrations are applied automatically via `littera.db.migrate` on every connection.

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `LITTERA_PG_LEASE_SECONDS` | How long PG stays up after a CLI command | `30` (0 in tests) |

---

## Running Tests

Tests use real embedded PostgreSQL -- no mocks for core behavior.

### Python tests (CLI + TUI)

```
uv pip install pytest
pytest tests/
```

Individual test files:

```
pytest tests/test_invariants.py      # Core model invariants
pytest tests/test_cli_commands.py    # CLI command coverage
pytest tests/test_entities.py        # Entity lifecycle
pytest tests/test_linguistics.py     # Linguistics layer
pytest tests/tui/                    # TUI view tests
```

Each test initializes a fresh work directory in a temp folder, starts its own PG instance, and tears it down afterward. Tests run with `LITTERA_PG_LEASE_SECONDS=0` automatically (detected via `PYTEST_CURRENT_TEST`).

### Desktop tests (Playwright)

The desktop frontend has a Playwright test suite that runs against a static file server (no Tauri shell required):

```
cd desktop
npm install
npx playwright install chromium
npm run build
npx playwright test --config tests/playwright.config.js
```

The Playwright config auto-starts a dev server on port 5199 via `tests/serve.js`.

---

## Desktop App

The desktop app is a Tauri v2 shell wrapping a ProseMirror-based editor. The Tauri process spawns a Python sidecar (`littera.desktop.server`) that starts embedded PG and serves a JSON API over HTTP.

### Architecture

```
Tauri (Rust)  -->  Python sidecar (HTTP API)  -->  Embedded PostgreSQL
     |
     v
  WebView (ProseMirror editor, vanilla JS)
```

### Development mode

1. Build the frontend bundle:

   ```
   cd desktop
   npm install
   npm run build
   ```

   For live rebuilds during development:

   ```
   npm run watch
   ```

2. Run the Tauri app in dev mode (from the `desktop/` directory):

   ```
   cd desktop
   cargo tauri dev
   ```

   This compiles the Rust shell, spawns it, and opens the window. The app will present a work picker on startup -- select or create a Littera work directory.

   To auto-open devtools on startup:

   ```
   LITTERA_DEVTOOLS=1 cargo tauri dev
   ```

### Production build

```
cd desktop
npm run build
cargo tauri build
```

The built application bundle appears in `desktop/src-tauri/target/release/bundle/`.

### Frontend structure

```
desktop/
  src/                    # Frontend served to WebView
    index.html            # Entry point
    main.js               # App bootstrap, Tauri IPC
    state.js              # Client-side state management
    render.js             # DOM rendering
    api.js                # HTTP client for sidecar API
    style.css             # Styles
    editor/               # ProseMirror editor modules
      index.js            # Editor entry point (bundled by esbuild)
      schema.js           # ProseMirror schema
      markdown.js         # Markdown serialization
      mention-popup.js    # Entity mention UI
      ...
    editor.bundle.js      # Built output (generated by build.js)
  src-tauri/              # Tauri/Rust shell
    Cargo.toml
    tauri.conf.json       # Tauri config (window size, CSP, etc.)
    src/main.rs           # Sidecar management, IPC commands, work picker
  tests/                  # Playwright specs
  build.js                # esbuild bundler script
```

---

## Building for Distribution

### macOS DMG

A convenience script handles the full release build:

```
cd desktop
./build-dmg.sh
```

The DMG will be at `desktop/src-tauri/target/release/bundle/dmg/`.

**Prerequisites:**
- `cargo install tauri-cli` (Tauri CLI)
- Icons in `desktop/src-tauri/icons/` (generate with `cargo tauri icon source.png`)
- Python venv at project root with `littera` installed

**Note:** The current build uses ad-hoc signing (`signingIdentity: null`). This works for local development and testing but macOS Gatekeeper will warn on first launch. For distribution outside the Mac App Store, you will need:
1. An Apple Developer ID certificate
2. Set `signingIdentity` in `tauri.conf.json`
3. Run notarization via `xcrun notarytool`

---

## Project Structure

```
littera/
  src/littera/
    cli/                  # Typer CLI (kubectl-style subcommands)
      app.py              # Entry point, command registration
      init.py             # `littera init` command
      doc.py, section.py, block.py, entity.py, mention.py, ...
    tui/                  # Textual TUI
      app.py              # LitteraApp
      state.py            # Redux-like state (reducer + actions)
    db/                   # Database layer
      bootstrap.py        # PG cluster init/start/stop mechanics
      embedded_pg.py      # Zonky binary download and cache
      workdb.py           # Work DB lifecycle (context manager)
      migrate.py          # Schema migration
    desktop/              # Desktop sidecar
      server.py           # HTTP API for Tauri frontend
    linguistics/          # Language processing layer
    __main__.py           # `python -m littera` entry
  db/
    schema.sql            # Canonical database schema
  desktop/                # Tauri desktop app (see above)
  tests/                  # pytest test suite
  docs/                   # Architecture and design docs
  pyproject.toml          # Python project config
  MANIFESTO.md            # Project philosophy
  INVARIANTS.md           # Structural invariants
  CLAUDE.md               # Agent guide
```

---

## Common Issues

### First run is slow

The first `littera init` downloads ~25 MB of PostgreSQL binaries from Maven Central. Subsequent inits reuse the cached binaries at `~/.cache/littera/embedded-postgres/`.

### Port conflicts

Each work gets a random port assigned at init time (stored in `.littera/config.yml`). If the port is taken, PG will fail to start. Fix by editing `config.yml` to change the port, or re-initialize.

### Stale PG process

If Littera crashes without cleanly stopping PG, a stale `postmaster.pid` file may prevent restart. The bootstrap layer handles stale PIDs automatically, but if issues persist:

```
# Find and remove the stale PID file
rm my-novel/.littera/pgdata/postmaster.pid
```

Or use the maintenance command:

```
littera mntn-db-reinit
```

### WAL corruption

If PG was killed uncleanly and cannot start (WAL corruption), the CLI detects this and offers recovery options via `pg_resetwal` or full cluster reinitialization. Use:

```
littera mntn-db-reset-wal
littera mntn-db-reinit      # nuclear option: deletes pgdata, re-inits
```

### macOS Gatekeeper

On first run, macOS may block the downloaded PG binaries. If you see permission errors from `initdb` or `postgres`, allow execution in System Settings > Privacy & Security, or run:

```
xattr -rd com.apple.quarantine ~/.cache/littera/embedded-postgres/
```

### Desktop app: sidecar not starting

The Tauri shell looks for Python in this order:

1. `<project-root>/.venv/bin/python`
2. `$VIRTUAL_ENV/bin/python`
3. `python3` on `$PATH`

Make sure `littera` is installed in the Python environment the desktop app will find. If using `uv venv` at the project root, the `.venv` will be picked up automatically.
