"""
server_tools.py — FastMCP server so 6 GTFS tools, SSE transport.

Singleton databaza — vsetky nastroje pracuju s jednou current.db.
Prvy volany tool by mal byt gtfs_load, ktory naimportuje GTFS data
ak DB este neexistuje.

Spustenie:
    cez docker-compose service `gtfs-mcp`

Tools:
    1. gtfs_load          — import GTFS CSV dir -> SQLite (reuse ak uz existuje)
    2. gtfs_query          — read-only SQL SELECT
    3. gtfs_propose_patch  — diff/preview navrhovanych zmien
    4. gtfs_validate_patch — FK, time ordering, required fields
    5. gtfs_apply_patch    — aplikacia zmien (atomic transakcia)
    6. gtfs_export         — export SQLite -> GTFS ZIP
"""

from __future__ import annotations

import json
import traceback

from mcp.server.fastmcp import FastMCP

from server_mcp_gtfs.databaza.databaza import ensure_loaded, run_query, export_to_gtfs
from server_mcp_gtfs.patchovanie.operacie_patchu import (
    parse_patch,
    build_diff_summary,
    apply_patch,
)
from server_mcp_gtfs.patchovanie.validacia import validate_patch

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "gtfs-editor",
    host="0.0.0.0",
    port=8808,
)


def _json_response(data: dict | list) -> str:
    """Serializuje odpoved do JSON s peknym formatovanim."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _error_response(msg: str, detail: str = "") -> str:
    """Generuje chybovu odpoved."""
    return _json_response({"error": msg, "detail": detail})


# ---------------------------------------------------------------------------
# Tool 1: gtfs_load
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_load(feed_path: str, force: bool = False) -> str:
    """
    Nacita GTFS data z adresara do SQLite.
    Ak DB uz existuje, len vrati info (pouzije existujucu).
    S force=True vymaze staru DB a naimportuje znova.

    Args:
        feed_path: Cesta k GTFS adresaru (napr. "data/gtfs_latest")
        force: Ak True, vymaze existujucu DB a naimportuje znova

    Returns:
        JSON s info o databaze a poctami riadkov v tabulkach.
    """
    try:
        result = ensure_loaded(feed_path, force=force)
        return _json_response(result)
    except Exception as e:
        return _error_response("Chyba pri nacitani GTFS", traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 2: gtfs_query
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_query(sql: str) -> str:
    """
    Vykona read-only SQL SELECT dotaz nad GTFS databazou.
    Maximalne 100 riadkov.

    Args:
        sql: SQL SELECT dotaz
             (napr. "SELECT * FROM stops WHERE stop_name LIKE '%Hlavna%'")

    Returns:
        JSON pole riadkov.
    """
    try:
        rows = run_query(sql)
        return _json_response({"rows": rows, "count": len(rows)})
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 3: gtfs_propose_patch
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_propose_patch(patch_json: str) -> str:
    """
    Navrhne zmeny a ukaze before/after diff preview BEZ aplikacie.

    Args:
        patch_json: JSON s operaciami podla patch schema.
            Priklad:
            {
              "operations": [
                {
                  "op": "update",
                  "table": "stop_times",
                  "filter": {
                    "column": "arrival_time",
                    "operator": ">=",
                    "value": "20:00:00"
                  },
                  "set": {
                    "arrival_time": {
                      "transform": "time_add",
                      "minutes": 10
                    }
                  }
                }
              ]
            }

    Returns:
        JSON diff summary s before/after ukazkami.
    """
    try:
        patch = parse_patch(patch_json)
        summary = build_diff_summary(patch)
        return _json_response(summary)
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 4: gtfs_validate_patch
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_validate_patch(patch_json: str) -> str:
    """
    Validuje patch BEZ aplikacie.
    Kontroluje FK integritu, time ordering, required fields.

    Args:
        patch_json: JSON s operaciami (rovnaky format ako propose_patch)

    Returns:
        JSON s {valid: bool, errors: [...], warnings: [...]}.
    """
    try:
        patch = parse_patch(patch_json)
        result = validate_patch(patch)
        return _json_response(result)
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 5: gtfs_apply_patch
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_apply_patch(patch_json: str) -> str:
    """
    Aplikuje patch na databazu v SQLite transakcii (atomic).
    POZOR: Volaj len po propose_patch + validate_patch + user confirm!

    Args:
        patch_json: JSON s operaciami (rovnaky format ako propose/validate)

    Returns:
        JSON s {applied: true, affected_rows: {...}}.
    """
    try:
        patch = parse_patch(patch_json)
        result = apply_patch(patch)
        return _json_response(result)
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 6: gtfs_export
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_export(output_path: str) -> str:
    """
    Exportuje databazu spat do GTFS ZIP suboru.

    Args:
        output_path: Cesta pre vystupny .zip
                     (napr. ".work/exports/feed.zip")

    Returns:
        JSON s cestou k vytvorenemu suboru.
    """
    try:
        path = export_to_gtfs(output_path)
        return _json_response({"exported": True, "path": path})
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    """Spusti MCP server cez SSE transport na porte 8808."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
