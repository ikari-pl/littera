"""Smoke test: the TUI state module imports cleanly."""


def test_simple_import():
    """AppState must be importable; a broken import should fail the suite."""
    from littera.tui.state import AppState

    assert AppState is not None
