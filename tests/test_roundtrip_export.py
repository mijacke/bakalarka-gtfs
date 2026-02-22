from __future__ import annotations

import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from bakalarka_gtfs.mcp import database as db


class TestGtfsRoundtripExport(unittest.TestCase):
    def test_import_export_reimport_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            feed_dir = tmp / "feed"
            feed_dir.mkdir(parents=True, exist_ok=True)

            self._write_csv(
                feed_dir / "stops.txt",
                ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_code", "zone_id", "location_type"],
                [
                    ["STOP_A", 'Prievoz, "most"', "48.1500", "17.1100", "A", "100", "0"],
                    ["STOP_B", "Opletalova, VW5", "48.1600", "17.1200", "B", "100", "0"],
                ],
            )
            self._write_csv(
                feed_dir / "routes.txt",
                ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color"],
                [["R1", "A1", "1", "Linka 1", "3", "FFFFFF"]],
            )
            self._write_csv(
                feed_dir / "calendar.txt",
                [
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
                [["S1", "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"]],
            )
            self._write_csv(
                feed_dir / "trips.txt",
                ["trip_id", "route_id", "service_id", "trip_headsign", "direction_id"],
                [["T1", "R1", "S1", "Opletalova, VW5", "0"]],
            )
            self._write_csv(
                feed_dir / "stop_times.txt",
                ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
                [
                    ["T1", "08:00:00", "08:00:00", "STOP_A", "1"],
                    ["T1", "08:05:00", "08:05:00", "STOP_B", "2"],
                ],
            )

            work_dir = tmp / "work"
            db_path = work_dir / "current.db"
            export_path = tmp / "roundtrip.zip"

            with patch.object(db, "WORK_DIR", work_dir), patch.object(db, "DB_PATH", db_path):
                first = db.ensure_loaded(str(feed_dir), force=True)
                self.assertEqual(first["status"], "imported")
                self.assertEqual(first["tables"]["stops"], 2)

                exported = db.export_to_gtfs(str(export_path))
                self.assertTrue(Path(exported).exists())

                with zipfile.ZipFile(exported) as zf:
                    stops_raw = zf.read("stops.txt").decode("utf-8")
                parsed_rows = list(csv.DictReader(io.StringIO(stops_raw)))
                self.assertEqual(parsed_rows[0]["stop_name"], 'Prievoz, "most"')

                second = db.ensure_loaded(exported, force=True)
                self.assertEqual(second["status"], "imported")
                self.assertEqual(second["tables"]["stops"], 2)

                rows = db.run_query("SELECT stop_id, stop_name FROM stops WHERE stop_id = 'STOP_A'")
                self.assertEqual(rows[0]["stop_name"], 'Prievoz, "most"')

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
