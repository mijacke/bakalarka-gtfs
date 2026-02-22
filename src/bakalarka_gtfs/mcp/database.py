"""
database.py — SQLite database for GTFS data (singleton — one current.db).

Functions:
  - ensure_loaded(feed_path)     — load GTFS if DB doesn't exist yet
  - get_current_db()             — path to active .db
  - run_query(sql)               — read-only SELECT, default limit 500 rows
  - export_to_gtfs(output_path)  — dump to CSV -> ZIP
  - reset_db()                   — delete DB (for new chat / fresh import)
"""

from __future__ import annotations

import csv
import io
import os
import sqlite3
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Cesty — singleton DB
# ---------------------------------------------------------------------------

# APP_ROOT env var: explicitne nastaveny v Docker (WORKDIR /app).
# Fallback: 3 urovne nad tymto suborom (src/bakalarka_gtfs/mcp -> project root).
PROJECT_ROOT = (
    Path(os.environ.get("APP_ROOT", "")) if os.environ.get("APP_ROOT") else Path(__file__).resolve().parents[3]
)
WORK_DIR = PROJECT_ROOT / ".work" / "datasets"
DB_PATH = WORK_DIR / "current.db"

# Mapovanie GTFS .txt -> SQLite tabulka
GTFS_TABLES: dict[str, str] = {
    "stops.txt": "stops",
    "routes.txt": "routes",
    "calendar.txt": "calendar",
    "trips.txt": "trips",
    "stop_times.txt": "stop_times",
    "shapes.txt": "shapes",
}


