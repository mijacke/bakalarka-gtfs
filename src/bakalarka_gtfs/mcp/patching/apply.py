"""
apply.py — DB Mutations and Patch Application logic.
"""

from __future__ import annotations

import re
import sqlite3

from ..database import _check_db, get_current_db
from .sql_builder import filter_to_where
from .transforms import apply_transform


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
    where, params = filter_to_where(op["filter"])
    sql = f"DELETE FROM {op['table']} WHERE {where}"
    cursor = conn.execute(sql, params)
    return cursor.rowcount


def _apply_update(conn: sqlite3.Connection, op: dict) -> int:
    """UPDATE operacia (vratane transformov ako time_add)."""
    table = op["table"]
    flt = op["filter"]
    set_spec = op["set"]
    where, params = filter_to_where(flt)

    has_transforms = any(isinstance(v, dict) and "transform" in v for v in set_spec.values())

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
        col_names = [desc[0] for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
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
                    new_val = apply_transform(str(row_dict.get(col, "")), val)
                else:
                    new_val = val
                set_parts.append(f"{col} = ?")
                set_params.append(new_val)

            sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE rowid = ?"
            conn.execute(sql, [*set_params, rowid])
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
