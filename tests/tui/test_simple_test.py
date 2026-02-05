def test_simple_import():
    """Test that imports work."""

    try:
        from littera.tui.state import AppState

        return True
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        return False


if __name__ == "__main__":
    test_simple_import()

    print("Testing complete")
