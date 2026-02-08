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

export function renameDocument(port, id, title) {
  return put(port, `/api/documents/${id}`, { title });
}

export function renameSection(port, id, title) {
  return put(port, `/api/sections/${id}`, { title });
}

export function createDocument(port, title) {
  return post(port, "/api/documents", { title });
}

export function deleteDocument(port, id) {
  return del(port, `/api/documents/${id}`);
}

export function createSection(port, documentId, title) {
  return post(port, "/api/sections", { document_id: documentId, title });
}

export function deleteSection(port, id) {
  return del(port, `/api/sections/${id}`);
}

export function createEntity(port, entityType, label) {
  return post(port, "/api/entities", { entity_type: entityType, label });
}

export function deleteEntity(port, id) {
  return del(port, `/api/entities/${id}`);
}

export function deleteMention(port, mentionId) {
  return del(port, `/api/mentions/${mentionId}`);
}

export function saveEntityNote(port, entityId, note) {
  return put(port, `/api/entities/${entityId}/note`, { note });
}

export function addEntityLabel(port, entityId, language, baseForm, aliases) {
  return post(port, `/api/entities/${entityId}/labels`, { language, base_form: baseForm, aliases });
}

export function deleteLabel(port, labelId) {
  return del(port, `/api/labels/${labelId}`);
}

export function fetchEntityProperties(port, entityId) {
  return get(port, `/api/entities/${entityId}/properties`);
}

export function setEntityProperties(port, entityId, properties) {
  return put(port, `/api/entities/${entityId}/properties`, properties);
}

export function deleteEntityProperty(port, entityId, key) {
  return del(port, `/api/entities/${entityId}/properties/${key}`);
}

// Alignments
export function fetchAlignments(port) {
  return get(port, "/api/alignments");
}

export function createAlignment(port, sourceBlockId, targetBlockId, type) {
  return post(port, "/api/alignments", {
    source_block_id: sourceBlockId,
    target_block_id: targetBlockId,
    alignment_type: type || "translation",
  });
}

export function deleteAlignment(port, alignmentId) {
  return del(port, `/api/alignments/${alignmentId}`);
}

// Reviews
export function fetchReviews(port) {
  return get(port, "/api/reviews");
}

export function createReview(port, description, opts = {}) {
  return post(port, "/api/reviews", { description, ...opts });
}

export function deleteReview(port, reviewId) {
  return del(port, `/api/reviews/${reviewId}`);
}
