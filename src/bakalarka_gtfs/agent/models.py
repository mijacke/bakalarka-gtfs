"""
models.py — Data structures for agent tracing and profiling.
"""

from dataclasses import dataclass, field


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
            "| # | Výskyt | Udalosť | Detail |",
            "|---|--------|---------|--------|",
        ]
        for i, entry in enumerate(self.entries, 1):
            detail_val = entry.detail.replace("\n", "<br>")
            detail_val = detail_val.replace("|", "\\|")
            lines.append(f"| {i} | {entry.elapsed:.2f}s | {entry.event} | {detail_val} |")
            
        lines.append("")
        lines.append("*Vysvetlivky:* `vstupnych_poloziek` = počet správ do LLM; `reasoning` = myšlienkové kroky (LLM si analyzuje postup); `function_call` = volanie nástroja (napr. načítať dáta z DB); `message` = textová odpoveď agenta.\n")
        return "\n".join(lines)
