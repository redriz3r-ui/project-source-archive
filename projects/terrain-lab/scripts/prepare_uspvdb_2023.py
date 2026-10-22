"""Prepare the cited USPVDB v1 polygons for Terrain Lab's WGS84 GeoJSON viewer.

Requires pyshp, pyproj, and shapely for this one-time source conversion.
The original USGS ZIP is never changed.
"""

import io
import json
from pathlib import Path
import zipfile

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'public/data/fleckenstein-2025/uspvdb_v1_0_20231108.zip'
OUTPUT = ROOT / 'public/data/fleckenstein-2025/uspvdb-v1-study-states.geojson'
STATES = {'AZ', 'CA', 'CO', 'NM', 'NV', 'TX', 'UT'}
BASE = 'uspvdb_v1_0_20231108'


def main():
    with zipfile.ZipFile(SOURCE) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read(f'{BASE}.zip'))) as inner:
            reader = shapefile.Reader(
                shp=io.BytesIO(inner.read(f'{BASE}.shp')),
                shx=io.BytesIO(inner.read(f'{BASE}.shx')),
                dbf=io.BytesIO(inner.read(f'{BASE}.dbf')),
            )
            source_crs = CRS.from_wkt(inner.read(f'{BASE}.prj').decode())
            to_wgs84 = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
            features = []
            for row in reader.iterShapeRecords():
                properties = row.record.as_dict()
                if properties['p_state'] not in STATES:
                    continue
                properties['terrainLabStudyId'] = 'fleckenstein-2025-solar-conservation'
                properties['terrainLabDatasetId'] = 'uspvdb-v1-study-states'
                properties['terrainLabRole'] = 'observed solar infrastructure; not tortoise observations'
                geometry = transform(to_wgs84.transform, shape(row.shape.__geo_interface__))
                features.append({
                    'type': 'Feature',
                    'id': properties['case_id'],
                    'geometry': mapping(geometry),
                    'properties': properties,
                })
    features.sort(key=lambda feature: feature['id'])
    OUTPUT.write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                                 separators=(',', ':')) + '\n')
    print(f'Prepared {len(features)} USPVDB solar-array polygons at {OUTPUT}')


if __name__ == '__main__':
    main()
