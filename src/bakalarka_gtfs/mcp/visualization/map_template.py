import json


def get_map_html(
    stops: list[dict],
    shapes: list[dict] | None = None,
    route_meta: dict | None = None,
    highlight_from: int | None = None,
    highlight_to: int | None = None,
) -> str:
    """
    Vygeneruje HTML kód pre interaktívnu mapu Leaflet.js

    Args:
        stops: Zoznam slovníkov s kľúčmi 'lat', 'lon', 'name' (a voliteľne 'time').
        shapes: Zoznam slovníkov s kľúčmi 'lat', 'lon' pre tvar trasy.
        route_meta: Metadata o linke — 'route_short_name', 'route_color', 'trip_headsign', 'title'.
        highlight_from: 0-based index zastávky odkiaľ začína hľadaný úsek (ŠTART).
        highlight_to: 0-based index zastávky kde končí hľadaný úsek (CIEĽ).

    Returns:
        HTML string pre LibreChat Artifacts.
    """
    if route_meta is None:
        route_meta = {}

    stops_json = json.dumps(stops, ensure_ascii=False)
    shapes_json = json.dumps(shapes, ensure_ascii=False) if shapes else "[]"
    meta_json = json.dumps(route_meta, ensure_ascii=False)
    hl_from = highlight_from if highlight_from is not None else -1
    hl_to = highlight_to if highlight_to is not None else -1

    route_color = route_meta.get("route_color", "F56200")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>GTFS Mapa</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #f0f4f8; }}
        #map {{ height: 560px; width: 100%; }}
        .map-title {{
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            color: #fff; padding: 10px 16px; font-size: 14px; font-weight: 600;
            display: flex; align-items: center; gap: 10px;
        }}
        .route-badge {{
            background: #{route_color};
            color: #fff; padding: 3px 10px; border-radius: 4px;
            font-weight: 700; font-size: 15px; min-width: 30px; text-align: center;
        }}
        /* —— Menovky zastávok —— */
        .sl {{
            background: rgba(255,255,255,0.93);
            border: 1px solid #94a3b8;
            border-radius: 5px;
            padding: 3px 8px;
            font-size: 12px;
            font-weight: 600;
            color: #1e293b;
            white-space: nowrap;
            box-shadow: 0 1px 5px rgba(0,0,0,0.18);
            line-height: 1.3;
            text-align: center;
        }}
        .sl-start {{
            background: #16a34a;
            color: #fff;
            border: 2px solid #15803d;
            font-size: 13px;
            font-weight: 700;
            padding: 4px 10px;
        }}
        .sl-end {{
            background: #dc2626;
            color: #fff;
            border: 2px solid #b91c1c;
            font-size: 13px;
            font-weight: 700;
            padding: 4px 10px;
        }}
        .sl-terminal {{
            background: #1e293b;
            color: #fff;
            border: 2px solid #475569;
            font-size: 12px;
            font-weight: 700;
            padding: 3px 9px;
        }}
        .sl-outside {{
            background: rgba(255,255,255,0.7);
            color: #94a3b8;
            border: 1px solid #cbd5e1;
            font-size: 11px;
            font-weight: 500;
        }}
        /* —— Popupy —— */
        .pc h3 {{ margin: 0 0 6px; font-size: 14px; color: #1e293b; }}
        .pc .d {{ color: #64748b; font-size: 12px; margin: 2px 0; }}
        .pc .ri {{
            margin-top: 6px; padding: 4px 8px; border-radius: 4px;
            font-weight: 600; font-size: 12px; display: inline-block;
        }}
        .pc .tag {{
            display: inline-block; padding: 2px 8px; border-radius: 3px;
            font-size: 11px; font-weight: 600; margin-top: 4px;
        }}
        .pc .tag-start {{ background: #dcfce7; color: #15803d; }}
        .pc .tag-end {{ background: #fef2f2; color: #dc2626; }}
    </style>
</head>
<body>
    <div class="map-title">
        <span class="route-badge">{route_meta.get("route_short_name", "")}</span>
        <span>{route_meta.get("title", "GTFS Mapa")}</span>
    </div>
    <div id="map"></div>
    <script>
        const stops = {stops_json};
        const shapes = {shapes_json};
        const meta = {meta_json};
        const hlFrom = {hl_from};
        const hlTo = {hl_to};
        const hasHighlight = hlFrom >= 0 && hlTo >= 0;
        const routeColor = '#' + (meta.route_color || 'F56200');

        const map = L.map('map');
        const allBounds = [];

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OSM</a>'
        }}).addTo(map);

        // ======= TRASA =======
        if (shapes && shapes.length > 0) {{
            const ll = shapes.map(p => [p.lat, p.lon]);
            L.polyline(ll, {{color: routeColor, weight: 5, opacity: 0.85}}).addTo(map);
            ll.forEach(c => allBounds.push(c));
        }} else if (stops && stops.length > 1) {{
            if (hasHighlight) {{
                // Pred hladanym usekom — cierna plna ciara
                if (hlFrom > 0) {{
                    const pre = stops.slice(0, hlFrom + 1).map(s => [s.lat, s.lon]);
                    L.polyline(pre, {{color: '#1e293b', weight: 4, opacity: 0.8}}).addTo(map);
                }}
                // Hladany usek — hruba plna ciara vo farbe linky
                const seg = stops.slice(hlFrom, hlTo + 1).map(s => [s.lat, s.lon]);
                L.polyline(seg, {{color: routeColor, weight: 6, opacity: 0.9}}).addTo(map);
                // Za hladanym usekom — cierna plna ciara
                if (hlTo < stops.length - 1) {{
                    const post = stops.slice(hlTo, stops.length).map(s => [s.lat, s.lon]);
                    L.polyline(post, {{color: '#1e293b', weight: 4, opacity: 0.8}}).addTo(map);
                }}
            }} else {{
                // Bez highlight — celá trasa vo farbe linky, ciarkovaná
                const ll = stops.map(s => [s.lat, s.lon]);
                L.polyline(ll, {{color: routeColor, weight: 4, opacity: 0.7, dashArray: '10, 7'}}).addTo(map);
            }}
        }}

        // ======= ZASTÁVKY =======
        const routeName = meta.route_short_name ? ('Linka ' + meta.route_short_name) : '';
        const headsign = meta.trip_headsign || '';
        const lightweight = stops.length > 30;  // Pre veľa zastávok — bez menoviek

        if (stops && stops.length > 0) {{
            stops.forEach((stop, i) => {{
                allBounds.push([stop.lat, stop.lon]);
                const num = i + 1;
                const isFirst = i === 0;
                const isLast = i === stops.length - 1;
                const isStart = hasHighlight && i === hlFrom;
                const isEnd = hasHighlight && i === hlTo;
                const inSegment = !hasHighlight || (i >= hlFrom && i <= hlTo);
                const timeStr = stop.time || '';

                // Popup — vždy (aj lightweight)
                let p = '<div class="pc">';
                p += '<h3>' + (lightweight ? '' : num + '. ') + stop.name + '</h3>';
                if (timeStr) p += '<div class="d">🕐 Čas: ' + timeStr + '</div>';
                if (!lightweight) p += '<div class="d">📍 Zastávka č. ' + num + ' z ' + stops.length + '</div>';
                if (isStart) p += '<div class="tag tag-start">🟢 ŠTART — odtiaľ hľadáte</div>';
                if (isEnd) p += '<div class="tag tag-end">🔴 CIEĽ — sem hľadáte</div>';
                if (routeName) {{
                    p += '<div class="ri" style="background:' + routeColor + ';color:#fff;">';
                    p += '🚋 ' + routeName;
                    if (headsign) p += ' → ' + headsign;
                    p += '</div>';
                }}
                p += '</div>';

                // Farba a veľkosť markera
                let radius, fillColor, borderColor, borderW;
                let labelClass = 'sl';

                if (isStart) {{
                    radius = 11; fillColor = '#16a34a'; borderColor = '#fff'; borderW = 3;
                    labelClass = 'sl sl-start';
                }} else if (isEnd) {{
                    radius = 11; fillColor = '#dc2626'; borderColor = '#fff'; borderW = 3;
                    labelClass = 'sl sl-end';
                }} else if (!lightweight && (isFirst || isLast)) {{
                    radius = 9; fillColor = '#1e293b'; borderColor = '#fff'; borderW = 3;
                    labelClass = 'sl sl-terminal';
                }} else if (inSegment) {{
                    radius = lightweight ? 5 : 7;
                    fillColor = lightweight ? '#F56200' : routeColor;
                    borderColor = '#fff'; borderW = lightweight ? 1 : 2;
                }} else {{
                    radius = 7; fillColor = '#1e293b'; borderColor = '#fff'; borderW = 2;
                    labelClass = 'sl sl-terminal';
                }}

                L.circleMarker([stop.lat, stop.lon], {{
                    radius: radius, fillColor: fillColor, color: borderColor,
                    weight: borderW, opacity: 1, fillOpacity: 0.9
                }}).bindPopup(p).addTo(map);

                // Label text — IBA pre málo zastávok (route view)
                if (!lightweight) {{
                    let labelText = num + '. ' + stop.name;
                    if (isStart) labelText = labelText + ' — ŠTART';
                    if (isEnd) labelText = labelText + ' — CIEĽ';

                    L.marker([stop.lat, stop.lon], {{
                        icon: L.divIcon({{
                            className: labelClass,
                            html: labelText,
                            iconSize: null,
                            iconAnchor: [-14, 12]
                        }})
                    }}).addTo(map);
                }}
            }});
        }}

        // ======= ZOOM =======
        if (allBounds.length > 0) {{
            map.fitBounds(allBounds, {{ padding: [50, 50] }});
        }} else {{
            map.setView([48.148598, 17.107748], 12);
        }}
    </script>
</body>
</html>"""
    return html
