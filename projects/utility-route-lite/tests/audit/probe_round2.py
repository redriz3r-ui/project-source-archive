from qgis.core import QgsGeometry
for wkt in ('LINESTRING(0 0,1 0)','MULTILINESTRING((0 0,1 0),(2 0,3 0))'):
    g=QgsGeometry.fromWkt(wkt).constGet()
    print(type(g).__name__, 'nCoordinates',g.nCoordinates(),'numGeometries',g.numGeometries() if hasattr(g,'numGeometries') else 1)
from qgis.core import Qgis,QgsCoordinateReferenceSystem,QgsApplication
import os
QgsApplication.setPrefixPath(os.environ['QGIS_PREFIX_PATH'],True)
app=QgsApplication([],False);app.initQgis()
for authority in ('EPSG:3857','EPSG:4978','EPSG:5703'):
    crs=QgsCoordinateReferenceSystem(authority)
    print(authority,crs.type(),crs.type()==Qgis.CrsType.Projected)
app.exitQgis()
