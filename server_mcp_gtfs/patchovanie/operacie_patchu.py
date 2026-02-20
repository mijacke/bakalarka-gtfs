"""
operacie_patchu.py — Patch JSON schema, diff summary builder, transformy.

Patch je zoznam operacii (update / delete / insert) nad GTFS tabulkami.
Tento modul:
  - parsuje a validuje patch JSON strukturu,
  - generuje before/after diff preview,
  - aplikuje transformy (time_add),
  - vykonava mutacie v SQLite transakcii.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from ..databaza.databaza import get_current_db, _check_db

# ---------------------------------------------------------------------------
# Patch JSON schema types
# ---------------------------------------------------------------------------

VALID_OPS = {"update", "delete", "insert"}
VALID_TABLES = {"stops", "routes", "calendar", "trips", "stop_times"}
VALID_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "IN", "LIKE"}


def parse_patch(patch_json: str) -> dict:
    """Parsuje patch JSON string, vrati dict s validovanou strukturou."""
    data = json.loads(patch_json)
    if "operations" not in data:
        raise ValueError("Patch JSON musi obsahovat kluc 'operations'.")
    for i, op in enumerate(data["operations"]):
        _validate_operation(op, i)
    return data


def _validate_operation(op: dict, idx: int) -> None:
    """Validuje jednu operaciu v patchi."""
    prefix = f"Operacia #{idx + 1}"
    if "op" not in op:
        raise ValueError(f"{prefix}: chyba 'op'.")
    if op["op"] not in VALID_OPS:
        raise ValueError(f"{prefix}: neplatny op '{op['op']}'. Povolene: {VALID_OPS}")
    if "table" not in op:
        raise ValueError(f"{prefix}: chyba 'table'.")
    if op["table"] not in VALID_TABLES:
        raise ValueError(
            f"{prefix}: neplatna tabulka '{op['table']}'. Povolene: {VALID_TABLES}"
        )

    if op["op"] in ("update", "delete") and "filter" not in op:
        raise ValueError(f"{prefix}: operacia '{op['op']}' vyzaduje 'filter'.")
    if op["op"] == "update" and "set" not in op:
        raise ValueError(f"{prefix}: 'update' vyzaduje 'set'.")
    if op["op"] == "insert" and "rows" not in op:
        raise ValueError(f"{prefix}: 'insert' vyzaduje 'rows'.")

    if "filter" in op:
        _validate_filter_spec(op["filter"], prefix)


def _validate_filter_spec(flt: dict | list, prefix: str) -> None:
    """Validuje filter (simple alebo zlozeny cez and/or)."""
    if isinstance(flt, list):
        if not flt:
            raise ValueError(f"{prefix}: filter zoznam nesmie byt prazdny.")
        for child in flt:
            _validate_filter_spec(child, prefix)
        return

    if not isinstance(flt, dict):
        raise ValueError(f"{prefix}: filter musi byt objekt alebo zoznam objektov.")

    has_and = "and" in flt
    has_or = "or" in flt
    if has_and and has_or:
        raise ValueError(f"{prefix}: filter nemoze mat sucasne 'and' aj 'or'.")

    if has_and or has_or:
        logic_key = "and" if has_and else "or"
        children = flt.get(logic_key)
        if not isinstance(children, list) or not children:
            raise ValueError(f"{prefix}: '{logic_key}' musi byt neprazdny zoznam.")
        for child in children:
            _validate_filter_spec(child, prefix)
        return

    missing = [key for key in ("column", "operator", "value") if key not in flt]
    if missing:
        raise ValueError(f"{prefix}: filter chyba kluce {missing}.")

    operator = str(flt["operator"]).upper()
    if operator not in VALID_OPERATORS:
        raise ValueError(f"{prefix}: neplatny operator '{flt['operator']}'.")
    if operator == "IN" and not isinstance(flt["value"], list):
        raise ValueError(f"{prefix}: operator IN vyzaduje zoznam hodnot.")


# ---------------------------------------------------------------------------
# Filter -> SQL WHERE
# ---------------------------------------------------------------------------


def _filter_to_where(flt: dict | list) -> tuple[str, list]:
    """Konvertuje filter na SQL WHERE klauzulu + parametre."""
    if isinstance(flt, list):
        parts = []
        params: list[Any] = []
        for child in flt:
            child_where, child_params = _filter_to_where(child)
            parts.append(f"({child_where})")
            params.extend(child_params)
        return " AND ".join(parts), params

    if not isinstance(flt, dict):
        raise ValueError("Filter musi byt objekt alebo zoznam objektov.")

    if "and" in flt:
        children = flt["and"]
        if not isinstance(children, list) or not children:
            raise ValueError("Filter 'and' musi byt neprazdny zoznam.")
        parts = []
        params: list[Any] = []
        for child in children:
            child_where, child_params = _filter_to_where(child)
            parts.append(f"({child_where})")
            params.extend(child_params)
        return " AND ".join(parts), params

    if "or" in flt:
        children = flt["or"]
        if not isinstance(children, list) or not children:
            raise ValueError("Filter 'or' musi byt neprazdny zoznam.")
        parts = []
        params: list[Any] = []
        for child in children:
            child_where, child_params = _filter_to_where(child)
            parts.append(f"({child_where})")
            params.extend(child_params)
        return " OR ".join(parts), params

    col = flt["column"]
    operator = str(flt["operator"]).upper()
    value = flt["value"]

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
        raise ValueError(f"Neplatny stlpec: {col}")

    if operator == "IN":
        if not isinstance(value, list):
            raise ValueError("Operator IN vyzaduje zoznam hodnot.")
        if not value:
            return "1 = 0", []
        placeholders = ", ".join(["?"] * len(value))
        return f"{col} IN ({placeholders})", value

    return f"{col} {operator} ?", [value]


# ---------------------------------------------------------------------------
# Transformácie
# ---------------------------------------------------------------------------


def _apply_transform(current_value: str, transform: dict) -> str:
    """Aplikuje transform (napr. time_add) na hodnotu."""
    name = transform.get("transform")
    if name == "time_add":
        minutes = transform.get("minutes", 0)
        return _time_add(current_value, minutes)
    raise ValueError(f"Neznamy transform: {name}")


def _time_add(time_str: str, minutes: int) -> str:
    """
    Prida minuty k GTFS casu (HH:MM:SS).
    GTFS podporuje casy > 24:00:00 (napr. 25:30:00).
    """
    parts = time_str.split(":")
    if len(parts) != 3:
        raise ValueError(f"Neplatny format casu: {time_str}")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    total_minutes = h * 60 + m + minutes
    new_h = total_minutes // 60
    new_m = total_minutes % 60
    return f"{new_h:02d}:{new_m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Diff / Preview
# ---------------------------------------------------------------------------


def build_diff_summary(patch: dict) -> dict:
    """
    Pre kazdu operaciu v patchi vytvori before/after preview.
    Vrati human-readable zhrnutie.
    """
    _check_db()
    db_path = get_current_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    summaries: list[dict] = []

    try:
        for i, op in enumerate(patch["operations"]):
            summary = _build_op_summary(conn, op, i)
            summaries.append(summary)
    finally:
        conn.close()

    total_affected = sum(s.get("matched_rows", 0) for s in summaries)
    return {
        "total_operations": len(summaries),
        "total_affected_rows": total_affected,
        "operations": summaries,
    }


def _build_op_summary(conn: sqlite3.Connection, op: dict, idx: int) -> dict:
    """Vytvori zhrnutie jednej operacie."""
    table = op["table"]
    op_type = op["op"]

    if op_type == "insert":
        rows = op.get("rows", [])
        return {
            "index": idx,
            "op": "insert",
            "table": table,
            "rows_to_insert": len(rows),
            "preview": rows[:5],
        }

    where_clause, params = _filter_to_where(op["filter"])

    count_sql = f"SELECT COUNT(*) as cnt FROM {table} WHERE {where_clause}"
    count = conn.execute(count_sql, params).fetchone()["cnt"]

    preview_sql = f"SELECT * FROM {table} WHERE {where_clause} LIMIT 5"
    before_rows = [dict(r) for r in conn.execute(preview_sql, params).fetchall()]

    result: dict[str, Any] = {
        "index": idx,
        "op": op_type,
        "table": table,
        "matched_rows": count,
        "before_preview": before_rows,
    }

    if op_type == "update" and before_rows:
        after_rows = []
        for row in before_rows:
            new_row = dict(row)
            for col, val in op["set"].items():
                if isinstance(val, dict) and "transform" in val:
                    new_row[col] = _apply_transform(str(row.get(col, "")), val)
                else:
                    new_row[col] = val
            after_rows.append(new_row)
        result["after_preview"] = after_rows

    return result


# ---------------------------------------------------------------------------
# Apply (mutacie v transakcii)
# ---------------------------------------------------------------------------


def apply_patch(patch: dict) -> dict:
    """
    Aplikuje patch na SQLite databazu v jednej transakcii (atomic).
    Vrati pocty ovplyvnenych riadkov.
    """
    _check_db()
    db_path = get_current_db()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    affected: dict[str, int] = {}

    try:
        for op in patch["operations"]:
            table = op["table"]
            op_type = op["op"]

            if op_type == "delete":
                rows = _apply_delete(conn, op)
            elif op_type == "update":
                rows = _apply_update(conn, op)
            elif op_type == "insert":
                rows = _apply_insert(conn, op)
            else:
                continue

            affected[table] = affected.get(table, 0) + rows

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"applied": True, "affected_rows": affected}


def _apply_delete(conn: sqlite3.Connection, op: dict) -> int:
    """DELETE operacia."""
    where, params = _filter_to_where(op["filter"])
    sql = f"DELETE FROM {op['table']} WHERE {where}"
    cursor = conn.execute(sql, params)
    return cursor.rowcount


def _apply_update(conn: sqlite3.Connection, op: dict) -> int:
    """UPDATE operacia (vratane transformov ako time_add)."""
    table = op["table"]
    flt = op["filter"]
    set_spec = op["set"]
    where, params = _filter_to_where(flt)

    has_transforms = any(
        isinstance(v, dict) and "transform" in v for v in set_spec.values()
    )

    if not has_transforms:
        set_parts = []
        set_params = []
        for col, val in set_spec.items():
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                raise ValueError(f"Neplatny stlpec: {col}")
            set_parts.append(f"{col} = ?")
            set_params.append(val)
        sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {where}"
        cursor = conn.execute(sql, set_params + params)
        return cursor.rowcount
    else:
        select_sql = f"SELECT rowid, * FROM {table} WHERE {where}"
        rows = conn.execute(select_sql, params).fetchall()
        col_names = [
            desc[0]
            for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description
        ]
        count = 0
        for row in rows:
            rowid = row[0]
            row_dict = {col_names[i]: row[i + 1] for i in range(len(col_names))}

            set_parts = []
            set_params = []
            for col, val in set_spec.items():
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                    raise ValueError(f"Neplatny stlpec: {col}")
                if isinstance(val, dict) and "transform" in val:
                    new_val = _apply_transform(str(row_dict.get(col, "")), val)
                else:
                    new_val = val
                set_parts.append(f"{col} = ?")
                set_params.append(new_val)

            sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE rowid = ?"
            conn.execute(sql, set_params + [rowid])
            count += 1
        return count


def _apply_insert(conn: sqlite3.Connection, op: dict) -> int:
    """INSERT operacia."""
    table = op["table"]
    rows = op["rows"]
    if not rows:
        return 0
    cols = list(rows[0].keys())
    for col in cols:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
            raise ValueError(f"Neplatny stlpec: {col}")
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
    count = 0
    for row in rows:
        values = tuple(row.get(c) for c in cols)
        conn.execute(sql, values)
        count += 1
    return count
