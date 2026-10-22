"""Build aggregate study locations and public GIS overlays from cited services.

Requires pyproj (`python -m pip install pyproj`). Individual tortoise coordinates
remain in memory and are never written to this project.
"""

import csv
import io
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)
BOUNDS = "-115.70,35.30,-114.80,35.90"
WEST, SOUTH, EAST, NORTH = -115.70, 35.30, -114.80, 35.90
SCIENCEBASE = "https://www.sciencebase.gov/catalog/item/5e38914ce4b0a79317df572d?format=json"
CENSUS = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer"
BLM = "https://gis.blm.gov/caarcgis/rest/services/RenewableEnergy/BLM_CA_Renewable_Energy_Projects/FeatureServer/0"


def get_json(url):
    with urlopen(url, timeout=45) as response:
        return json.load(response)


def query(url, fields):
    parameters = {
        "where": "1=1", "geometry": BOUNDS, "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": fields, "outSR": "4326", "returnGeometry": "true", "f": "geojson",
    }
    result = get_json(url + "/query?" + urlencode(parameters))
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def write(name, features):
    path = OUT / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"{path.relative_to(ROOT)}: {len(features)} features, {path.stat().st_size} bytes")


def simplify_line(points, tolerance_degrees=0.00009):
    """Douglas-Peucker, about 10 m north-south at this latitude."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    best_index, best_distance = 0, 0
    for index, point in enumerate(points[1:-1], 1):
        t = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2)) if length2 else 0
        distance = ((point[0] - start[0] - t * dx) ** 2 + (point[1] - start[1] - t * dy) ** 2) ** 0.5
        if distance > best_distance:
            best_index, best_distance = index, distance
    if best_distance <= tolerance_degrees:
        return [start, end]
    return simplify_line(points[:best_index + 1], tolerance_degrees)[:-1] + simplify_line(points[best_index:], tolerance_degrees)


def clip_segment(start, end):
    """Liang–Barsky clip of a line segment to the atlas query envelope."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    low, high = 0.0, 1.0
    for p, q in ((-dx, start[0] - WEST), (dx, EAST - start[0]),
                 (-dy, start[1] - SOUTH), (dy, NORTH - start[1])):
        if p == 0:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                low = max(low, t)
            else:
                high = min(high, t)
            if low > high:
                return None
    return ([start[0] + low * dx, start[1] + low * dy],
            [start[0] + high * dx, start[1] + high * dy])


def clip_line(points):
    pieces, current = [], []
    for start, end in zip(points, points[1:]):
        clipped = clip_segment(start, end)
        if clipped is None:
            if len(current) > 1:
                pieces.append(current)
            current = []
            continue
        first, last = clipped
        if current and abs(current[-1][0] - first[0]) + abs(current[-1][1] - first[1]) < 1e-8:
            current.append(last)
        else:
            if len(current) > 1:
                pieces.append(current)
            current = [first, last]
    if len(current) > 1:
        pieces.append(current)
    return [simplify_line(piece) for piece in pieces]


def clip_feature(feature):
    pieces = clip_line(feature["geometry"]["coordinates"])
    if not pieces:
        return False
    feature["geometry"] = {"type": "LineString", "coordinates": pieces[0]} if len(pieces) == 1 else {
        "type": "MultiLineString", "coordinates": pieces,
    }
    return True


release = get_json(SCIENCEBASE)
csv_url = next(item["downloadUri"] for item in release["files"] if item["name"].endswith(".csv"))
with urlopen(csv_url, timeout=45) as response:
    rows = list(csv.DictReader(io.StringIO(response.read().decode("utf-8-sig"))))
assert len(rows) == 299, "USGS record count changed; review before rebuilding"
locations = defaultdict(list)
for row in rows:
    locations[row["Plot"]].append((float(row["UTMx"]), float(row["UTMy"])))
assert len(locations) == 11

transform = Transformer.from_crs("EPSG:26911", "EPSG:4326", always_xy=True)
sites = []
for name, coords in sorted(locations.items()):
    east = sum(x for x, _ in coords) / len(coords)
    north = sum(y for _, y in coords) / len(coords)
    lon, lat = transform.transform(east, north)
    sites.append({
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
        "properties": {"name": name, "n": len(coords), "kind": "broader-area" if name == "PiuteValley" else "plot-centroid",
                       "method": "mean of individual NAD83 / UTM zone 11N coordinates; not a plot boundary"},
    })
write("study-sites.geojson", sites)

roads = query(CENSUS + "/2", "NAME,BASENAME,MTFCC")["features"]
roads = [f for f in roads if f["properties"].get("NAME") in ("I- 15", "Mojave Fwy") and clip_feature(f)]
assert roads, "I-15 feature selection returned no lines"
for feature in roads:
    feature["properties"] = {"name": "I-15", "source_name": feature["properties"]["NAME"]}
write("interstate-15.geojson", roads)

rail = query(CENSUS + "/9", "NAME,BASENAME,MTFCC")["features"]
rail = [f for f in rail if f["properties"].get("MTFCC") == "R1011" and clip_feature(f)]
for feature in rail:
    feature["properties"] = {"name": feature["properties"].get("NAME") or "Railway (unnamed in TIGER)"}
write("railways.geojson", rail)

solar = query(BLM, "ProjectName,Commodity,Disposition,ProjectType,EffectiveDate,DataSource")["features"]
solar = [f for f in solar if f["properties"].get("Commodity") == "Solar Energy Facilities"
         and f["properties"].get("Disposition") == "Authorized"]
for feature in solar:
    feature["properties"] = {"name": feature["properties"]["ProjectName"], "status": "Authorized BLM ROW",
                             "note": "One mapped right-of-way, not the full Ivanpah solar footprint"}
write("solar-row.geojson", solar)
