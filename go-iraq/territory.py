import json
from pathlib import Path

geometry = json.loads((Path(__file__).parent / "web/iraq.json").read_text())
polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]


def in_ring(lon, lat, ring):
    inside = False
    for (x, y), (u, v) in zip(ring, ring[1:]):
        if (y > lat) != (v > lat) and lon < (u - x) * (lat - y) / (v - y) + x:
            inside = not inside
    return inside


def inside_iraq(lon, lat):
    return any(in_ring(lon, lat, rings[0]) and not any(in_ring(lon, lat, hole) for hole in rings[1:])
               for rings in polygons)
