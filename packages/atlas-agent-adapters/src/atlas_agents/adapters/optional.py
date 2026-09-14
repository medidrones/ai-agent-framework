"""Optional adapter dependency errors."""


class MissingAdapterDependencyError(ImportError):
    """Report a missing transport extra without installing it implicitly."""
