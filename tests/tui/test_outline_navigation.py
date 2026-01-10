"""
Test for specific navigation UX requirements from phase1b-tui.md.

This test verifies navigation state transitions work correctly.
"""

import pytest
from littera.tui.state import AppState, PathElement, OutlineSelect, OutlinePush, OutlinePop


def test_outline_navigation_state_transitions():
    """Navigation state transitions should work correctly."""
    state = AppState()

    # Initially at documents level
    assert state.nav_level == "documents"
    assert len(state.path) == 0

    # Select a document
    state.dispatch(OutlineSelect(kind="document", item_id="doc-1"))
    assert state.entity_selection.kind == "document"
    assert state.entity_selection.id == "doc-1"

    # Drill down into document
    state.dispatch(OutlinePush(PathElement(kind="document", id="doc-1", title="Test Doc")))
    assert state.nav_level == "sections"
    assert len(state.path) == 1
    assert state.path[0].kind == "document"

    # Selection should be cleared after push
    assert state.entity_selection.id is None

    # Select a section
    state.dispatch(OutlineSelect(kind="section", item_id="sec-1"))
    assert state.entity_selection.kind == "section"

    # Drill down into section
    state.dispatch(OutlinePush(PathElement(kind="section", id="sec-1", title="Test Section")))
    assert state.nav_level == "blocks"
    assert len(state.path) == 2

    # Go back up
    state.dispatch(OutlinePop())
    assert state.nav_level == "sections"
    assert len(state.path) == 1

    # Go back to documents
    state.dispatch(OutlinePop())
    assert state.nav_level == "documents"
    assert len(state.path) == 0


def test_current_document_and_section_properties():
    """current_document and current_section properties should track path."""
    state = AppState()

    # No current document or section at start
    assert state.current_document is None
    assert state.current_section is None

    # Push a document
    state.dispatch(OutlinePush(PathElement(kind="document", id="doc-1", title="Doc 1")))
    assert state.current_document is not None
    assert state.current_document.id == "doc-1"
    assert state.current_section is None

    # Push a section
    state.dispatch(OutlinePush(PathElement(kind="section", id="sec-1", title="Sec 1")))
    assert state.current_document.id == "doc-1"
    assert state.current_section is not None
    assert state.current_section.id == "sec-1"

    # Pop section
    state.dispatch(OutlinePop())
    assert state.current_document.id == "doc-1"
    assert state.current_section is None
