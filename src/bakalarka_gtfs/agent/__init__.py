"""
agent — GTFS agent logic.

Main class:
    GTFSAgent  — code-first agent that connects to an MCP server via SSE

Supporting modules:
    prompts    — system prompt (Slovak, defines agent behaviour and tools)
    pricing    — LLM token cost estimation per model

Usage::

    from bakalarka_gtfs.agent import GTFSAgent

    agent = GTFSAgent()
    answer = await agent.run("Koľko zastávok máme?")
"""

from .agent import GTFSAgent
from .models import AgentProfiling, AgentTrace

__all__ = ["AgentProfiling", "AgentTrace", "GTFSAgent"]
