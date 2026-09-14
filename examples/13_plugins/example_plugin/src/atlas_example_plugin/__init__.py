"""Public factory for the local example plugin."""

from atlas_example_plugin.plugin import ExampleToolPlugin


def create_plugin() -> ExampleToolPlugin:
    """Create an inactive plugin instance for the Atlas loader."""
    return ExampleToolPlugin()


__all__ = ["ExampleToolPlugin", "create_plugin"]
