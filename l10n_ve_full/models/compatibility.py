# Temporary compatibility helpers to avoid hard failures caused by non-stored/searchable related fields
# These are stop-gap measures to let the server accept writes while root causes are addressed.
from odoo import fields
import warnings

_original_resolve_depends = fields.Field.resolve_depends


def _safe_resolve_depends(self, model):
    """
    Wrapper around Field.resolve_depends to catch situations where a dependency
    references a non-stored field used in a computed/related dependency and
    would otherwise emit warnings or raise errors that block operations.

    NOTE: This is a temporary mitigation. Proper fix requires making the
    dependent fields searchable/stored or simplifying the dependency.
    """
    try:
        for dep in _original_resolve_depends(self, model):
            yield dep
    except Exception as e:
        # Log a warning and return empty iterator so the caller will not break.
        warnings.warn(f"compatibility._safe_resolve_depends suppressed exception: {e}")
        return


# Apply the monkeypatch
fields.Field.resolve_depends = _safe_resolve_depends
