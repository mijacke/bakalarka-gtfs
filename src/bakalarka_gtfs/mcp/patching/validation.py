"""
validation.py — Validation of a GTFS patch before application.

Checks:
  - FK integrity (e.g. route_id in trips must exist in routes)
  - time ordering for stop_times (arrival <= departure)
  - required fields on insert
  - warning if filter matches 0 rows
"""

from __future__ import annotations

import sqlite3

from ..database import _check_db, get_current_db
from .operations import _apply_transform, _filter_to_where

# ---------------------------------------------------------------------------
# FK relacie medzi GTFS tabulkami
# ---------------------------------------------------------------------------

_FK_RELATIONS: dict[str, list[tuple[str, str, str]]] = {
    # tabulka: [(stlpec, ref_tabulka, ref_stlpec), ...]
    "trips": [
        ("route_id", "routes", "route_id"),
        ("service_id", "calendar", "service_id"),
    ],
    "stop_times": [
        ("trip_id", "trips", "trip_id"),
        ("stop_id", "stops", "stop_id"),
    ],
}

# ---------------------------------------------------------------------------
# Povinne stlpce pre insert
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "stops": ["stop_id", "stop_name", "stop_lat", "stop_lon"],
    "routes": ["route_id", "route_short_name", "route_type"],
    "calendar": [
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ],
    "trips": ["trip_id", "route_id", "service_id"],
    "stop_times": [
        "trip_id",
        "arrival_time",
        "departure_time",
        "stop_id",
        "stop_sequence",
    ],
}


# ---------------------------------------------------------------------------
# Hlavna funkcia
# ---------------------------------------------------------------------------


def validate_patch(patch_json: dict) -> dict:
    """Zvaliduje patch a vrati zoznam problemov (errors, warnings)."""
    _check_db()
    db_path = get_current_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    errors: list[str] = []
    warnings: list[str] = []

    try:
        for i, op in enumerate(patch_json["operations"]):
            prefix = f"Op#{i + 1} ({op['op']} {op['table']})"
            op["table"]
            op_type = op["op"]

            if op_type == "insert":
                _validate_insert(conn, op, prefix, errors, warnings)
            elif op_type == "update":
                _validate_update(conn, op, prefix, errors, warnings)
            elif op_type == "delete":
                _validate_delete(conn, op, prefix, errors, warnings)
    finally:
        conn.close()

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Per-operacia validacie
# ---------------------------------------------------------------------------


