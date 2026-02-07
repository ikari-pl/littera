/**
 * mention-view.js — ProseMirror NodeView for entity mentions.
 *
 * Renders {@Label|entity:uuid} as a styled read-only pill.
 * The pill is contenteditable="false" so ProseMirror treats it
 * as an atom — selectable and deletable, but not editable.
 */

export class MentionView {
  constructor(node) {
    this.dom = document.createElement("span");
    this.dom.className = "mention-pill";
    this.dom.contentEditable = "false";
    this.dom.setAttribute("data-entity-id", node.attrs.id);
    this.dom.textContent = node.attrs.label;
  }

  // Atoms have no editable content
  stopEvent() {
    return true;
  }

  // Prevent ProseMirror from trying to update inner content
  ignoreMutation() {
    return true;
  }
}
