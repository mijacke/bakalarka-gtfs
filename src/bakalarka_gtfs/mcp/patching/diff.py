"""
diff.py — Generation of before/after preview logic.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..database import _check_db, get_current_db
from .sql_builder import filter_to_where
from .transforms import apply_transform


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

    where_clause, params = filter_to_where(op["filter"])

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
                    new_row[col] = apply_transform(str(row.get(col, "")), val)
                else:
                    new_row[col] = val
            after_rows.append(new_row)
        result["after_preview"] = after_rows

    return result
