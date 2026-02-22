"""
patching — Patch operations and validation for GTFS data.

Usage::

    from bakalarka_gtfs.mcp.patching import parse_patch, validate_patch

    patch = parse_patch(json_string)
    result = validate_patch(patch)
"""

from .apply import apply_patch
from .diff import build_diff_summary
from .models import parse_patch
from .validation import validate_patch

__all__ = ["apply_patch", "build_diff_summary", "parse_patch", "validate_patch"]
