#!/usr/bin/env bash
# Build Littera.dmg for macOS distribution.
#
# Prerequisites:
#   - Rust toolchain (rustup)
#   - Tauri CLI: cargo install tauri-cli
#   - Python venv at project root (.venv/)
#
# Usage:
#   cd desktop && ./build-dmg.sh
#
# Output:
#   src-tauri/target/release/bundle/dmg/Littera_0.1.0_aarch64.dmg

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Building Littera desktop app..."
echo "    Project root: $PROJECT_ROOT"

# Verify Python venv exists
if [ ! -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    echo "ERROR: No Python venv found at $PROJECT_ROOT/.venv/"
    echo "Run: cd $PROJECT_ROOT && uv venv && uv pip install -e ."
    exit 1
fi

# Build the frontend bundle if build.js exists
if [ -f "$SCRIPT_DIR/build.js" ]; then
    echo "==> Building frontend bundle..."
    cd "$SCRIPT_DIR"
    npm run build
fi

# Build the Tauri app in release mode
cd "$SCRIPT_DIR"
cargo tauri build

echo ""
echo "==> Build complete!"
echo "    DMG location: src-tauri/target/release/bundle/dmg/"
ls -la src-tauri/target/release/bundle/dmg/*.dmg 2>/dev/null || echo "    (DMG may not have been generated without icons)"
