"""
transforms.py — Data transformation utilities for patching GTFS data.
"""

from __future__ import annotations


def apply_transform(current_value: str, transform: dict) -> str:
    """Aplikuje transform (napr. time_add) na hodnotu."""
    name = transform.get("transform")
    if name == "time_add":
        minutes = transform.get("minutes", 0)
        return time_add(current_value, minutes)
    raise ValueError(f"Neznamy transform: {name}")


def time_add(time_str: str, minutes: int) -> str:
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


def gtfs_time_to_seconds(time_str: str) -> int:
    """Prevedie GTFS cas HH:MM:SS (HH moze byt >24) na sekundy."""
    parts = time_str.split(":")
    if len(parts) != 3:
        raise ValueError(f"'{time_str}' (ocakavany format HH:MM:SS)")

    h, m, s = (int(parts[0]), int(parts[1]), int(parts[2]))
    if m < 0 or m > 59 or s < 0 or s > 59 or h < 0:
        raise ValueError(f"'{time_str}' (neplatne hodnoty casu)")
    return h * 3600 + m * 60 + s
