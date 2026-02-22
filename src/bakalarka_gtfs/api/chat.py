"""
chat.py — Endpoints for chat completions and models.
"""

import json
import logging
import re
import time
import uuid

from agents.exceptions import MaxTurnsExceeded
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..agent.agent import AgentProfiling, AgentTrace, GTFSAgent
from ..core.config import AGENT_MAX_TURNS, ENABLE_TRACE_LOGS, SHOW_TIMING_FOOTER, SHOW_TRACE_HEADER
from .auth import is_authorized, sign_confirmation_message, unauthorized_response
from .formatting import format_timing_footer, format_trace_header
from .schemas import ChatRequest

router = APIRouter()

logger = logging.getLogger(__name__)
if ENABLE_TRACE_LOGS:
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logger = logging.getLogger("uvicorn.error")

AGENT = GTFSAgent(max_turns=AGENT_MAX_TURNS)
_CONFIRM_MESSAGE_PATTERN = re.compile(r"^/confirm\s+[a-fA-F0-9]{64}$")


def _last_user_message(messages: list[dict]) -> str:
    """Vrati poslednu user spravu (alebo prazdny string)."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "") or ""
    return ""


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
        headers["x-gtfs-thinking-ms"] = str(round(profiling.thinking_seconds * 1000))
        headers["x-gtfs-model-ms"] = str(round(profiling.model_seconds * 1000))
        headers["x-gtfs-db-mcp-ms"] = str(round(profiling.db_mcp_seconds * 1000))
        headers["x-gtfs-python-ms"] = str(round(profiling.python_overhead_seconds * 1000))
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


@router.get("/v1/models")
async def list_models(request: Request):
    """Vráti zoznam dostupných modelov (len gtfs-agent)."""
    if not is_authorized(request):
        return unauthorized_response()

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


@router.post("/v1/chat/completions")
async def chat_completions(chat_request: ChatRequest, request: Request):
    """
    OpenAI-kompatibilný chat completions endpoint.

    - Prijme správy od LibreChat
    - Odfiltruje system správy (agent má vlastné inštrukcie)
    - Spustí GTFSAgent
    - Vráti odpoveď v OpenAI formáte (streaming alebo naraz)
    """
    if not is_authorized(request):
        return unauthorized_response()

    # Extrahuj system spravy od klienta (LibreChat sem vklada instrukcie pre Artifacts)
    extra_instructions = "\n\n".join(
        m.content.strip() for m in chat_request.messages if m.role == "system" and m.content
    )

    # Odfiltruj system spravy — agent ma vlastne instrukcie v prompts.py plus tie co sme prave extrahovali
    spravy = [{"role": m.role, "content": m.content or ""} for m in chat_request.messages if m.role != "system"]

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
    agent_trace = AgentTrace()

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
        confirmation_signature = sign_confirmation_message(last_user_message)
        odpoved, profiling, agent_trace = await AGENT.run_with_profiling(
            vstup=spravy,
            extra_instructions=extra_instructions,
            confirmation_message=last_user_message,
            confirmation_signature=confirmation_signature,
            collect_trace=SHOW_TRACE_HEADER,
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
        odpoved = f"Interna chyba agenta.\nID chyby: {error_id}\nSkus poziadavku zopakovat."

    if chat_request.stream:
        _trace_log(
            "GTFS chat thinking_done trace_id=%s thinking_ms=%d model_ms=%d db_mcp_ms=%d python_ms=%d",
            trace_id,
            round(profiling.thinking_seconds * 1000),
            round(profiling.model_seconds * 1000),
            round(profiling.db_mcp_seconds * 1000),
            round(profiling.python_overhead_seconds * 1000),
        )
        return StreamingResponse(
            _stream_odpoved(
                text=odpoved,
                completion_id=completion_id,
                created=created,
                profiling=profiling,
                trace_id=trace_id,
                agent_trace=agent_trace,
            ),
            media_type="text/event-stream",
            headers=_build_response_headers(
                trace_id=trace_id,
                profiling=profiling,
            ),
        )

    # Non-streaming: zostav finalnu odpoved
    final_content = ""

    if SHOW_TRACE_HEADER:
        final_content += format_trace_header(agent_trace)

    final_content += odpoved

    if SHOW_TIMING_FOOTER:
        final_content += format_timing_footer(
            profiling=profiling,
            prompt_tokens=profiling.prompt_tokens,
            completion_tokens=profiling.completion_tokens,
        )

    _trace_log(
        "GTFS chat done trace_id=%s thinking_ms=%d model_ms=%d db_mcp_ms=%d python_ms=%d stream=%s",
        trace_id,
        round(profiling.thinking_seconds * 1000),
        round(profiling.model_seconds * 1000),
        round(profiling.db_mcp_seconds * 1000),
        round(profiling.python_overhead_seconds * 1000),
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
                "message": {"role": "assistant", "content": final_content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": profiling.prompt_tokens,
            "completion_tokens": profiling.completion_tokens,
            "total_tokens": profiling.total_tokens,
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
    agent_trace: AgentTrace | None = None,
):
    """Streamuje odpoveď po slovách v OpenAI chunk formáte."""

    def _make_chunk(content: str, finish_reason=None):
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": "gtfs-agent",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content} if content else {},
                    "finish_reason": finish_reason,
                }
            ],
        }

    # -- Trace header (ak je zapnuty) --
    if SHOW_TRACE_HEADER and agent_trace:
        trace_header = format_trace_header(agent_trace)
        if trace_header:
            yield f"data: {json.dumps(_make_chunk(trace_header))}\n\n"

    # -- Hlavna odpoved --
    slova = text.split(" ")
    for i, slovo in enumerate(slova):
        obsah = slovo if i == 0 else " " + slovo
        yield f"data: {json.dumps(_make_chunk(obsah))}\n\n"

    # -- Timing footer (ak je zapnuty) --
    if SHOW_TIMING_FOOTER:
        footer_text = format_timing_footer(
            profiling=profiling,
            prompt_tokens=profiling.prompt_tokens,
            completion_tokens=profiling.completion_tokens,
        )
        yield f"data: {json.dumps(_make_chunk(footer_text))}\n\n"

    _trace_log(
        "GTFS chat stream_done trace_id=%s thinking_ms=%d model_ms=%d db_mcp_ms=%d python_ms=%d",
        trace_id,
        round(profiling.thinking_seconds * 1000),
        round(profiling.model_seconds * 1000),
        round(profiling.db_mcp_seconds * 1000),
        round(profiling.python_overhead_seconds * 1000),
    )

    # Finálny chunk
    yield f"data: {json.dumps(_make_chunk('', finish_reason='stop'))}\n\n"
    yield "data: [DONE]\n\n"
