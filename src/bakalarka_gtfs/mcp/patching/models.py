"""
models.py — Data structures and validation definitions for the GTFS patch.
"""

from __future__ import annotations

import json

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
        raise ValueError(f"{prefix}: neplatna tabulka '{op['table']}'. Povolene: {VALID_TABLES}")

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
