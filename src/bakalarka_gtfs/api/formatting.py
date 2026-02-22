"""
formatting.py — Utility functions for text formatting in API responses.
"""

from ..agent.models import AgentProfiling, AgentTrace
from ..agent.pricing import vypocitaj_cenu
from ..core.config import AGENT_MODEL


def format_timing_footer(profiling: AgentProfiling, prompt_tokens: int, completion_tokens: int) -> str:
    """
    Format casov pre nenapadny footer pod odpovedou.
    Zobrazuje sa pod ciarou, aby co najmenej rusil chat.
    """
    total_tokens = prompt_tokens + completion_tokens
    estimated_price = vypocitaj_cenu(AGENT_MODEL, prompt_tokens, completion_tokens)

    return (
        "\n\n---\n"
        f"_celkový čas rozmýšľania: {profiling.thinking_seconds:.2f} s_\n"
        f"_profiling: model {profiling.model_seconds:.2f} s | "
        f"db/mcp {profiling.db_mcp_seconds:.2f} s | "
        f"python {profiling.python_overhead_seconds:.2f} s_\n"
        f"_tokeny: {prompt_tokens} prompt / {completion_tokens} completion ({total_tokens} total) | "
        f"odhadovaná cena: **${estimated_price:.4f}**_"
    )


def format_trace_header(trace: AgentTrace) -> str:
    """
    Format trace ako markdown header blok nad odpovedou.
    Profesionalny styl — zobrazuje kompletny priebeh agenta.
    """
    md = trace.to_markdown()
    if not md:
        return ""
    return md + "\n---\n\n"
