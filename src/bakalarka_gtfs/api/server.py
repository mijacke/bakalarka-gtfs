"""
server.py — OpenAI-compatible API server for the GTFS agent.

This server creates the /v1/chat/completions endpoint, which is
compatible with the OpenAI API format. LibreChat (or any other
application) can use it as a custom endpoint.

Startup:
    via docker-compose service `gtfs-api`

LibreChat connects to http://gtfs-api:8000/v1 (in the Docker network).
"""

from __future__ import annotations

from fastapi import FastAPI

from ..core.config import API_PORT, SHOW_TRACE_HEADER
from .chat import router as chat_router

# ---------------------------------------------------------------------------
# FastAPI aplikácia
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GTFS Agent API",
    description="OpenAI-kompatibilný endpoint pre GTFS agenta",
    version="0.3.0",
)

app.include_router(chat_router)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "gtfs-agent"}


# ---------------------------------------------------------------------------
# Spustenie servera
# ---------------------------------------------------------------------------


def main():
    """Spustí API server."""
    import uvicorn

    print("GTFS Agent API server")
    print(f"   Endpoint: http://localhost:{API_PORT}/v1/chat/completions")
    print(f"   Modely:   http://localhost:{API_PORT}/v1/models")
    print(f"   Health:   http://localhost:{API_PORT}/health")
    print(f"   Trace header: {'ON' if SHOW_TRACE_HEADER else 'OFF'}")
    print()
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


if __name__ == "__main__":
    main()
