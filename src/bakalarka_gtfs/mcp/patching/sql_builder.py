"""
sql_builder.py — Logic to convert Patch JSON filters into SQLite WHERE clauses.
"""

from __future__ import annotations

import re
from typing import Any


def filter_to_where(flt: dict | list) -> tuple[str, list]:
    """Konvertuje filter na SQL WHERE klauzulu + parametre."""
    if isinstance(flt, list):
        parts = []
        params: list[Any] = []
        for child in flt:
            child_where, child_params = filter_to_where(child)
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
            child_where, child_params = filter_to_where(child)
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
            child_where, child_params = filter_to_where(child)
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
