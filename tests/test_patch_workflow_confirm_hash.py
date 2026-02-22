from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import patch


def _install_mcp_stub() -> None:
    if "mcp.server.fastmcp" in sys.modules:
        return

    mcp_module = types.ModuleType("mcp")
    server_module = types.ModuleType("mcp.server")
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")

    class _FastMCPStub:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self):
            def decorator(fn):
                return fn

            return decorator

        def run(self, *args, **kwargs):
            return None

    fastmcp_module.FastMCP = _FastMCPStub
    mcp_module.server = server_module
    server_module.fastmcp = fastmcp_module
    sys.modules["mcp"] = mcp_module
    sys.modules["mcp.server"] = server_module
    sys.modules["mcp.server.fastmcp"] = fastmcp_module


_install_mcp_stub()

from bakalarka_gtfs.mcp import server as st  # noqa: E402 — must come after MCP stub


class TestPatchWorkflowConfirmHash(unittest.TestCase):
    def setUp(self) -> None:
        st._PATCH_STATES.clear()

    def tearDown(self) -> None:
        st._PATCH_STATES.clear()

    def test_apply_uses_confirmed_proposed_patch_when_payload_differs(self) -> None:
        proposed_patch = {
            "operations": [
                {
                    "op": "update",
                    "table": "stop_times",
                    "filter": {"column": "trip_id", "operator": "=", "value": "T1"},
                    "set": {"arrival_time": {"transform": "time_add", "minutes": 5}},
                }
            ]
        }
        different_apply_patch = {
            "operations": [
                {
                    "op": "update",
                    "table": "stop_times",
                    "filter": {"column": "trip_id", "operator": "=", "value": "T1"},
                    "set": {"arrival_time": {"transform": "time_add", "minutes": 7}},
                }
            ]
        }
        expected_hash = st._patch_hash(proposed_patch)

        with (
            patch.object(
                st,
                "parse_patch",
                side_effect=[proposed_patch, proposed_patch, different_apply_patch],
            ),
            patch.object(
                st,
                "build_diff_summary",
                return_value={"total_operations": 1, "total_affected_rows": 1, "operations": []},
            ),
            patch.object(st, "validate_patch", return_value={"valid": True, "errors": [], "warnings": []}),
            patch.object(
                st,
                "apply_patch",
                return_value={"applied": True, "affected_rows": {"stop_times": 1}},
            ) as apply_mock,
        ):
            propose = json.loads(st.gtfs_propose_patch('{"operations": []}'))
            self.assertEqual(propose["patch_hash"], expected_hash)

            validate = json.loads(st.gtfs_validate_patch('{"operations": []}'))
            self.assertTrue(validate["valid"])
            self.assertEqual(validate["patch_hash"], expected_hash)

            confirm_message = f"/confirm {expected_hash}"
            confirm_signature = st._sign_confirmation_message(confirm_message)
            applied = json.loads(
                st.gtfs_apply_patch(
                    '{"operations": [{"op":"update"}]}',
                    confirm_message,
                    confirm_signature,
                )
            )

        self.assertTrue(applied["applied"])
        self.assertEqual(applied["patch_hash"], expected_hash)
        apply_mock.assert_called_once_with(proposed_patch)
        self.assertNotIn(expected_hash, st._PATCH_STATES)


if __name__ == "__main__":
    unittest.main()
