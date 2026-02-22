"""
api — OpenAI-compatible FastAPI server.

Provides ``/v1/chat/completions`` and ``/v1/models`` endpoints
so LibreChat (or any OpenAI-compatible client) can talk to the
GTFS agent.

Entry point::

    python -m bakalarka_gtfs.api.server
"""
