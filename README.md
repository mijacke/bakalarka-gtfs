# Bakalarka GTFS

Projekt je prehladne rozdeleny na kod, konfiguraciu, data a dokumentaciu.
Runtime je nastavene primarne na Docker Desktop (bez lokalneho CLI workflow).

## Struktura projektu

- `agent_gtfs/`
  - `agent/agent_s_mcp.py` - custom GTFS agent s napojenim na MCP cez SSE
  - `agent/systemove_instrukcie.py` - system prompt a policy agenta
  - `api/api_server.py` - OpenAI-kompatibilny API endpoint pre LibreChat
  - `konfiguracia/nastavenia.py` - nacitanie konfiguracie z `.env`
- `server_mcp_gtfs/`
  - `server/server_tools.py` - FastMCP server so 6 GTFS toolmi
  - `databaza/databaza.py` - import/export GTFS a SQLite vrstva
  - `patchovanie/operacie_patchu.py` - patch parser, preview diff, apply operacie
  - `patchovanie/validacia.py` - validacia patchov (FK, casy, required fields)
- `konfiguracia/librechat/`
  - `librechat.yaml` - custom endpoint pre GTFS agenta
- `data/gtfs_latest/`
  - zdrojove GTFS `.txt` subory
- `dokumentacia/plany/`
  - planovacie a navrhove dokumenty
- `.work/`
  - runtime data (SQLite DB, exporty)
- `Dockerfile`
  - image pre `gtfs-mcp` a `gtfs-api`
- `docker-compose.yml`
  - cely stack: LibreChat + GTFS API + MCP + MongoDB + Meilisearch
- `requirements.txt`
  - runtime zavislosti pre Docker image

## Poznamka k `__init__.py`

- `__init__.py` subory su zamerne odstranene, aby bol kod menej zahlteny.
- Projekt funguje ako namespace baliky (Python 3.12) a spusta sa cez Docker.

## Spustenie cez Docker

1. Vytvor `.env` z `.env.example` a dopln kluce.
2. Spusti stack:
   - `docker compose up -d --build`
3. Otvor LibreChat:
   - `http://localhost:${LIBRECHAT_PORT}` (default `http://localhost:3090`)
4. V LibreChat su aktivne endpointy:
   - `GTFS Agent` (custom endpoint na `gtfs-api`)
   - `OpenAI`
   - `Anthropic`

## Autorizacia GTFS API

- API overuje kluc z `.env` (`GTFS_API_KEY`) cez:
  - `Authorization: Bearer <GTFS_API_KEY>`
  - alebo `x-api-key: <GTFS_API_KEY>`
- Endpointy bez platneho kluca vracaju `401` a payload:
  - `{"error":{"message":"Invalid API key.",...}}`

## Overenie autorizacie (realny test)

- Testovane 19.02.2026 proti `http://127.0.0.1:8000/v1/models`:
  - bez kluca -> `401`
  - zly kluc -> `401`
  - spravny kluc (`gtfs-agent-key`) -> `200`
