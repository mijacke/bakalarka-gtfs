"""
agent_s_mcp.py — GTFSAgent trieda.

Pripája sa na MCP server cez SSE a umožňuje editáciu GTFS dát
cez textové príkazy. Dá sa volať z akejkoľvek Python aplikácie.

Použitie:
    from agent_gtfs import GTFSAgent

    agent = GTFSAgent()
    result = await agent.run("Koľko zastávok máme?")
    print(result)
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from agents import Agent, Runner
from agents.lifecycle import RunHooksBase
from agents.mcp import MCPServerSse

from .systemove_instrukcie import SYSTEM_PROMPT
from ..konfiguracia.nastavenia import MCP_SERVER_URL, AGENT_MODEL


@dataclass
class AgentProfiling:
    """Rozpis casu pouzity na interny profiling odpovedi."""

    thinking_seconds: float
    model_seconds: float
    db_mcp_seconds: float
    python_overhead_seconds: float
    llm_calls: int
    tool_calls: int


class _ProfilingHooks(RunHooksBase):
    """Hooky pre meranie casu LLM a tool volani pocas behu agenta."""

    def __init__(self) -> None:
        self._llm_starts: list[float] = []
        self._tool_starts: dict[int, list[float]] = defaultdict(list)
        self.model_seconds = 0.0
        self.db_mcp_seconds = 0.0
        self.llm_calls = 0
        self.tool_calls = 0

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self._llm_starts.append(time.perf_counter())

    async def on_llm_end(self, context, agent, response) -> None:
        if self._llm_starts:
            started = self._llm_starts.pop()
            self.model_seconds += max(0.0, time.perf_counter() - started)
        self.llm_calls += 1

    async def on_tool_start(self, context, agent, tool) -> None:
        self._tool_starts[id(tool)].append(time.perf_counter())

    async def on_tool_end(self, context, agent, tool, result) -> None:
        started_stack = self._tool_starts.get(id(tool))
        if started_stack:
            started = started_stack.pop()
            self.db_mcp_seconds += max(0.0, time.perf_counter() - started)
        self.tool_calls += 1

    def to_profiling(self, thinking_seconds: float) -> AgentProfiling:
        model = max(0.0, min(self.model_seconds, thinking_seconds))
        db_mcp = max(0.0, min(self.db_mcp_seconds, max(0.0, thinking_seconds - model)))
        python_overhead = max(0.0, thinking_seconds - model - db_mcp)
        return AgentProfiling(
            thinking_seconds=thinking_seconds,
            model_seconds=model,
            db_mcp_seconds=db_mcp,
            python_overhead_seconds=python_overhead,
            llm_calls=self.llm_calls,
            tool_calls=self.tool_calls,
        )


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
    ):
        self.mcp_url = mcp_url
        self.model = model

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
        output, _profiling = await self.run_with_profiling(
            vstup=vstup,
            confirmation_message=confirmation_message,
            confirmation_signature=confirmation_signature,
        )
        return output

    async def run_with_profiling(
        self,
        vstup: str | list[dict],
        confirmation_message: str = "",
        confirmation_signature: str = "",
    ) -> tuple[str, AgentProfiling]:
        """Spusti agenta a vrati finalny text spolu s rozpisom casu."""
        mcp_server = MCPServerSse(
            name="gtfs-editor",
            params={
                "url": self.mcp_url,
                "timeout": 30,
                "sse_read_timeout": 300,
            },
            cache_tools_list=True,
        )

        async with mcp_server:
            instructions = self._compose_instructions(
                confirmation_message=confirmation_message,
                confirmation_signature=confirmation_signature,
            )
            agent = Agent(
                name="GTFSAgent",
                model=self.model,
                instructions=instructions,
                mcp_servers=[mcp_server],
            )
            hooks = _ProfilingHooks()
            started_at = time.perf_counter()
            result = await Runner.run(agent, input=vstup, hooks=hooks)
            thinking_seconds = max(0.0, time.perf_counter() - started_at)
            profiling = hooks.to_profiling(thinking_seconds=thinking_seconds)
            return result.final_output, profiling
