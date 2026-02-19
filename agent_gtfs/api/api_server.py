"""
api_server.py — OpenAI-kompatibilny API server pre GTFS agenta.

Tento server vytvára endpoint /v1/chat/completions, ktorý je
kompatibilný s OpenAI API formátom. Vďaka tomu ho môže LibreChat
(alebo akákoľvek iná aplikácia) použiť ako custom endpoint.

Spustenie:
    cez docker-compose service `gtfs-api`

LibreChat sa pripaja na http://gtfs-api:8000/v1 (v Docker sieti).
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
import uuid
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from ..agent.agent_s_mcp import GTFSAgent
from ..konfiguracia.nastavenia import API_PORT, API_KEY

# ---------------------------------------------------------------------------
# FastAPI aplikácia
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GTFS Agent API",
    description="OpenAI-kompatibilný endpoint pre GTFS agenta",
    version="0.2.0",
)


# ---------------------------------------------------------------------------
# Modely pre request/response
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: str
    content: str | None = None


class ChatRequest(BaseModel):
    model: str = "gtfs-agent"
    messages: list[Message]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


def _extract_bearer_token(auth_header: str | None) -> str | None:
    """Vytiahne token z Authorization: Bearer <token>."""
    if not auth_header:
        return None
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _is_authorized(request: Request) -> bool:
    """
    Overi API kluc v hlavicke.
    Primarne: Authorization: Bearer <GTFS_API_KEY>
    Fallback: x-api-key: <GTFS_API_KEY>
    """
    bearer = _extract_bearer_token(request.headers.get("authorization"))
    if bearer and hmac.compare_digest(bearer, API_KEY):
        return True

    x_api_key = request.headers.get("x-api-key")
    if x_api_key and hmac.compare_digest(x_api_key, API_KEY):
        return True

    return False


def _unauthorized_response() -> JSONResponse:
    """OpenAI-like auth error response."""
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "message": "Invalid API key.",
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key",
            }
        },
    )


# ---------------------------------------------------------------------------
# Endpointy
# ---------------------------------------------------------------------------


@app.get("/v1/models")
async def list_models(request: Request):
    """Vráti zoznam dostupných modelov (len gtfs-agent)."""
    if not _is_authorized(request):
        return _unauthorized_response()

    return {
        "object": "list",
        "data": [
            {
                "id": "gtfs-agent",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "gtfs-agent",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(chat_request: ChatRequest, request: Request):
    """
    OpenAI-kompatibilný chat completions endpoint.

    - Prijme správy od LibreChat
    - Odfiltruje system správy (agent má vlastné inštrukcie)
    - Spustí GTFSAgent
    - Vráti odpoveď v OpenAI formáte (streaming alebo naraz)
    """
    if not _is_authorized(request):
        return _unauthorized_response()

    # Odfiltruj system spravy — agent ma vlastne instrukcie v systemove_instrukcie.py
    spravy = [
        {"role": m.role, "content": m.content or ""}
        for m in chat_request.messages
        if m.role != "system"
    ]

    if not spravy:
        spravy = [{"role": "user", "content": "Ahoj"}]

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    try:
        agent = GTFSAgent()
        odpoved = await agent.run(spravy)
    except Exception as e:
        odpoved = f"❌ Chyba agenta: {e}\n\n```\n{traceback.format_exc()}\n```"

    if chat_request.stream:
        return StreamingResponse(
            _stream_odpoved(odpoved, completion_id, created),
            media_type="text/event-stream",
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": "gtfs-agent",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": odpoved},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


async def _stream_odpoved(
    text: str, completion_id: str, created: int
):
    """Streamuje odpoveď po slovách v OpenAI chunk formáte."""
    slova = text.split(" ")
    for i, slovo in enumerate(slova):
        obsah = slovo if i == 0 else " " + slovo
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": "gtfs-agent",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": obsah},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)

    # Finálny chunk
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": "gtfs-agent",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


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

    print(f"🚀 GTFS Agent API server")
    print(f"   Endpoint: http://localhost:{API_PORT}/v1/chat/completions")
    print(f"   Modely:   http://localhost:{API_PORT}/v1/models")
    print(f"   Health:   http://localhost:{API_PORT}/health")
    print()
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


if __name__ == "__main__":
    main()
