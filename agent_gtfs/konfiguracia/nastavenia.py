"""
nastavenia.py — Nastavenia GTFS agenta.

Načíta konfiguráciu z .env súboru alebo použije predvolené hodnoty.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# URL MCP servera (GTFS tools)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8808/sse")

# OpenAI model pre agenta
AGENT_MODEL = os.getenv("GTFS_AGENT_MODEL", "gpt-5-mini")

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
