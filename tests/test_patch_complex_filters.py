from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bakalarka_gtfs.mcp import database as db
from bakalarka_gtfs.mcp.patching.operations import build_diff_summary
from bakalarka_gtfs.mcp.patching.validation import validate_patch


class TestPatchComplexFilters(unittest.TestCase):
    def test_propose_and_validate_with_and_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            feed_dir = tmp / "feed"
            feed_dir.mkdir(parents=True, exist_ok=True)

            self._write_csv(
                feed_dir / "stops.txt",
                ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_code", "zone_id", "location_type"],
                [
                    ["STOP_A", "A", "48.1", "17.1", "", "", "0"],
                    ["STOP_B", "B", "48.2", "17.2", "", "", "0"],
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
                [
                    ["SAT", "0", "0", "0", "0", "0", "1", "0", "20260101", "20261231"],
                    ["WD", "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"],
                ],
            )
            self._write_csv(
                feed_dir / "trips.txt",
                ["trip_id", "route_id", "service_id", "trip_headsign", "direction_id"],
                [
                    ["T_SAT", "R1", "SAT", "Sobota", "0"],
                    ["T_WD", "R1", "WD", "Pracovny den", "0"],
                ],
            )
            self._write_csv(
                feed_dir / "stop_times.txt",
                ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
                [
                    ["T_SAT", "08:00:00", "08:00:00", "STOP_A", "1"],
                    ["T_SAT", "12:15:00", "12:15:00", "STOP_B", "2"],
                    ["T_SAT", "16:30:00", "16:30:00", "STOP_A", "3"],
                    ["T_WD", "08:30:00", "08:30:00", "STOP_A", "1"],
                ],
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
                            "filter": {
                                "and": [
                                    {"column": "trip_id", "operator": "IN", "value": ["T_SAT"]},
                                    {"column": "arrival_time", "operator": ">=", "value": "08:00:00"},
                                    {"column": "arrival_time", "operator": "<=", "value": "16:00:00"},
                                    {"column": "departure_time", "operator": ">=", "value": "08:00:00"},
                                    {"column": "departure_time", "operator": "<=", "value": "16:00:00"},
                                ]
                            },
                            "set": {
                                "arrival_time": {"transform": "time_add", "minutes": 7},
                                "departure_time": {"transform": "time_add", "minutes": 7},
                            },
                        }
                    ]
                }

                summary = build_diff_summary(patch_payload)
                self.assertEqual(summary["total_operations"], 1)
                self.assertEqual(summary["total_affected_rows"], 2)
                self.assertEqual(summary["operations"][0]["matched_rows"], 2)

                result = validate_patch(patch_payload)
                self.assertTrue(result["valid"], result)
                self.assertEqual(result["errors"], [])

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