def _validate_insert(
    conn: sqlite3.Connection,
    op: dict,
    prefix: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validacia INSERT operacie."""
    table = op["table"]
    rows = op.get("rows", [])

    required = _REQUIRED_FIELDS.get(table, [])
    for j, row in enumerate(rows):
        for field in required:
            if field not in row or row[field] is None or str(row[field]).strip() == "":
                errors.append(f"{prefix} row#{j + 1}: chyba povinny stlpec '{field}'.")

    fk_checks = _FK_RELATIONS.get(table, [])
    for j, row in enumerate(rows):
        for col, ref_table, ref_col in fk_checks:
            val = row.get(col)
            if val is not None:
                exists = conn.execute(
                    f"SELECT 1 FROM {ref_table} WHERE {ref_col} = ? LIMIT 1",
                    [val],
                ).fetchone()
                if not exists:
                    errors.append(f"{prefix} row#{j + 1}: FK chyba — {col}='{val}' neexistuje v {ref_table}.{ref_col}.")


def _validate_update(
    conn: sqlite3.Connection,
    op: dict,
    prefix: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validacia UPDATE operacie."""
    table = op["table"]
    flt = op["filter"]
    set_spec = op["set"]

    where, params = _filter_to_where(flt)
    count = conn.execute(f"SELECT COUNT(*) as c FROM {table} WHERE {where}", params).fetchone()["c"]

    if count == 0:
        warnings.append(f"{prefix}: filter matchuje 0 riadkov.")
        return

    fk_checks = _FK_RELATIONS.get(table, [])
    for col, ref_table, ref_col in fk_checks:
        if col in set_spec:
            val = set_spec[col]
            if isinstance(val, dict) and "transform" in val:
                continue
            exists = conn.execute(
                f"SELECT 1 FROM {ref_table} WHERE {ref_col} = ? LIMIT 1",
                [val],
            ).fetchone()
            if not exists:
                errors.append(f"{prefix}: FK chyba — {col}='{val}' neexistuje v {ref_table}.{ref_col}.")

    if table == "stop_times":
        _validate_time_ordering(conn, op, prefix, errors, warnings)


def _validate_time_ordering(
    conn: sqlite3.Connection,
    op: dict,
    prefix: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """
    Kontrola ze po update bude arrival_time <= departure_time
    pre stop_times.
    """
    set_spec = op["set"]
    if "arrival_time" not in set_spec and "departure_time" not in set_spec:
        return

    where, params = _filter_to_where(op["filter"])
    cursor = conn.execute(
        f"SELECT arrival_time, departure_time FROM stop_times WHERE {where}",
        params,
    )

    for row in cursor:
        arr = row["arrival_time"]
        dep = row["departure_time"]

        if "arrival_time" in set_spec:
            val = set_spec["arrival_time"]
            if isinstance(val, dict) and "transform" in val:
                arr = _apply_transform(arr, val)
            else:
                arr = val

        if "departure_time" in set_spec:
            val = set_spec["departure_time"]
            if isinstance(val, dict) and "transform" in val:
                dep = _apply_transform(dep, val)
            else:
                dep = val

        try:
            arr_seconds = _gtfs_time_to_seconds(str(arr)) if arr not in (None, "") else None
            dep_seconds = _gtfs_time_to_seconds(str(dep)) if dep not in (None, "") else None
        except ValueError as e:
            errors.append(f"{prefix}: neplatny format casu po update: {e}")
            break

        if arr_seconds is not None and dep_seconds is not None and arr_seconds > dep_seconds:
            errors.append(f"{prefix}: po update arrival_time ({arr}) > departure_time ({dep}).")
            break


def _gtfs_time_to_seconds(time_str: str) -> int:
    """Prevedie GTFS cas HH:MM:SS (HH moze byt >24) na sekundy."""
    parts = time_str.split(":")
    if len(parts) != 3:
        raise ValueError(f"'{time_str}' (ocakavany format HH:MM:SS)")

    h, m, s = (int(parts[0]), int(parts[1]), int(parts[2]))
    if m < 0 or m > 59 or s < 0 or s > 59 or h < 0:
        raise ValueError(f"'{time_str}' (neplatne hodnoty casu)")
    return h * 3600 + m * 60 + s


def _validate_delete(
    conn: sqlite3.Connection,
    op: dict,
    prefix: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validacia DELETE operacie."""
    table = op["table"]
    where, params = _filter_to_where(op["filter"])
    count = conn.execute(f"SELECT COUNT(*) as c FROM {table} WHERE {where}", params).fetchone()["c"]

    if count == 0:
        warnings.append(f"{prefix}: filter matchuje 0 riadkov, nic sa nezmaze.")

    # Pri zapnutych FK by tieto operacie pri aplikacii aj tak zlyhali.
    if table == "trips":
        affected_trip_ids = conn.execute(f"SELECT trip_id FROM trips WHERE {where}", params).fetchall()
        for row in affected_trip_ids:
            ref_count = conn.execute(
                "SELECT COUNT(*) as c FROM stop_times WHERE trip_id = ?",
                [row["trip_id"]],
            ).fetchone()["c"]
            if ref_count > 0:
                errors.append(f"{prefix}: mazanie trip_id='{row['trip_id']}' blokuje {ref_count} riadkov v stop_times.")

    if table in ("routes", "calendar"):
        child_table = "trips"
        col = "route_id" if table == "routes" else "service_id"
        affected_ids = conn.execute(f"SELECT {col} FROM {table} WHERE {where}", params).fetchall()
        for row in affected_ids:
            ref_count = conn.execute(
                f"SELECT COUNT(*) as c FROM {child_table} WHERE {col} = ?",
                [row[col]],
            ).fetchone()["c"]
            if ref_count > 0:
                errors.append(f"{prefix}: mazanie {col}='{row[col]}' blokuje {ref_count} riadkov v {child_table}.")
