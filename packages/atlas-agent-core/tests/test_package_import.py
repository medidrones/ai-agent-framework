"""Smoke tests for the public package."""

import atlas_agents


def test_package_exposes_version() -> None:
    """The installed package exposes its initial public version."""
    assert atlas_agents.__version__ == "0.1.0"
