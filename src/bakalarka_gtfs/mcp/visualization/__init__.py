"""
visualization — Interactive map generation for GTFS routes and stops.

Uses Leaflet.js to render stops, route shapes, and highlighted
segments as an HTML widget compatible with LibreChat Artifacts.
"""

from .map_template import get_map_html

__all__ = ["get_map_html"]
