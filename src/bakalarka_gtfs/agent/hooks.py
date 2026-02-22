"""
hooks.py — Hooks for measuring LLM and tool calls during agent execution.
"""

import json
import time
from collections import defaultdict

from agents.lifecycle import RunHooksBase

from .models import AgentProfiling, AgentTrace, TraceEntry


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
            self._trace_entries.append(TraceEntry(elapsed=self._elapsed(), event=event, detail=detail))

    def _format_long_text(self, text: str, max_preview: int = 100) -> str:
        """Skrati dlhy text na max_preview znakov s '…' na konci."""
        text_str = str(text) if text is not None else "(prázdne)"
        clean = text_str.replace("\n", " ").strip()
        if len(clean) <= max_preview:
            return clean
        return clean[:max_preview] + " …"

    # -- Agent lifecycle ---------------------------------------------------

    async def on_agent_start(self, context, agent) -> None:
        self._add_trace("AGENT START", f"{agent.name}")

    async def on_agent_end(self, context, agent, output) -> None:
        detail = f"{agent.name} -> " + self._format_long_text(output)
        self._add_trace("AGENT END", detail)

    # -- LLM lifecycle -----------------------------------------------------

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self._llm_starts.append(time.perf_counter())
        items_count = len(input_items) if input_items else 0
        self._add_trace("LLM START", f"model={agent.model or 'default'}, vstupnych_poloziek={items_count}")

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
            self._add_trace("LLM END", f"vystup=[{types_str}], tokeny={in_tok}+{out_tok}")

    # -- Tool lifecycle ----------------------------------------------------

    async def on_tool_start(self, context, agent, tool) -> None:
        self._tool_starts[id(tool)].append(time.perf_counter())
        tool_name = getattr(tool, "name", type(tool).__name__)
        tool_input = getattr(context, "tool_input", None)
        if tool_input:
            in_str = f"vstup={json.dumps(tool_input, ensure_ascii=False)}"
            detail = f"{tool_name} | " + self._format_long_text(in_str, max_preview=100)
        else:
            detail = f"{tool_name}"
        self._add_trace("TOOL START", detail)

    async def on_tool_end(self, context, agent, tool, result) -> None:
        started_stack = self._tool_starts.get(id(tool))
        if started_stack:
            started = started_stack.pop()
            self.db_mcp_seconds += max(0.0, time.perf_counter() - started)
        self.tool_calls += 1

        tool_name = getattr(tool, "name", type(tool).__name__)
        detail = f"{tool_name} -> " + self._format_long_text(result, max_preview=120)
        self._add_trace("TOOL END", detail)

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
