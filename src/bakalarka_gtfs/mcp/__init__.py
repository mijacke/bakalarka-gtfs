"""
mcp — MCP server, GTFS database, patching, and visualization.

Submodules:
    server         — FastMCP server with 8 GTFS tools (SSE transport)
    database       — SQLite singleton: import, query, export GTFS data
    patching/      — Patch operations (update/delete/insert) and validation
    visualization/ — Leaflet.js interactive map generator

Entry point::

    python -m bakalarka_gtfs.mcp.server
"""

from .database import ensure_loaded, export_to_gtfs, get_current_db, run_query

__all__ = ["ensure_loaded", "export_to_gtfs", "get_current_db", "run_query"]
