# Bakalarka GTFS

Projekt na editáciu mestských cestovných poriadkov (GTFS) pomocou LLM agenta.
Obsahuje MCP server s nástrojmi na prácu s GTFS dátami a OpenAI-kompatibilné
API pre pripojenie z LibreChat.

## Štruktúra projektu

```
src/bakalarka_gtfs/          # Hlavný balík
├── core/config.py           # Konfigurácia z .env
├── agent/                   # GTFS agent
│   ├── agent.py             # GTFSAgent trieda (code-first)
│   ├── prompts.py           # System prompt a pravidlá
│   └── pricing.py           # Oceňovanie tokenov
├── api/server.py            # FastAPI — OpenAI-kompatibilný endpoint
└── mcp/                     # MCP server a GTFS nástroje
    ├── server.py            # FastMCP server (SSE transport)
    ├── database.py          # SQLite import/export/query
    ├── patching/             # Patch operácie a validácia
    │   ├── operations.py
    │   └── validation.py
    └── visualization/        # Interaktívna mapa
        └── map_template.py

config/librechat/            # Konfigurácia LibreChat endpointu
data/gtfs_latest/            # Zdrojové GTFS .txt súbory
docs/                        # Dokumentácia
experiments/                 # Experimenty a evaluácie
tests/                       # Unit testy
.work/                       # Runtime dáta (SQLite DB, exporty)
```

## Spustenie cez Docker

1. Vytvor `.env` z `.env.example` a doplň kľúče.
2. Spusti stack:
   ```bash
   docker compose up -d --build
   ```
3. Otvor LibreChat: `http://localhost:3090`
4. Aktívne endpointy v LibreChat:
   - **GTFS Agent** (custom endpoint na `gtfs-api`)
   - OpenAI
   - Anthropic

## Autorizácia GTFS API

- API overuje kľúč z `.env` (`GTFS_API_KEY`) cez:
  - `Authorization: Bearer <GTFS_API_KEY>`
  - alebo `x-api-key: <GTFS_API_KEY>`

## Bezpečné potvrdenie apply kroku

- `gtfs_apply_patch` je server-side chránený:
  - vyžaduje workflow `propose → validate → explicitný user confirm`
  - potvrdenie musí byť v tvare: `/confirm <patch_hash>`
- Podpis sa overuje cez shared secret (`GTFS_CONFIRMATION_SECRET`)

## Timing footer / Trace header

- Footer pod odpoveďou: `GTFS_SHOW_TIMING_FOOTER=true|false`
- Trace header (priebeh agenta): `GTFS_SHOW_TRACE_HEADER=true|false`
- Server trace logy: `GTFS_ENABLE_TRACE_LOGS=true|false`

## Testy

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
