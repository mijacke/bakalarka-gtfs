"""
config.py — Configuration for the GTFS agent.

Loads settings from a .env file or uses default values.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# URL MCP servera (GTFS tools)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8808/sse")

# OpenAI model pre agenta
AGENT_MODEL = os.getenv("GTFS_AGENT_MODEL", "gpt-5-mini")

# Maximalny pocet internych turnov agenta (LLM/tool iteracii na 1 odpoved)
AGENT_MAX_TURNS = int(os.getenv("GTFS_AGENT_MAX_TURNS", "20"))

# Port pre API server
API_PORT = int(os.getenv("GTFS_API_PORT", "8000"))

# API kľúč (ľubovoľný — slúži len na autentifikáciu z LibreChat)
API_KEY = os.getenv("GTFS_API_KEY", "gtfs-agent-key")

# Shared secret pre podpis explicitneho user potvrdenia apply kroku
CONFIRMATION_SECRET = os.getenv("GTFS_CONFIRMATION_SECRET", "change-me-in-env")

# Zobrazit timing footer pod odpovedou (pod ciarou) pre potreby evaluacie
SHOW_TIMING_FOOTER = os.getenv("GTFS_SHOW_TIMING_FOOTER", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Zapnut request trace logy (prepojenie s LibreChat headers)
ENABLE_TRACE_LOGS = os.getenv("GTFS_ENABLE_TRACE_LOGS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Zobrazit trace header (priebeh agenta) nad odpovedou
SHOW_TRACE_HEADER = os.getenv("GTFS_SHOW_TRACE_HEADER", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
