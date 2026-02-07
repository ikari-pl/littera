/**
 * build.js — Bundle ProseMirror editor into a single ESM file.
 *
 * Usage:
 *   node build.js          # one-shot build
 *   node build.js --watch  # watch mode for development
 */

const path = require("path");
const esbuild = require("esbuild");

const watch = process.argv.includes("--watch");
const dir = __dirname;

const opts = {
  entryPoints: [path.join(dir, "src/editor/index.js")],
  bundle: true,
  format: "esm",
  outfile: path.join(dir, "src/editor.bundle.js"),
  sourcemap: true,
  target: "es2020",
  logLevel: "info",
};

if (watch) {
  esbuild.context(opts).then((ctx) => ctx.watch());
} else {
  esbuild.build(opts);
}
