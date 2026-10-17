"""CRS parsing belongs to the installed QGIS runtime, not a WKT regex."""

from qgis.core import Qgis, QgsCoordinateReferenceSystem


def is_projected_meters(definition):
    crs = QgsCoordinateReferenceSystem.fromWkt(definition)
    if not crs.isValid():
        crs = QgsCoordinateReferenceSystem(definition)
    return (crs.isValid() and not crs.isGeographic()
            and crs.mapUnits() == Qgis.DistanceUnit.Meters)
