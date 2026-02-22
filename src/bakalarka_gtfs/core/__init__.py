"""
core — Shared configuration for all components.

Re-exports the most common settings so callers can write::

    from bakalarka_gtfs.core import AGENT_MODEL, API_PORT
"""

from .config import (
    AGENT_MAX_TURNS,
    AGENT_MODEL,
    API_KEY,
    API_PORT,
    CONFIRMATION_SECRET,
    ENABLE_TRACE_LOGS,
    MCP_SERVER_URL,
    SHOW_TIMING_FOOTER,
    SHOW_TRACE_HEADER,
)

__all__ = [
    "AGENT_MAX_TURNS",
    "AGENT_MODEL",
    "API_KEY",
    "API_PORT",
    "CONFIRMATION_SECRET",
    "ENABLE_TRACE_LOGS",
    "MCP_SERVER_URL",
    "SHOW_TIMING_FOOTER",
    "SHOW_TRACE_HEADER",
]
