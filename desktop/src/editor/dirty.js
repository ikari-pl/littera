/**
 * dirty.js — Track which blocks changed between saves.
 *
 * Uses ProseMirror's structural sharing: unchanged blocks retain
 * reference identity (oldChild === newChild). Changed or new blocks
 * have a different reference. Deleted blocks exist in savedDoc but
 * not in currentDoc.
 */

/**
 * Compare saved and current doc to find dirty blocks.
 *
 * Returns {updates: [{id, node}], creates: [{id, node}], deletes: [{id}]}
 */
export function findDirtyBlocks(savedDoc, currentDoc) {
  // Build a set of block IDs in the saved doc
  const savedIds = new Set();
  const savedByIndex = [];
  savedDoc.forEach((child) => {
    savedIds.add(child.attrs.id);
    savedByIndex.push(child);
  });

  // Build index of saved blocks by ID for reference comparison
  const savedById = new Map();
  savedDoc.forEach((child) => {
    savedById.set(child.attrs.id, child);
  });

  const updates = [];
  const creates = [];
  const currentIds = new Set();

  currentDoc.forEach((child) => {
    const id = child.attrs.id;
    currentIds.add(id);

    if (!savedIds.has(id)) {
      // New block (created via Shift+Enter)
      creates.push({ id, node: child });
    } else {
      // Existing block — check if reference changed
      const savedNode = savedById.get(id);
      if (savedNode !== child) {
        updates.push({ id, node: child });
      }
    }
  });

  // Deleted blocks: in saved but not in current
  const deletes = [];
  for (const id of savedIds) {
    if (!currentIds.has(id)) {
      deletes.push({ id });
    }
  }

  return { updates, creates, deletes };
}
