"""Smoke tests for the public package."""

import atlas_agents


def test_package_can_be_imported() -> None:
    """The installed package exposes a non-empty string version."""
    assert isinstance(atlas_agents.__version__, str)
    assert atlas_agents.__version__
