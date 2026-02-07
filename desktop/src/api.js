/**
 * api.js — HTTP fetch helpers wrapping sidecar endpoints.
 *
 * Every function takes a port number and returns parsed JSON.
 * Errors are thrown as plain Error objects for the caller to handle.
 */

function base(port) {
  return `http://127.0.0.1:${port}`;
}

async function get(port, path) {
  const res = await fetch(`${base(port)}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

async function put(port, path, body) {
  const res = await fetch(`${base(port)}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: PUT ${path}`);
  return res.json();
}

async function post(port, path, body) {
  const res = await fetch(`${base(port)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: POST ${path}`);
  return res.json();
}

async function del(port, path) {
  const res = await fetch(`${base(port)}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}: DELETE ${path}`);
  return res.json();
}

export function fetchDocuments(port) {
  return get(port, "/api/documents");
}

export function fetchSections(port, documentId) {
  return get(port, `/api/documents/${documentId}/sections`);
}

export function fetchBlocks(port, sectionId) {
  return get(port, `/api/sections/${sectionId}/blocks`);
}

export function fetchBlock(port, blockId) {
  return get(port, `/api/blocks/${blockId}`);
}

export function fetchEntities(port) {
  return get(port, "/api/entities");
}

export function fetchEntity(port, entityId) {
  return get(port, `/api/entities/${entityId}`);
}

export function fetchStatus(port) {
  return get(port, "/api/status");
}

export function saveBlock(port, blockId, sourceText) {
  return put(port, `/api/blocks/${blockId}`, { source_text: sourceText });
}

export function saveBlocksBatch(port, blocks) {
  return put(port, "/api/blocks/batch", { blocks });
}

export function createBlock(port, sectionId, opts = {}) {
  return post(port, "/api/blocks", { section_id: sectionId, ...opts });
}

export function deleteBlock(port, blockId) {
  return del(port, `/api/blocks/${blockId}`);
}
