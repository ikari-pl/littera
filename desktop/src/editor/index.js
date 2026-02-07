/**
 * Editor bundle entry point — re-exports the public API.
 *
 * esbuild bundles this into editor.bundle.js (ESM).
 */

export { createEditor, loadSection } from "./editor.js";
export { findDirtyBlocks } from "./dirty.js";
export { blocksToDoc, blockNodeToMarkdown } from "./markdown.js";
export { schema } from "./schema.js";
