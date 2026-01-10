"""
Test to verify state.py fixes.
"""

from dataclasses import fields
from littera.tui.state import AppState, EditSession, EditTarget


def test_state_py_has_return_to_field():
    """Verify state.py has return_to field in EditSession."""
    # Check that EditSession has return_to as a dataclass field
    field_names = {f.name for f in fields(EditSession)}
    assert "return_to" in field_names

    # Verify we can create an instance with return_to
    session = EditSession(
        target=EditTarget(kind="entity_note", id="ent1"),
        original_text="original text",
        current_text="edited note",
        return_to="outline",
    )
    assert session.return_to == "outline"


def test_app_state_has_dispatch():
    """Verify AppState has dispatch method."""
    state = AppState()
    assert hasattr(state, "dispatch")
    assert callable(state.dispatch)


def test_app_state_computed_properties():
    """Verify AppState has computed properties."""
    state = AppState()
    # These should not raise AttributeError
    _ = state.edit_session
    _ = state.entity_selection
    _ = state.nav_level
    _ = state.path
    _ = state.current_document
    _ = state.current_section


if __name__ == "__main__":
    test_state_py_has_return_to_field()
    test_app_state_has_dispatch()
    test_app_state_computed_properties()