"""
patching — Patch operations and validation for GTFS data.

Modules:
    operations  — parse, diff-preview, transform (time_add), apply patches
    validation  — FK integrity, time ordering, required fields checks

Usage::

    from bakalarka_gtfs.mcp.patching import parse_patch, validate_patch

    patch = parse_patch(json_string)
    result = validate_patch(patch)
"""

from .operations import apply_patch, build_diff_summary, parse_patch
from .validation import validate_patch

__all__ = ["apply_patch", "build_diff_summary", "parse_patch", "validate_patch"]
