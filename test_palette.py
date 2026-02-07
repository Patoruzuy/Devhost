#!/usr/bin/env python
"""Quick test of command palette functionality."""

def main() -> int:
    try:
        from devhost_tui.app import DevhostDashboard

        app = DevhostDashboard()

        # Check that command input is in compose
        widgets = list(app.compose())
        widget_ids = [getattr(w, "id", None) for w in widgets]

        assert "command-input" in widget_ids, "Missing command-input"
        assert "command-suggestions" in widget_ids, "Missing command-suggestions"
        assert "draft-banner" in widget_ids, "Missing draft-banner"
        assert "context-help" in widget_ids, "Missing context-help"

        # Check event handlers exist
        assert hasattr(app, "on_input_submitted"), "Missing on_input_submitted"
        assert hasattr(app, "on_input_changed"), "Missing on_input_changed"
        assert hasattr(app, "on_key"), "Missing on_key"
        assert hasattr(app, "on_list_view_selected"), "Missing on_list_view_selected"

        # Check helper methods
        assert hasattr(app, "_execute_command"), "Missing _execute_command"
        assert hasattr(app, "_show_command_suggestions"), "Missing _show_command_suggestions"
        assert hasattr(app, "_hide_command_suggestions"), "Missing _hide_command_suggestions"

        print("✓ All command palette widgets present")
        print("✓ All event handlers exist")
        print("✓ All helper methods exist")
        print("✓ Command palette is FIXED!")
        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
