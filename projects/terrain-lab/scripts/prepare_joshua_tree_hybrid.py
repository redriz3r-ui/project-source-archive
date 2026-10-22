"""Convert the preserved USGS Joshua-tree hybrid-presence cells to WGS84 GeoJSON.

Run with pyshp, pyproj, and shapely (the same conversion tools used for USPVDB).
The source shapefile components are never modified or simplified.
"""

import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'research/intake/sources/esque-2023-joshua-tree'
BASE = 'Hybrid_Presence_Cells'
OUTPUT = SOURCE / 'hybrid-presence-cells.geojson'
BUNDLE = SOURCE / 'Hybrid_Presence_Cells_source_bundle.zip'
COMPONENTS = ('cpg', 'dbf', 'prj', 'sbn', 'sbx', 'shp', 'shx')


def main():
    # A deterministic local archive groups the unmodified publisher components
    # for the existing registered-dataset provenance contract.
    with ZipFile(BUNDLE, 'w') as archive:
        for extension in COMPONENTS:
            name = f'{BASE}.{extension}'
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (SOURCE / name).read_bytes())
    reader = shapefile.Reader(str(SOURCE / f'{BASE}.shp'))
    source_crs = CRS.from_wkt((SOURCE / f'{BASE}.prj').read_text())
    if source_crs.to_authority() != ('ESRI', '102008'):
        raise ValueError(f'Unexpected source CRS: {source_crs.to_string()}')
    to_wgs84 = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
    features = []
    for row in reader.iterShapeRecords():
        properties = row.record.as_dict()
        if properties['Final_Stat'] != 'P' or properties['State'] != 'NV':
            raise ValueError('Unexpected source category or state')
        geometry = shape(row.shape.__geo_interface__)
        if not geometry.is_valid:
            raise ValueError(f'Invalid source geometry: {properties["ID"]}')
        # The source is POLYGONZ, but its Z values are not a measured tree height.
        # Produce two-dimensional WGS84 GeoJSON for the existing vector map.
        projected = transform(lambda x, y, z=None: to_wgs84.transform(x, y), geometry)
        features.append({
            'type': 'Feature', 'id': properties['ID'],
            'geometry': mapping(projected),
            'properties': {
                **properties,
                'terrainLabStudyId': 'esque-2023-joshua-tree-distribution',
                'terrainLabDatasetId': 'hybrid-presence-grid-cells',
                'terrainLabRole': 'observed-geography',
                'terrainLabSubject': 'Joshua tree hybrid presence grid cell; not an individual tree location',
            },
        })
    features.sort(key=lambda feature: feature['id'])
    if len(features) != 941 or len({feature['id'] for feature in features}) != 941:
        raise ValueError('Unexpected source feature count or duplicate ID')
    OUTPUT.write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                                 separators=(',', ':')) + '\n')
    print(f'Prepared {len(features)} grid cells at {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
