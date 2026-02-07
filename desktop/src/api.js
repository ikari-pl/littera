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
