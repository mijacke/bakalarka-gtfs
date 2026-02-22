from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bakalarka_gtfs.mcp import database as db
from bakalarka_gtfs.mcp.patching.validation import validate_patch


class TestValidationFullScan(unittest.TestCase):
    def test_time_ordering_checks_rows_beyond_100(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            feed_dir = tmp / "feed"
            feed_dir.mkdir(parents=True, exist_ok=True)

            self._write_csv(
                feed_dir / "stops.txt",
                ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_code", "zone_id", "location_type"],
                [["STOP_A", "A", "48.1", "17.1", "", "", "0"]],
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
                [["S1", "1", "1", "1", "1", "1", "1", "1", "20260101", "20261231"]],
            )
            self._write_csv(
                feed_dir / "trips.txt",
                ["trip_id", "route_id", "service_id", "trip_headsign", "direction_id"],
                [["T1", "R1", "S1", "Test", "0"]],
            )

            stop_times_rows = []
            for i in range(1, 151):
                arrival = "08:00:00"
                departure = "08:10:00"
                if i == 130:
                    arrival = "08:20:00"
                stop_times_rows.append(["T1", arrival, departure, "STOP_A", str(i)])
            self._write_csv(
                feed_dir / "stop_times.txt",
                ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
                stop_times_rows,
            )

            work_dir = tmp / "work"
            db_path = work_dir / "current.db"

            with patch.object(db, "WORK_DIR", work_dir), patch.object(db, "DB_PATH", db_path):
                db.ensure_loaded(str(feed_dir), force=True)
                patch_payload = {
                    "operations": [
                        {
                            "op": "update",
                            "table": "stop_times",
                            "filter": {"column": "trip_id", "operator": "=", "value": "T1"},
                            "set": {"arrival_time": {"transform": "time_add", "minutes": 5}},
                        }
                    ]
                }

                result = validate_patch(patch_payload)
                self.assertFalse(result["valid"])
                self.assertTrue(
                    any("arrival_time" in error and "departure_time" in error for error in result["errors"])
                )

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
