"""Check scientific data invariants of the shipped, aggregate GeoJSON files."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "public" / "data"


def features(name):
    document = json.loads((root / name).read_text())
    assert document["type"] == "FeatureCollection"
    return document["features"]


sites = features("study-sites.geojson")
assert len(sites) == 11
assert sum(site["properties"]["n"] for site in sites) == 299
assert sum(site["properties"]["kind"] == "broader-area" for site in sites) == 1
assert next(site for site in sites if site["properties"]["kind"] == "broader-area")["properties"]["name"] == "PiuteValley"
for site in sites:
    longitude, latitude = site["geometry"]["coordinates"]
    assert -115.70 < longitude < -114.80 and 35.30 < latitude < 35.90
    assert site["geometry"]["type"] == "Point"

highway = features("interstate-15.geojson")
railway = features("railways.geojson")
solar = features("solar-row.geojson")
assert highway and all(feature["properties"]["name"] == "I-15" for feature in highway)
assert railway and all(feature["geometry"]["type"] == "LineString" for feature in railway)
assert len(solar) == 1 and solar[0]["properties"]["name"] == "Solar Partners I - Ivanpah 2"
print("Verified 11 aggregate sites / 299 records, distinct Piute area, and nonempty cited GIS overlays.")
