"""
agent.py — GTFSAgent class.

Connects to an MCP server via SSE and allows editing of GTFS data
through text commands. Can be called from any Python application.

Usage:
    from bakalarka_gtfs.agent import GTFSAgent

    agent = GTFSAgent()
    result = await agent.run("Koľko zastávok máme?")
    print(result)
"""

from __future__ import annotations

import json
import re
import time

from agents import Agent, Runner
from agents.mcp import MCPServerSse

from ..core.config import AGENT_MAX_TURNS, AGENT_MODEL, MCP_SERVER_URL
from .hooks import _TracingHooks
from .models import AgentProfiling, AgentTrace
from .prompts import SYSTEM_PROMPT

_CONFIRM_MESSAGE_PATTERN = re.compile(r"^/confirm\s+[a-fA-F0-9]{64}$")


class GTFSAgent:
    """
    Code-first GTFS agent — pripojí sa na MCP server a umožňuje
    editáciu GTFS dát cez textové príkazy.

    Argumenty:
        mcp_url: URL MCP servera (predvolene z .env alebo localhost:8808)
        model:   OpenAI model (predvolene z .env alebo gpt-4.1)
    """

    def __init__(
        self,
        mcp_url: str = MCP_SERVER_URL,
        model: str = AGENT_MODEL,
        max_turns: int = AGENT_MAX_TURNS,
    ):
        self.mcp_url = mcp_url
        self.model = model
        self.max_turns = max(1, int(max_turns))

    @staticmethod
    def _compose_instructions(confirmation_message: str, confirmation_signature: str) -> str:
        """Doplni runtime kontext pre server-side potvrdenie apply kroku."""
        runtime_context = (
            "\n\n## Runtime confirmation context (secured by API)\n"
            "- Pri volani gtfs_apply_patch MUSIS pouzit tieto 2 hodnoty bez zmeny:\n"
            f"- confirmation_message: {json.dumps(confirmation_message, ensure_ascii=False)}\n"
            f"- confirmation_signature: {confirmation_signature}\n"
            "- Server aplikuje patch len ak confirmation_message je presne "
            "'/confirm <patch_hash>' a podpis sedi."
        )
        if _CONFIRM_MESSAGE_PATTERN.match((confirmation_message or "").strip()):
            runtime_context += (
                "\n- CONFIRM rezim: NEROB novy propose/validate, "
                "okamzite volaj gtfs_apply_patch presne raz.\n"
                '- V CONFIRM rezime pouzi patch_json: "{}" '
                "(server aplikuje patch podla potvrdeneho hashu)."
            )
        return SYSTEM_PROMPT + runtime_context

    async def run(
        self,
        vstup: str | list[dict],
        confirmation_message: str = "",
        confirmation_signature: str = "",
    ) -> str:
        """
        Spustí agenta a vráti finálnu odpoveď.

        Args:
            vstup: Buď textový príkaz (str) alebo zoznam správ
                   [{"role": "user", "content": "..."}, ...] pre multi-turn.

        Returns:
            Finálna odpoveď agenta ako string.
        """
        output, _profiling, _trace = await self.run_with_profiling(
            vstup=vstup,
            extra_instructions="",
            confirmation_message=confirmation_message,
            confirmation_signature=confirmation_signature,
        )
        return output

    async def run_with_profiling(
        self,
        vstup: str | list[dict],
        extra_instructions: str = "",
        confirmation_message: str = "",
        confirmation_signature: str = "",
        collect_trace: bool = False,
    ) -> tuple[str, AgentProfiling, AgentTrace]:
        """Spusti agenta a vrati finalny text spolu s rozpisom casu a trace."""
        mcp_server = MCPServerSse(
            name="gtfs-editor",
            params={
                "url": self.mcp_url,
                "timeout": 30,
                "sse_read_timeout": 300,
            },
            cache_tools_list=False,
        )

        async with mcp_server:
            instructions = self._compose_instructions(
                confirmation_message=confirmation_message,
                confirmation_signature=confirmation_signature,
            )
            if extra_instructions:
                instructions += f"\n\n## Extra inštrukcie od klientskej aplikácie:\n{extra_instructions}"

            agent = Agent(
                name="GTFSAgent",
                model=self.model,
                instructions=instructions,
                mcp_servers=[mcp_server],
            )
            hooks = _TracingHooks(collect_trace=collect_trace)
            started_at = time.perf_counter()
            result = await Runner.run(
                agent,
                input=vstup,
                hooks=hooks,
                max_turns=self.max_turns,
            )
            thinking_seconds = max(0.0, time.perf_counter() - started_at)
            profiling = hooks.to_profiling(thinking_seconds=thinking_seconds)
            trace = hooks.to_trace()
            return result.final_output, profiling, trace
