"""Errors for optional provider dependency boundaries."""


class MissingProviderDependencyError(ImportError):
    """Report a missing provider extra without installing it implicitly."""