def get_current_db() -> Path:
    """Vrati cestu k aktualnej SQLite databaze."""
    return DB_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS stops (
    stop_id       TEXT PRIMARY KEY,
    stop_name     TEXT NOT NULL,
    stop_lat      REAL NOT NULL,
    stop_lon      REAL NOT NULL,
    stop_code     TEXT,
    zone_id       TEXT,
    location_type INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS routes (
    route_id         TEXT PRIMARY KEY,
    agency_id        TEXT,
    route_short_name TEXT,
    route_long_name  TEXT,
    route_type       INTEGER NOT NULL,
    route_color      TEXT
);

CREATE TABLE IF NOT EXISTS calendar (
    service_id TEXT PRIMARY KEY,
    monday     INTEGER,
    tuesday    INTEGER,
    wednesday  INTEGER,
    thursday   INTEGER,
    friday     INTEGER,
    saturday   INTEGER,
    sunday     INTEGER,
    start_date TEXT,
    end_date   TEXT
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id       TEXT PRIMARY KEY,
    route_id      TEXT NOT NULL REFERENCES routes(route_id),
    service_id    TEXT NOT NULL REFERENCES calendar(service_id),
    trip_headsign TEXT,
    direction_id  INTEGER,
    shape_id      TEXT
);

CREATE TABLE IF NOT EXISTS stop_times (
    trip_id        TEXT    NOT NULL REFERENCES trips(trip_id),
    arrival_time   TEXT    NOT NULL,
    departure_time TEXT    NOT NULL,
    stop_id        TEXT    NOT NULL REFERENCES stops(stop_id),
    stop_sequence  INTEGER NOT NULL,
    PRIMARY KEY (trip_id, stop_sequence)
);

CREATE TABLE IF NOT EXISTS shapes (
    shape_id       TEXT NOT NULL,
    shape_pt_lat   REAL NOT NULL,
    shape_pt_lon   REAL NOT NULL,
    shape_pt_sequence INTEGER NOT NULL,
    shape_dist_traveled REAL,
    PRIMARY KEY (shape_id, shape_pt_sequence)
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    record_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    old_data JSON,
    new_data JSON
);
"""

# Stlpce, ktore importujeme z CSV pre kazdu tabulku
_TABLE_COLUMNS: dict[str, list[str]] = {
    "stops": ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_code", "zone_id", "location_type"],
    "routes": ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color"],
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
    "trips": ["trip_id", "route_id", "service_id", "trip_headsign", "direction_id", "shape_id"],
    "stop_times": ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
    "shapes": ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled"],
}


def _create_audit_triggers(conn: sqlite3.Connection) -> None:
    """Dynamicky vytvori audit triggery pre vsetky tabulky."""
    for table, cols in _TABLE_COLUMNS.items():
        # Urcenie identifikatora pre zaznam (PK)
        if table == "stop_times":
            record_id_expr = "NEW.trip_id || '-' || NEW.stop_sequence"
            old_record_id_expr = "OLD.trip_id || '-' || OLD.stop_sequence"
        elif table == "shapes":
            record_id_expr = "NEW.shape_id || '-' || NEW.shape_pt_sequence"
            old_record_id_expr = "OLD.shape_id || '-' || OLD.shape_pt_sequence"
        else:
            pk_col = cols[0]
            record_id_expr = f"NEW.{pk_col}"
            old_record_id_expr = f"OLD.{pk_col}"

        # JSON object expression pre old_data a new_data
        new_json_args = ", ".join(f"'{c}', NEW.{c}" for c in cols)
        old_json_args = ", ".join(f"'{c}', OLD.{c}" for c in cols)

        new_json_expr = f"json_object({new_json_args})" if new_json_args else "NULL"
        old_json_expr = f"json_object({old_json_args})" if old_json_args else "NULL"

        triggers = [
            f"""
            CREATE TRIGGER IF NOT EXISTS audit_{table}_insert
            AFTER INSERT ON {table}
            BEGIN
                INSERT INTO audit_log (table_name, operation, record_id, old_data, new_data)
                VALUES ('{table}', 'INSERT', {record_id_expr}, NULL, {new_json_expr});
            END;
            """,
            f"""
            CREATE TRIGGER IF NOT EXISTS audit_{table}_update
            AFTER UPDATE ON {table}
            BEGIN
                INSERT INTO audit_log (table_name, operation, record_id, old_data, new_data)
                VALUES ('{table}', 'UPDATE', {record_id_expr}, {old_json_expr}, {new_json_expr});
            END;
            """,
            f"""
            CREATE TRIGGER IF NOT EXISTS audit_{table}_delete
            AFTER DELETE ON {table}
            BEGIN
                INSERT INTO audit_log (table_name, operation, record_id, old_data, new_data)
                VALUES ('{table}', 'DELETE', {old_record_id_expr}, {old_json_expr}, NULL);
            END;
            """,
        ]
        for t_sql in triggers:
            conn.executescript(t_sql)


def create_schema(conn: sqlite3.Connection) -> None:
    """Vytvori 5 GTFS tabuliek, audit tabulku a vsetky triggery (idempotentne)."""
    conn.executescript(_SCHEMA_SQL)
    _create_audit_triggers(conn)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def _do_import(feed: Path) -> dict[str, int]:
    """Importuje GTFS CSV subory do current.db. Vrati pocty riadkov."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    create_schema(conn)

    tables_info: dict[str, int] = {}

    for txt_file, table in GTFS_TABLES.items():
        csv_path = feed / txt_file
        if not csv_path.exists():
            tables_info[table] = 0
            continue

        cols = _TABLE_COLUMNS[table]
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

        count = 0
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            batch: list[tuple] = []
            for row in reader:
                values = tuple(row.get(c, None) or None for c in cols)
                batch.append(values)
                count += 1
                if len(batch) >= 5000:
                    conn.executemany(sql, batch)
                    batch.clear()
            if batch:
                conn.executemany(sql, batch)

        tables_info[table] = count

    conn.commit()
    conn.close()
    return tables_info


def _find_gtfs_root(base: Path, max_depth: int = 3) -> Path | None:
    """
    Hlada GTFS root (adresar so stops.txt) v rozbalenom ZIP.
    Podporuje rozne struktury:
      - stops.txt priamo v roote
      - stops.txt v jednom podpriecinku (napr. feed/)
      - stops.txt hlbsie vnorene (max_depth urovni)
    """
    if (base / "stops.txt").exists():
        return base

    if max_depth <= 0:
        return None

    for child in sorted(base.iterdir()):
        if child.is_dir() and not child.name.startswith((".", "__")):
            found = _find_gtfs_root(child, max_depth - 1)
            if found is not None:
                return found

    return None


def ensure_loaded(feed_path: str, force: bool = False) -> dict:
    """
    Nacita GTFS data z adresara alebo ZIP do current.db.

    Ak DB uz existuje a force=False, vrati info o existujucej DB
    bez re-importu (rychle — pre opakovane volania v tom istom chate).

    Args:
        feed_path: Cesta k GTFS adresaru alebo .zip
        force: Ak True, vymaze existujucu DB a re-importuje

    Returns:
        dict s tables (pocty riadkov) a status.
    """
    feed = Path(feed_path)

    # Resolve relativnu cestu
    if not feed.is_absolute():
        feed = PROJECT_ROOT / feed

    # Ak je ZIP, rozbalime a najdeme GTFS subory
    if feed.suffix.lower() == ".zip":
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="gtfs_"))
        with zipfile.ZipFile(feed) as zf:
            zf.extractall(tmp)

        # Hladaj stops.txt — moze byt priamo v tmp, alebo v podpriecinku
        feed = _find_gtfs_root(tmp)
        if feed is None:
            raise FileNotFoundError(
                f"ZIP subor '{feed_path}' neobsahuje platne GTFS data "
                f"(chyba stops.txt). Skontroluj strukturu ZIP archivu."
            )

    if not feed.exists() or not (feed / "stops.txt").exists():
        raise FileNotFoundError(f"GTFS adresar '{feed}' neexistuje alebo neobsahuje stops.txt.")

    # Ak DB existuje a nechceme force -> vratime existujuce info
    if DB_PATH.exists() and not force:
        tables_info = _get_table_counts()
        return {
            "status": "already_loaded",
            "message": "Databaza uz existuje, pouzivam existujucu. Pouzi force=true pre re-import.",
            "tables": tables_info,
            "db_path": str(DB_PATH),
        }

    # Force alebo prvy import
    if DB_PATH.exists():
        DB_PATH.unlink()

    tables_info = _do_import(feed)
    return {
        "status": "imported",
        "message": "GTFS data uspesne nacitane do databazy.",
        "tables": tables_info,
        "db_path": str(DB_PATH),
    }


