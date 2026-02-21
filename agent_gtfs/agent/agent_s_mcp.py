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
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from agents import Agent, Runner
from agents.lifecycle import RunHooksBase
from agents.mcp import MCPServerSse

from .systemove_instrukcie import SYSTEM_PROMPT
from ..konfiguracia.nastavenia import MCP_SERVER_URL, AGENT_MODEL, AGENT_MAX_TURNS

_CONFIRM_MESSAGE_PATTERN = re.compile(r"^/confirm\s+[a-fA-F0-9]{64}$")


@dataclass
class AgentProfiling:
    """Rozpis casu pouzity na interny profiling odpovedi."""

    thinking_seconds: float
    model_seconds: float
    db_mcp_seconds: float
    python_overhead_seconds: float
    llm_calls: int
    tool_calls: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class TraceEntry:
    """Jeden zaznam v trace — udalost pocas behu agenta."""

    elapsed: float
    event: str
    detail: str


@dataclass
class AgentTrace:
    """Kolekcia trace zaznamov z jedneho behu agenta."""

    entries: list[TraceEntry] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Formatuje trace ako markdown tabulku (profesionalny styl, bez emoji)."""
        if not self.entries:
            return ""

        lines = [
            "**Agent Trace**\n",
            "| # | Cas | Udalost | Detail |",
            "|---|-----|---------|--------|",
        ]
        for i, entry in enumerate(self.entries, 1):
            detail_escaped = entry.detail.replace("|", "\\|")
            lines.append(
                f"| {i} | {entry.elapsed:.2f}s | {entry.event} | {detail_escaped} |"
            )
        lines.append("")
        return "\n".join(lines)


class _TracingHooks(RunHooksBase):
    """Hooky pre meranie casu a zber trace dat LLM/tool volani pocas behu agenta."""

    def __init__(self, collect_trace: bool = False) -> None:
        self._llm_starts: list[float] = []
        self._tool_starts: dict[int, list[float]] = defaultdict(list)
        self.model_seconds = 0.0
        self.db_mcp_seconds = 0.0
        self.llm_calls = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

        # Trace data
        self._collect_trace = collect_trace
        self._t0 = time.perf_counter()
        self._trace_entries: list[TraceEntry] = []

    def _elapsed(self) -> float:
        return max(0.0, time.perf_counter() - self._t0)

    def _add_trace(self, event: str, detail: str) -> None:
        if self._collect_trace:
            self._trace_entries.append(
                TraceEntry(elapsed=self._elapsed(), event=event, detail=detail)
            )

    # -- Agent lifecycle ---------------------------------------------------

    async def on_agent_start(self, context, agent) -> None:
        self._add_trace("AGENT START", f"{agent.name}")

    async def on_agent_end(self, context, agent, output) -> None:
        out_preview = str(output)[:120] if output else "(prazdny)"
        self._add_trace("AGENT END", f"{agent.name} -> {out_preview}")

    # -- LLM lifecycle -----------------------------------------------------

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self._llm_starts.append(time.perf_counter())
        items_count = len(input_items) if input_items else 0
        self._add_trace(
            "LLM START",
            f"model={agent.model or 'default'}, vstupnych_poloziek={items_count}"
        )

    async def on_llm_end(self, context, agent, response) -> None:
        if self._llm_starts:
            started = self._llm_starts.pop()
            self.model_seconds += max(0.0, time.perf_counter() - started)
        self.llm_calls += 1

        if hasattr(response, "usage") and response.usage:
            self.prompt_tokens += getattr(response.usage, "input_tokens", 0)
            self.completion_tokens += getattr(response.usage, "output_tokens", 0)
            self.total_tokens += getattr(response.usage, "total_tokens", 0)

        # Trace: sucet output poloziek podla typu
        if self._collect_trace and hasattr(response, "output"):
            type_counts: dict[str, int] = defaultdict(int)
            for item in response.output:
                item_type = getattr(item, "type", type(item).__name__)
                type_counts[str(item_type)] += 1
            types_str = ", ".join(f"{k}={v}" for k, v in type_counts.items())
            in_tok = getattr(response.usage, "input_tokens", 0) if response.usage else 0
            out_tok = getattr(response.usage, "output_tokens", 0) if response.usage else 0
            self._add_trace(
                "LLM END",
                f"vystup=[{types_str}], tokeny={in_tok}+{out_tok}"
            )

    # -- Tool lifecycle ----------------------------------------------------

    async def on_tool_start(self, context, agent, tool) -> None:
        self._tool_starts[id(tool)].append(time.perf_counter())
        tool_name = getattr(tool, "name", type(tool).__name__)
        self._add_trace("TOOL START", f"{tool_name}")

    async def on_tool_end(self, context, agent, tool, result) -> None:
        started_stack = self._tool_starts.get(id(tool))
        if started_stack:
            started = started_stack.pop()
            self.db_mcp_seconds += max(0.0, time.perf_counter() - started)
        self.tool_calls += 1

        tool_name = getattr(tool, "name", type(tool).__name__)
        result_preview = str(result)[:200] if result else "(prazdny)"
        # Skrat velmi dlhe vysledky
        if len(result_preview) >= 200:
            result_preview = result_preview[:197] + "..."
        self._add_trace("TOOL END", f"{tool_name} -> {result_preview}")

    # -- Konverzia na vysledky ---------------------------------------------

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
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
        )

    def to_trace(self) -> AgentTrace:
        return AgentTrace(entries=list(self._trace_entries))


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
                "- V CONFIRM rezime pouzi patch_json: \"{}\" "
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
