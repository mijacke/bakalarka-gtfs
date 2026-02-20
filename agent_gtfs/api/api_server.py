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

import hashlib
import hmac
import json
import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from agents.exceptions import MaxTurnsExceeded

from ..agent.agent_s_mcp import GTFSAgent, AgentProfiling
from ..konfiguracia.nastavenia import (
    API_PORT,
    API_KEY,
    CONFIRMATION_SECRET,
    ENABLE_TRACE_LOGS,
    SHOW_TIMING_FOOTER,
    AGENT_MAX_TURNS,
)

# ---------------------------------------------------------------------------
# FastAPI aplikácia
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GTFS Agent API",
    description="OpenAI-kompatibilný endpoint pre GTFS agenta",
    version="0.2.0",
)
logger = logging.getLogger(__name__)
AGENT = GTFSAgent(max_turns=AGENT_MAX_TURNS)
_CONFIRM_MESSAGE_PATTERN = re.compile(r"^/confirm\s+[a-fA-F0-9]{64}$")

if ENABLE_TRACE_LOGS:
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logger = logging.getLogger("uvicorn.error")


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


def _last_user_message(messages: list[dict]) -> str:
    """Vrati poslednu user spravu (alebo prazdny string)."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "") or ""
    return ""


def _sign_confirmation_message(message: str) -> str:
    """Vytvori HMAC SHA-256 podpis potvrdenia, overitelny MCP serverom."""
    return hmac.new(
        CONFIRMATION_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _format_timing_footer(profiling: AgentProfiling) -> str:
    """
    Format casov pre nenapadny footer pod odpovedou.
    Zobrazuje sa pod ciarou, aby co najmenej rusil chat.
    """
    return (
        "\n\n---\n"
        f"_celkový čas rozmýšľania: {profiling.thinking_seconds:.2f} s_\n"
        f"_profiling: model {profiling.model_seconds:.2f} s | "
        f"db/mcp {profiling.db_mcp_seconds:.2f} s | "
        f"python {profiling.python_overhead_seconds:.2f} s_"
    )


def _extract_trace_id(request: Request, fallback: str) -> str:
    """Získa trace id z bežných hlavičiek (LibreChat / proxy), inak fallback."""
    for header in (
        "x-trace-id",
        "x-request-id",
        "x-correlation-id",
        "x-librechat-message-id",
    ):
        value = request.headers.get(header)
        if value:
            return value.strip()
    return fallback


def _build_response_headers(
    trace_id: str,
    profiling: AgentProfiling | None = None,
) -> dict[str, str]:
    """Technické hlavičky pre tracing/latenciu bez rušenia obsahu chatu."""
    headers = {"x-gtfs-trace-id": trace_id}
    if profiling is not None:
        headers["x-gtfs-thinking-ms"] = str(int(round(profiling.thinking_seconds * 1000)))
        headers["x-gtfs-model-ms"] = str(int(round(profiling.model_seconds * 1000)))
        headers["x-gtfs-db-mcp-ms"] = str(int(round(profiling.db_mcp_seconds * 1000)))
        headers["x-gtfs-python-ms"] = str(int(round(profiling.python_overhead_seconds * 1000)))
    return headers


def _trace_log(message: str, *args) -> None:
    """Log trace správy; fallback cez print pre docker logs."""
    if not ENABLE_TRACE_LOGS:
        return
    try:
        rendered = message % args if args else message
        print(rendered, flush=True)
    except Exception:
        pass


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
    trace_id = _extract_trace_id(request, fallback=completion_id)
    thinking_started_at = time.perf_counter()
    profiling = AgentProfiling(
        thinking_seconds=0.0,
        model_seconds=0.0,
        db_mcp_seconds=0.0,
        python_overhead_seconds=0.0,
        llm_calls=0,
        tool_calls=0,
    )

    _trace_log(
        "GTFS chat start trace_id=%s stream=%s model=%s messages=%d",
        trace_id,
        chat_request.stream,
        chat_request.model,
        len(spravy),
    )

    try:
        last_user_message = _last_user_message(spravy).strip()
        if _CONFIRM_MESSAGE_PATTERN.match(last_user_message):
            # V confirm mode neposielaj cely chat, aby sa agent zbytocne
            # nevracal k navrhovaniu noveho patchu.
            spravy = [{"role": "user", "content": last_user_message}]
        confirmation_signature = _sign_confirmation_message(last_user_message)
        odpoved, profiling = await AGENT.run_with_profiling(
            spravy,
            confirmation_message=last_user_message,
            confirmation_signature=confirmation_signature,
        )
    except MaxTurnsExceeded:
        thinking_seconds = time.perf_counter() - thinking_started_at
        profiling = AgentProfiling(
            thinking_seconds=thinking_seconds,
            model_seconds=0.0,
            db_mcp_seconds=0.0,
            python_overhead_seconds=thinking_seconds,
            llm_calls=0,
            tool_calls=0,
        )
        odpoved = (
            "Postup sa zastavil, pretoze agent prekrocil limit internych krokov. "
            "Skuste prosim upresnit patch filter jednoduchsie (napr. jeden route_id, "
            "presny casovy interval, bez alternativnych variantov) a zopakovat krok "
            "`propose + validate`."
        )
    except Exception:
        thinking_seconds = time.perf_counter() - thinking_started_at
        profiling = AgentProfiling(
            thinking_seconds=thinking_seconds,
            model_seconds=0.0,
            db_mcp_seconds=0.0,
            python_overhead_seconds=thinking_seconds,
            llm_calls=0,
            tool_calls=0,
        )
        error_id = uuid.uuid4().hex[:10]
        logger.exception("GTFS agent failed (error_id=%s)", error_id)
        odpoved = (
            "❌ Interna chyba agenta.\n"
            f"ID chyby: {error_id}\n"
            "Skus poziadavku zopakovat."
        )

    if chat_request.stream:
        _trace_log(
            "GTFS chat thinking_done trace_id=%s thinking_ms=%d model_ms=%d db_mcp_ms=%d python_ms=%d",
            trace_id,
            int(round(profiling.thinking_seconds * 1000)),
            int(round(profiling.model_seconds * 1000)),
            int(round(profiling.db_mcp_seconds * 1000)),
            int(round(profiling.python_overhead_seconds * 1000)),
        )
        return StreamingResponse(
            _stream_odpoved(
                text=odpoved,
                completion_id=completion_id,
                created=created,
                profiling=profiling,
                trace_id=trace_id,
            ),
            media_type="text/event-stream",
            headers=_build_response_headers(
                trace_id=trace_id,
                profiling=profiling,
            ),
        )

    if SHOW_TIMING_FOOTER:
        odpoved = odpoved + _format_timing_footer(profiling=profiling)

    _trace_log(
        "GTFS chat done trace_id=%s thinking_ms=%d model_ms=%d db_mcp_ms=%d python_ms=%d stream=%s",
        trace_id,
        int(round(profiling.thinking_seconds * 1000)),
        int(round(profiling.model_seconds * 1000)),
        int(round(profiling.db_mcp_seconds * 1000)),
        int(round(profiling.python_overhead_seconds * 1000)),
        chat_request.stream,
    )

    payload = {
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
        "gtfs_timing": {
            "total_thinking_seconds": round(profiling.thinking_seconds, 3),
            "model_seconds": round(profiling.model_seconds, 3),
            "db_mcp_seconds": round(profiling.db_mcp_seconds, 3),
            "python_overhead_seconds": round(profiling.python_overhead_seconds, 3),
            "llm_calls": profiling.llm_calls,
            "tool_calls": profiling.tool_calls,
        },
    }
    return JSONResponse(
        content=payload,
        headers=_build_response_headers(
            trace_id=trace_id,
            profiling=profiling,
        ),
    )


async def _stream_odpoved(
    text: str,
    completion_id: str,
    created: int,
    profiling: AgentProfiling,
    trace_id: str,
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

    if SHOW_TIMING_FOOTER:
        footer_text = _format_timing_footer(profiling=profiling)
        footer_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": "gtfs-agent",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": footer_text},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(footer_chunk)}\n\n"

    _trace_log(
        "GTFS chat stream_done trace_id=%s thinking_ms=%d model_ms=%d db_mcp_ms=%d python_ms=%d",
        trace_id,
        int(round(profiling.thinking_seconds * 1000)),
        int(round(profiling.model_seconds * 1000)),
        int(round(profiling.db_mcp_seconds * 1000)),
        int(round(profiling.python_overhead_seconds * 1000)),
    )

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