def reset_db() -> dict:
    """Vymaze aktualnu databazu (pre fresh import)."""
    if DB_PATH.exists():
        DB_PATH.unlink()
        return {"status": "reset", "message": "Databaza vymazana. Pouzi gtfs_load pre novy import."}
    return {"status": "no_db", "message": "Ziadna databaza neexistovala."}


def _get_table_counts() -> dict[str, int]:
    """Vrati pocty riadkov v existujucej DB."""
    conn = sqlite3.connect(str(DB_PATH))
    counts: dict[str, int] = {}
    for table in GTFS_TABLES.values():
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0]
        except Exception:
            counts[table] = 0
    conn.close()
    return counts


def _check_db() -> None:
    """Kontrola, ze DB existuje."""
    if not DB_PATH.exists():
        raise FileNotFoundError("Databaza neexistuje. Najprv zavolaj gtfs_load('data/gtfs_latest') pre nacitanie dat.")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH"}


def run_query(sql: str, limit: int = 500) -> list[dict]:
    """
    Vykona read-only SELECT dotaz nad aktualnou DB.
    Ak dotaz nema LIMIT, doplni sa predvoleny `limit`.
    """
    _check_db()

    sql_upper = sql.strip().upper()
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in sql_upper.split():
            raise ValueError(f"Zakazany SQL prikaz: {kw}. Len SELECT je povoleny.")

    if not sql_upper.startswith("SELECT"):
        raise ValueError("Len SELECT dotazy su povolene.")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip("; ") + f" LIMIT {limit}"
        cursor = conn.execute(sql)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

_EXPORT_COLUMNS: dict[str, list[str]] = _TABLE_COLUMNS.copy()


def export_to_gtfs(output_path: str) -> str:
    """Exportuje aktualnu DB do GTFS ZIP suboru."""
    _check_db()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for txt_file, table in GTFS_TABLES.items():
            cols = _EXPORT_COLUMNS[table]
            cursor = conn.execute(f"SELECT {', '.join(cols)} FROM {table}")
            rows = cursor.fetchall()

            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer, lineterminator="\n")
            writer.writerow(cols)
            for row in rows:
                values = [row[c] if row[c] is not None else "" for c in cols]
                writer.writerow(values)
            zf.writestr(txt_file, buffer.getvalue())

    conn.close()
    return str(out)
