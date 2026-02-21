import sys
from server_mcp_gtfs.server.server_tools import gtfs_show_map
from server_mcp_gtfs.databaza.databaza import current_db

try:
    res = gtfs_show_map(route_id="some_missing_route")
    print(res[:200])
except Exception as e:
    print(e)
