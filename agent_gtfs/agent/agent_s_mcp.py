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

from agents import Agent, Runner
from agents.mcp import MCPServerSse

from .systemove_instrukcie import SYSTEM_PROMPT
from ..konfiguracia.nastavenia import MCP_SERVER_URL, AGENT_MODEL


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

            result = await Runner.run(agent, input=vstup)
            return result.final_output
