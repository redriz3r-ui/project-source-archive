"""Read-only PyQGIS source adapter and GeoPackage QA output."""

from pathlib import Path

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsDistanceArea, QgsFeature, QgsField, QgsGeometry, QgsPointXY,
    QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes,
)

from ..core.builder import BuildError, build_graph, _check_canceled, _validate_profile


def _crs_wkt(crs):
    return crs.toWkt(Qgis.CrsWktVariant.Wkt2_2019)


def _point_transform(source_crs, network_crs, context):
    operation = QgsCoordinateTransform(source_crs, network_crs, context.transformContext())
    def transform(xy):
        point = operation.transform(QgsPointXY(*xy))
        return [point.x(), point.y()]
    return transform


def graph_from_source(source, *, source_crs, network_crs, layer_key, feature_key_field,
                      profile, junctions, context, feedback=None):
    _check_canceled(feedback)
    _validate_profile(profile)
    if source is None or not source_crs.isValid() or not network_crs.isValid():
        raise BuildError("INVALID_CRS", "source/network CRS is invalid")
    if source.sourceCrs() != source_crs:
        raise BuildError("INVALID_CRS", "declared SOURCE_CRS differs from source layer CRS")
    if network_crs.isGeographic() or network_crs.mapUnits() != Qgis.DistanceUnit.Meters:
        raise BuildError("INVALID_CRS", "NETWORK_CRS must be projected with meter horizontal units")
    names = {field.name() for field in source.fields()}
    if feature_key_field not in names:
        raise BuildError("UNSUPPORTED_RULE", "feature key field does not exist")
    for rule in (profile.get("eligibility", {}), profile.get("direction", {})):
        if rule.get("mode") == "FIELD" and rule.get("field") not in names:
            raise BuildError("UNSUPPORTED_RULE", f"rule field {rule.get('field')!r} does not exist")
    selected = {feature_key_field}
    selected.update(rule["field"] for rule in (profile["eligibility"], profile["direction"]) if rule["mode"] == "FIELD")
    def features():
        vertex_count = 0
        part_count = 0
        for item in source.getFeatures():
            _check_canceled(feedback)
            geometry = item.geometry()
            if geometry is None or geometry.isNull() or geometry.isEmpty() or QgsWkbTypes.isCurvedType(geometry.wkbType()):
                raise BuildError("INVALID_GEOMETRY", "null, empty or curved geometry is unsupported")
            if geometry.type() != Qgis.GeometryType.Line:
                raise BuildError("INVALID_GEOMETRY", "only LineString/MultiLineString is supported")
            has_z = QgsWkbTypes.hasZ(geometry.wkbType())
            has_m = QgsWkbTypes.hasM(geometry.wkbType())
            abstract = geometry.constGet()
            geometry_parts = abstract.numGeometries() if geometry.isMultipart() else 1
            if (vertex_count + abstract.nCoordinates() > 2_000_000
                    or part_count + geometry_parts > 250_000):
                raise BuildError("LIMIT_EXCEEDED", "source vertex/part limit exceeded before snapshot allocation")
            pieces = geometry.asGeometryCollection() if geometry.isMultipart() else [geometry]
            sequences = []
            for piece in pieces:
                _check_canceled(feedback)
                part_count += 1
                if part_count > 250_000:
                    raise BuildError("LIMIT_EXCEEDED", "too many source parts")
                coordinates = []
                for vertex in piece.vertices():
                    _check_canceled(feedback)
                    vertex_count += 1
                    if vertex_count > 2_000_000:
                        raise BuildError("LIMIT_EXCEEDED", "too many source vertices")
                    ordinate = [vertex.x(), vertex.y()]
                    if has_z:
                        ordinate.append(vertex.z())
                    if has_m:
                        ordinate.append(vertex.m())
                    coordinates.append(ordinate)
                sequences.append(coordinates)
            props = {}
            for name in selected:
                value = item[name]
                # PyQGIS may return a null QVariant rather than Python None.
                if isinstance(value, QVariant):
                    if value.isNull():
                        value = None
                    else:
                        value = value.value()
                props[name] = value
            yield {"geometry": {"type": "MultiLineString" if geometry.isMultipart() else "LineString",
                                "coordinates": sequences if geometry.isMultipart() else sequences[0]},
                   "properties": props, "native_fid": str(item.id()), "has_z": has_z, "has_m": has_m}
    distance = QgsDistanceArea()
    distance.setSourceCrs(network_crs, context.transformContext())
    if profile["ellipsoid"] != "NONE" and not distance.setEllipsoid(profile["ellipsoid"]):
        raise BuildError("INVALID_CRS", "ellipsoid setup failed")
    if profile["ellipsoid"] == "NONE":
        distance.setEllipsoid("NONE")
    def measure(vertices):
        raw = distance.measureLine([QgsPointXY(*xy) for xy in vertices])
        return distance.convertLengthMeasurement(raw, Qgis.DistanceUnit.Meters)
    junction_transform = None
    if junctions is not None:
        junction_crs = QgsCoordinateReferenceSystem.fromWkt(junctions.get("junction_crs_wkt", ""))
        if not junction_crs.isValid():
            raise BuildError("INVALID_CRS", "junction CRS WKT is invalid")
        junction_transform = _point_transform(junction_crs, network_crs, context)
    return build_graph(features(), source_crs_wkt=_crs_wkt(source_crs), network_crs_wkt=_crs_wkt(network_crs),
                       layer_key=layer_key, feature_key_field=feature_key_field, profile=profile,
                       junctions=junctions, transform=_point_transform(source_crs, network_crs, context),
                       junction_transform=junction_transform, measure=measure,
                       qgis_version=Qgis.QGIS_VERSION if hasattr(Qgis, "QGIS_VERSION") else QgsApplication.qgisVersion(),
                       feedback=feedback)


QA_FIELDS = (
    ("schema_version", QVariant.String), ("issue_id", QVariant.String), ("route_id", QVariant.String),
    ("severity", QVariant.String), ("code", QVariant.String), ("message", QVariant.String),
    ("source_layer_key", QVariant.String), ("source_feature_key", QVariant.String),
    ("source_part_index", QVariant.Int), ("edge_id", QVariant.String), ("junction_id", QVariant.String),
)


def write_qa_gpkg(graph, destination, network_crs, context, feedback=None):
    _check_canceled(feedback)
    destination = Path(destination)
    layer = QgsVectorLayer("Point", "qa_issues", "memory")
    if not layer.isValid():
        raise BuildError("EXPORT_FAILED", "cannot create QA memory layer")
    layer.setCrs(network_crs)
    provider = layer.dataProvider()
    provider.addAttributes([QgsField(name, field_type) for name, field_type in QA_FIELDS])
    layer.updateFields()
    rows = []
    for issue in graph["qa_issues"]:
        _check_canceled(feedback)
        feature = QgsFeature(layer.fields())
        feature.setAttributes([issue.get(name) for name, _ in QA_FIELDS])
        if issue.get("xy") is not None:
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*issue["xy"])))
        rows.append(feature)
        if len(rows) >= 1000:
            if not provider.addFeatures(rows)[0]:
                raise BuildError("EXPORT_FAILED", "cannot add QA issues")
            rows.clear()
    if rows and not provider.addFeatures(rows)[0]:
        raise BuildError("EXPORT_FAILED", "cannot add QA issues")
    _check_canceled(feedback)
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = "qa_issues"
    error, message, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(destination), context.transformContext(), options)
    if error != QgsVectorFileWriter.WriterError.NoError:
        raise BuildError("EXPORT_FAILED", message)
    _check_canceled(feedback)
    return destination
