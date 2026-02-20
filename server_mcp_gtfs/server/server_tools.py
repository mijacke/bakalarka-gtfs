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
    5. gtfs_apply_patch    — aplikacia zmien (atomic transakcia, signed confirm)
    6. gtfs_export         — export SQLite -> GTFS ZIP
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
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

CONFIRMATION_SECRET = os.getenv("GTFS_CONFIRMATION_SECRET", "change-me-in-env")
PATCH_STATE_TTL_SECONDS = int(os.getenv("GTFS_PATCH_STATE_TTL_SECONDS", "1800"))
CONFIRM_PATTERN = re.compile(r"^/confirm\s+([a-fA-F0-9]{64})$")

# In-memory stav patch workflow (propose -> validate -> apply).
_PATCH_STATES: dict[str, dict] = {}


def _json_response(data: dict | list) -> str:
    """Serializuje odpoved do JSON s peknym formatovanim."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _error_response(msg: str, detail: str = "") -> str:
    """Generuje chybovu odpoved."""
    return _json_response({"error": msg, "detail": detail})


def _patch_hash(patch: dict) -> str:
    """Stabilny hash patchu (SHA-256 z canonical JSON)."""
    canonical = json.dumps(patch, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cleanup_patch_states() -> None:
    """Odstrani expirovane stavy patchov."""
    now = time.time()
    expired_keys = [
        key
        for key, value in _PATCH_STATES.items()
        if now - value.get("created_at", now) > PATCH_STATE_TTL_SECONDS
    ]
    for key in expired_keys:
        _PATCH_STATES.pop(key, None)


def _mark_proposed(patch_hash: str, patch: dict) -> None:
    now = time.time()
    _PATCH_STATES[patch_hash] = {
        "created_at": now,
        "proposed_at": now,
        "validated_at": None,
        "validated_ok": False,
        "patch": patch,
    }


def _mark_validated(patch_hash: str, valid: bool) -> None:
    state = _PATCH_STATES.get(patch_hash)
    if state is None:
        return
    state["validated_at"] = time.time()
    state["validated_ok"] = bool(valid)


def _sign_confirmation_message(message: str) -> str:
    return hmac.new(
        CONFIRMATION_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _validate_confirmation(
    patch_hash: str,
    confirmation_message: str,
    confirmation_signature: str,
) -> tuple[bool, str]:
    msg = (confirmation_message or "").strip()
    sig = (confirmation_signature or "").strip()

    if not msg or not sig:
        return False, "Chyba explicitne potvrdenie. Pouzi '/confirm <patch_hash>'."

    expected_sig = _sign_confirmation_message(msg)
    if not hmac.compare_digest(expected_sig, sig):
        return False, "Neplatny podpis potvrdenia pouzivatela."

    match = CONFIRM_PATTERN.match(msg)
    if not match:
        return False, "Neplatny format potvrdenia. Pouzi '/confirm <patch_hash>'."

    confirmed_hash = match.group(1).lower()
    if confirmed_hash != patch_hash:
        return False, "Potvrdenie patri k inemu patch_hash."

    return True, ""


def _extract_confirmed_hash(
    confirmation_message: str,
    confirmation_signature: str,
) -> tuple[str | None, str]:
    """Overi podpis a format potvrdenia, vrati potvrdeny patch_hash."""
    msg = (confirmation_message or "").strip()
    sig = (confirmation_signature or "").strip()

    if not msg or not sig:
        return None, "Chyba explicitne potvrdenie. Pouzi '/confirm <patch_hash>'."

    expected_sig = _sign_confirmation_message(msg)
    if not hmac.compare_digest(expected_sig, sig):
        return None, "Neplatny podpis potvrdenia pouzivatela."

    match = CONFIRM_PATTERN.match(msg)
    if not match:
        return None, "Neplatny format potvrdenia. Pouzi '/confirm <patch_hash>'."

    return match.group(1).lower(), ""


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
    Ak dotaz nema LIMIT, pouzije sa predvoleny limit 500 riadkov.

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
        _cleanup_patch_states()
        patch = parse_patch(patch_json)
        summary = build_diff_summary(patch)
        patch_hash = _patch_hash(patch)
        _mark_proposed(patch_hash, patch)
        summary["patch_hash"] = patch_hash
        summary["confirm_command"] = f"/confirm {patch_hash}"
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
        _cleanup_patch_states()
        patch = parse_patch(patch_json)
        patch_hash = _patch_hash(patch)
        state = _PATCH_STATES.get(patch_hash)
        if state is None or not state.get("proposed_at"):
            return _error_response(
                "Workflow violation",
                "Najprv zavolaj gtfs_propose_patch pre rovnaky patch_json.",
            )

        result = validate_patch(patch)
        _mark_validated(patch_hash, result.get("valid", False))
        result["patch_hash"] = patch_hash
        result["confirm_command"] = f"/confirm {patch_hash}"
        return _json_response(result)
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 5: gtfs_apply_patch
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_apply_patch(
    patch_json: str,
    confirmation_message: str,
    confirmation_signature: str,
) -> str:
    """
    Aplikuje patch na databazu v SQLite transakcii (atomic).
    POZOR: Volaj len po propose_patch + validate_patch + user confirm!

    Args:
        patch_json: JSON s operaciami (rovnaky format ako propose/validate)
        confirmation_message: Posledna user sprava, ktora ma byt vo formate
            '/confirm <patch_hash>'.
        confirmation_signature: HMAC SHA-256 podpis confirmation_message.

    Returns:
        JSON s {applied: true, affected_rows: {...}}.
    """
    try:
        _cleanup_patch_states()
        confirmed_hash, detail = _extract_confirmed_hash(
            confirmation_message=confirmation_message,
            confirmation_signature=confirmation_signature,
        )
        if not confirmed_hash:
            return _error_response("Missing or invalid confirmation", detail)

        state = _PATCH_STATES.get(confirmed_hash)
        if state is None or not state.get("proposed_at"):
            return _error_response(
                "Workflow violation",
                "Patch nebol navrhnuty cez gtfs_propose_patch.",
            )
        if not state.get("validated_at"):
            return _error_response(
                "Workflow violation",
                "Patch nebol validovany cez gtfs_validate_patch.",
            )
        if not state.get("validated_ok"):
            return _error_response(
                "Validation failed",
                "Patch nie je validny. Oprav chyby a validuj znova.",
            )

        confirmation_ok, detail = _validate_confirmation(
            confirmed_hash,
            confirmation_message,
            confirmation_signature,
        )
        if not confirmation_ok:
            return _error_response("Missing or invalid confirmation", detail)

        # Pouzi presne patch ulozeny pri propose kroku, aby apply nepadol
        # na rozdieloch v patch_json serializacii medzi volaniami.
        state_patch = state.get("patch")
        if not isinstance(state_patch, dict):
            return _error_response(
                "Workflow violation",
                "Chyba interny stav patchu. Navrhni patch znova cez gtfs_propose_patch.",
            )

        parsed_apply_hash = None
        try:
            parsed_apply_patch = parse_patch(patch_json)
            parsed_apply_hash = _patch_hash(parsed_apply_patch)
        except Exception:
            # apply prebehne podla potvrdeneho hashu a ulozeneho patchu z propose
            pass
        if parsed_apply_hash and parsed_apply_hash != confirmed_hash:
            state["apply_patch_mismatch"] = True
            state["apply_patch_mismatch_hash"] = parsed_apply_hash

        result = apply_patch(state_patch)
        _PATCH_STATES.pop(confirmed_hash, None)
        result["patch_hash"] = confirmed_hash
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
