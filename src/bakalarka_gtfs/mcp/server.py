"""
server.py — FastMCP server with GTFS tools, SSE transport.

Singleton database — all tools work with one current.db.
The first tool called should be gtfs_load, which imports GTFS data
if the DB doesn't exist yet.

Startup:
    via docker-compose service `gtfs-mcp`

Tools:
    1. gtfs_load          — import GTFS CSV dir -> SQLite (reuse if exists)
    2. gtfs_query          — read-only SQL SELECT
    3. gtfs_propose_patch  — diff/preview of proposed changes
    4. gtfs_validate_patch — FK, time ordering, required fields
    5. gtfs_apply_patch    — apply changes (atomic transaction, signed confirm)
    6. gtfs_export         — export SQLite -> GTFS ZIP
    7. gtfs_get_history    — audit log
    8. gtfs_show_map       — interactive map widget
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

from bakalarka_gtfs.mcp.database import ensure_loaded, export_to_gtfs, run_query
from bakalarka_gtfs.mcp.patching import (
    apply_patch,
    build_diff_summary,
    parse_patch,
    validate_patch,
)
from bakalarka_gtfs.mcp.visualization.map_template import get_map_html

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
        key for key, value in _PATCH_STATES.items() if now - value.get("created_at", now) > PATCH_STATE_TTL_SECONDS
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
    except Exception:
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
# Tool 7: gtfs_get_history
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_get_history(limit: int = 50) -> str:
    """
    Ziska historiu zmien (audit log) vykonanych nad GTFS databazou.

    Args:
        limit: Maximalny pocet predchadzajucich zaznamov na zobrazenie (predvolene 50).

    Returns:
        JSON pole zaznamov zoradenych od najnovsich.
    """
    try:
        sql = f"SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT {limit}"
        rows = run_query(sql)
        return _json_response({"history": rows, "count": len(rows)})
    except Exception as e:
        return _error_response(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool 8: gtfs_show_map
# ---------------------------------------------------------------------------


@mcp.tool()
def gtfs_show_map(
    route_id: str | None = None,
    trip_id: str | None = None,
    from_stop_id: str | None = None,
    to_stop_id: str | None = None,
    show_all_stops: bool = False,
) -> str:
    """
    Vygeneruje interaktívny HTML widget (Artifact) s mapou — buď zobrazí trasu/spoj, alebo všetky zastávky.

    Režimy použitia:
    A) show_all_stops=True: Zobrazí všetky zastávky v databáze na mape (ignoruje route_id/trip_id).
    B) trip_id: Zobrazí konkrétny trip a jeho zastávky.
    C) route_id: Zobrazí cestu s najvyšším počtom zastávok pre danú linku.
    D) route_id + from_stop_id + to_stop_id: Nájde trip na tejto linke,
       ktorý obsahuje obe zastávky v správnom poradí, a zobrazí len úsek medzi nimi.

    Args:
        route_id: ID linky (trasy).
        trip_id: Konkrétne ID trip-u.
        from_stop_id: ID počiatočnej zastávky (odkiaľ ide spoj). Použite spolu s route_id a to_stop_id.
        to_stop_id: ID cieľovej zastávky (kam ide spoj). Použite spolu s route_id a from_stop_id.
        show_all_stops: Ak True, zobrazí všetky zastávky v databáze na mape.

    Returns:
        LibreChat Artifact s interaktívnou mapou.
    """
    try:
        route_meta = {}

        # ===== REŽIM A: Všetky zastávky =====
        if show_all_stops:
            stops_sql = """
                SELECT
                    ROUND(AVG(stop_lat), 4) as lat,
                    ROUND(AVG(stop_lon), 4) as lon,
                    stop_name as name
                FROM stops
                GROUP BY stop_name
            """
            stops = run_query(stops_sql)
            if not stops:
                return _error_response("Prázdna databáza", "V databáze nie sú žiadne zastávky.")

            # Kompaktný formát: [[lat,lon,name], ...] — menšie než pole objektov
            compact = json.dumps(
                [[s["lat"], s["lon"], s["name"]] for s in stops],
                ensure_ascii=False,
            )
            # Minimálny HTML aby neprekročil limity LLM výstupu
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>*{{margin:0;padding:0}}body{{font-family:sans-serif}}
#h{{background:#1e293b;color:#fff;padding:8px 14px;font-size:14px;font-weight:600}}
#m{{height:560px;width:100%}}</style></head>
<body><div id="h">📍 Všetky zastávky ({len(stops)})</div><div id="m"></div>
<script>
var d={compact};
var m=L.map('m');
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19}}).addTo(m);
var b=[];
for(var i=0;i<d.length;i++){{
var s=d[i];b.push([s[0],s[1]]);
L.circleMarker([s[0],s[1]],{{radius:4,fillColor:'#F56200',color:'#fff',weight:1,fillOpacity:0.85}}).bindPopup('<b>'+s[2]+'</b>').addTo(m);
}}
m.fitBounds(b,{{padding:[30,30]}});
</script></body></html>"""

            return (
                ':::artifact{identifier="gtfs-map-all" type="text/html" title="Všetky zastávky"}\n'
                f"```html\n{html}\n```\n"
                ":::"
            )

        if not trip_id and not route_id:
            return _error_response("Chyba parametrov", "Zadaj buď trip_id, route_id, alebo show_all_stops=True.")

        # ===== Získat route_meta ak máme route_id =====
        if route_id:
            meta_sql = f"SELECT route_short_name, route_long_name, route_color FROM routes WHERE route_id = '{route_id}' LIMIT 1"
            meta_res = run_query(meta_sql)
            if meta_res:
                r = meta_res[0]
                route_meta = {
                    "route_short_name": r.get("route_short_name", ""),
                    "route_long_name": r.get("route_long_name", ""),
                    "route_color": r.get("route_color", "F56200"),
                }

        # ===== REŽIM D: Smerový výber (from → to) — celý trip s highlighted úsekom =====
        if not trip_id and route_id and from_stop_id and to_stop_id:
            direction_sql = f"""
                SELECT
                    st_from.trip_id,
                    st_from.stop_sequence AS seq_from,
                    st_to.stop_sequence AS seq_to
                FROM stop_times st_from
                JOIN stop_times st_to ON st_from.trip_id = st_to.trip_id
                JOIN trips t ON t.trip_id = st_from.trip_id
                WHERE t.route_id = '{route_id}'
                  AND st_from.stop_id = '{from_stop_id}'
                  AND st_to.stop_id = '{to_stop_id}'
                  AND st_from.stop_sequence < st_to.stop_sequence
                LIMIT 1
            """
            dir_res = run_query(direction_sql)
            if dir_res:
                trip_id = dir_res[0]["trip_id"]
                seq_from = dir_res[0]["seq_from"]
                seq_to = dir_res[0]["seq_to"]

                # Načítaj VŠETKY zastávky celého tripu
                all_stops_sql = f"""
                    SELECT
                        s.stop_lat as lat,
                        s.stop_lon as lon,
                        s.stop_name as name,
                        st.arrival_time as time,
                        st.stop_sequence as seq
                    FROM stop_times st
                    JOIN stops s ON st.stop_id = s.stop_id
                    WHERE st.trip_id = '{trip_id}'
                    ORDER BY st.stop_sequence ASC
                """
                stops = run_query(all_stops_sql)
                if stops:
                    # Nájdi 0-based indexy highlight úseku
                    highlight_from = None
                    highlight_to = None
                    for i, stop in enumerate(stops):
                        if stop["seq"] == seq_from:
                            highlight_from = i
                        if stop["seq"] == seq_to:
                            highlight_to = i

                    hs_sql = f"SELECT trip_headsign FROM trips WHERE trip_id = '{trip_id}' LIMIT 1"
                    hs_res = run_query(hs_sql)
                    route_meta["trip_headsign"] = hs_res[0]["trip_headsign"] if hs_res else ""

                    from_name = stops[highlight_from]["name"] if highlight_from is not None else ""
                    to_name = stops[highlight_to]["name"] if highlight_to is not None else ""
                    route_meta["title"] = (
                        f"Linka {route_meta.get('route_short_name', route_id)}: {from_name} → {to_name}"
                    )

                    html = get_map_html(
                        stops=stops,
                        shapes=[],
                        route_meta=route_meta,
                        highlight_from=highlight_from,
                        highlight_to=highlight_to,
                    )
                    artifact_id = f"gtfs-map-{route_id}-segment"
                    return (
                        f':::artifact{{identifier="{artifact_id}" type="text/html" title="{route_meta["title"]}"}}\n'
                        f"```html\n{html}\n```\n"
                        ":::"
                    )
            else:
                return _error_response(
                    "Nenajdený priamy spoj",
                    f"Pre route_id={route_id} neexistuje trip kde from_stop_id={from_stop_id} je pred to_stop_id={to_stop_id}. "
                    "Skús opačný smer alebo iný route_id.",
                )

        # ===== REŽIM B/C: Celý trip =====
        if not trip_id:
            trip_sql = f"""
                SELECT t.trip_id, COUNT(st.stop_id) as stop_count
                FROM trips t
                JOIN stop_times st ON t.trip_id = st.trip_id
                WHERE t.route_id = '{route_id}'
                GROUP BY t.trip_id
                ORDER BY stop_count DESC
                LIMIT 1
            """
            res = run_query(trip_sql)
            if not res:
                return _error_response("Nenajdené dáta", f"Pre route_id {route_id} sa nenašiel žiadny trip.")
            trip_id = res[0]["trip_id"]

        # Shapes
        shapes = []
        try:
            shape_sql = f"SELECT shape_id FROM trips WHERE trip_id = '{trip_id}'"
            res = run_query(shape_sql)
            shape_id = res[0]["shape_id"] if res and "shape_id" in res[0] and res[0]["shape_id"] else None
            if shape_id:
                coord_sql = f"SELECT shape_pt_lat as lat, shape_pt_lon as lon FROM shapes WHERE shape_id = '{shape_id}' ORDER BY shape_pt_sequence ASC"
                shapes = run_query(coord_sql)
        except Exception:
            pass

        # Zastávky
        stops_sql = f"""
            SELECT
                s.stop_lat as lat,
                s.stop_lon as lon,
                s.stop_name as name,
                st.arrival_time as time
            FROM stop_times st
            JOIN stops s ON st.stop_id = s.stop_id
            WHERE st.trip_id = '{trip_id}'
            ORDER BY st.stop_sequence ASC
        """
        stops = run_query(stops_sql)

        if not stops:
            return _error_response("Nenajdené zastávky", f"Pre trip_id {trip_id} sa nenašli žiadne zastávky.")

        # Headsign + route_id z trips ak chýba
        hs_sql = f"SELECT trip_headsign, route_id FROM trips WHERE trip_id = '{trip_id}' LIMIT 1"
        hs_res = run_query(hs_sql)
        if hs_res:
            route_meta["trip_headsign"] = hs_res[0].get("trip_headsign", "")
            if not route_id:
                route_id = hs_res[0].get("route_id", "")
        if not route_meta.get("route_short_name") and route_id:
            meta_sql = f"SELECT route_short_name, route_long_name, route_color FROM routes WHERE route_id = '{route_id}' LIMIT 1"
            meta_res = run_query(meta_sql)
            if meta_res:
                r = meta_res[0]
                route_meta["route_short_name"] = r.get("route_short_name", "")
                route_meta["route_long_name"] = r.get("route_long_name", "")
                route_meta["route_color"] = r.get("route_color", "F56200")

        title = f"Linka {route_meta.get('route_short_name', route_id)}: {stops[0]['name']} → {stops[-1]['name']}"
        route_meta["title"] = title

        html = get_map_html(stops=stops, shapes=shapes, route_meta=route_meta)
        artifact_id = f"gtfs-map-{route_id or trip_id}"
        return f':::artifact{{identifier="{artifact_id}" type="text/html" title="{title}"}}\n```html\n{html}\n```\n:::'
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
