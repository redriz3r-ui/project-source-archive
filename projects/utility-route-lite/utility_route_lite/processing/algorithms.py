"""Processing interface; Network Builder is implemented, other tasks are shells."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterPoint,
    QgsProcessingParameterString,
)


def source_parameters(optional):
    """Frozen source-mode names; XOR choices are for later implementation."""
    return [
        QgsProcessingParameterFeatureSource("SOURCE_LINES", "Existing utility lines (read only)", optional=optional),
        QgsProcessingParameterCrs("SOURCE_CRS", "Declared source CRS", optional=optional),
        QgsProcessingParameterCrs("NETWORK_CRS", "Network CRS", optional=optional),
        QgsProcessingParameterString("LAYER_KEY", "Stable source layer key", optional=optional),
        QgsProcessingParameterField("FEATURE_KEY_FIELD", "Stable feature key field", parentLayerParameterName="SOURCE_LINES", optional=optional),
        QgsProcessingParameterFile("RULE_PROFILE", "Rule profile JSON", optional=optional),
        QgsProcessingParameterFile("JUNCTIONS_JSON", "Declared junctions JSON", optional=True),
    ]


def graph_or_source_parameters():
    return [QgsProcessingParameterFile("GRAPH_JSON", "Existing network graph JSON", optional=True),
            *source_parameters(optional=True)]


class StubAlgorithm(QgsProcessingAlgorithm):
    ALGORITHM_ID = ""
    TITLE = ""

    def name(self):
        return self.ALGORITHM_ID

    def displayName(self):  # noqa: N802 - QGIS API spelling
        return f"{self.TITLE} (NOT IMPLEMENTED)"

    def group(self):
        return "Utility Route Lite"

    def groupId(self):  # noqa: N802 - QGIS API spelling
        return "utility_route_lite"

    def shortHelpString(self):  # noqa: N802 - QGIS API spelling
        return "NOT IMPLEMENTED. This v0.1 scaffold exposes the frozen interface only; it produces no results."

    def createInstance(self):  # noqa: N802 - QGIS API spelling
        return type(self)()

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802 - QGIS API spelling
        raise QgsProcessingException(f"NOT IMPLEMENTED: {self.TITLE} is a scaffold only")


class BuildNetworkAlgorithm(StubAlgorithm):
    ALGORITHM_ID = "build_network"
    TITLE = "Network Builder"

    def displayName(self):  # noqa: N802
        return self.TITLE

    def shortHelpString(self):  # noqa: N802
        return ("Build a proposed 2D utility pathway graph from a read-only line source. "
                "Crossings and nearby gaps never create connections. Choose exact geometric endpoint "
                "connectivity or supply a versioned, explicit junction document. Geometry does not "
                "verify physical asset connectivity. A projected meter NETWORK_CRS and stable "
                "feature key field are required. Invalid geometry/rules abort without a graph.")

    def initAlgorithm(self, config=None):  # noqa: N802
        for parameter in source_parameters(optional=False):
            self.addParameter(parameter)
        self.addParameter(QgsProcessingParameterFileDestination("GRAPH_JSON", "Network graph JSON", "JSON files (*.json)"))
        self.addParameter(QgsProcessingParameterFileDestination("QA_GPKG", "QA issues GeoPackage", "GeoPackage files (*.gpkg)"))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        from ..core.builder import BuildError
        from ..core.serialization import pretty_json
        from ..qgis_adapters.builder import graph_from_source, write_qa_gpkg

        source = self.parameterAsSource(parameters, "SOURCE_LINES", context)
        source_crs = self.parameterAsCrs(parameters, "SOURCE_CRS", context)
        network_crs = self.parameterAsCrs(parameters, "NETWORK_CRS", context)
        layer_key = self.parameterAsString(parameters, "LAYER_KEY", context)
        feature_key_field = self.parameterAsString(parameters, "FEATURE_KEY_FIELD", context)
        graph_path = Path(self.parameterAsFileOutput(parameters, "GRAPH_JSON", context))
        qa_path = Path(self.parameterAsFileOutput(parameters, "QA_GPKG", context))
        rule_path = Path(self.parameterAsFile(parameters, "RULE_PROFILE", context))
        junction_value = self.parameterAsFile(parameters, "JUNCTIONS_JSON", context)
        try:
            if source is None or not str(graph_path) or not str(qa_path):
                raise BuildError("INVALID_GEOMETRY", "source and output destinations are required")
            if graph_path.resolve() == qa_path.resolve() or graph_path.exists() or qa_path.exists():
                raise BuildError("EXPORT_FAILED", "output paths must differ and must not already exist")
            profile = json.loads(rule_path.read_text(encoding="utf-8"))
            junctions = json.loads(Path(junction_value).read_text(encoding="utf-8")) if junction_value else None
            graph = graph_from_source(source, source_crs=source_crs, network_crs=network_crs,
                                      layer_key=layer_key, feature_key_field=feature_key_field,
                                      profile=profile, junctions=junctions, context=context, feedback=feedback)
            if feedback and feedback.isCanceled():
                raise BuildError("CANCELED", "build canceled")
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            qa_path.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=qa_path.parent) as temporary, TemporaryDirectory(dir=graph_path.parent) as graph_temporary:
                staged_qa = Path(temporary) / "qa.gpkg"
                staged_graph = Path(graph_temporary) / "graph.json"
                write_qa_gpkg(graph, staged_qa, network_crs, context, feedback=feedback)
                staged_graph.write_text(pretty_json(graph), encoding="utf-8")
                if feedback and feedback.isCanceled():
                    raise BuildError("CANCELED", "build canceled")
                if graph_path.exists() or qa_path.exists():
                    raise BuildError("EXPORT_FAILED", "output destination appeared during build")
                published = []
                try:
                    for staged, destination in ((staged_qa, qa_path), (staged_graph, graph_path)):
                        # Atomic no-clobber publication. Each stage is on its destination filesystem.
                        try:
                            os.link(staged, destination)
                        except OSError as exc:
                            raise BuildError("EXPORT_FAILED", f"cannot exclusively publish {destination.name}: {exc}") from exc
                        published.append((staged, destination))
                        if feedback and feedback.isCanceled():
                            raise BuildError("CANCELED", "build canceled")
                except Exception:
                    for staged, destination in reversed(published):
                        try:
                            # A replacement by another writer is not ours to remove.
                            if os.path.samestat(staged.stat(), destination.lstat()):
                                destination.unlink()
                        except FileNotFoundError:
                            pass
                    raise
            return {"GRAPH_JSON": str(graph_path), "QA_GPKG": str(qa_path)}
        except BuildError as exc:
            raise QgsProcessingException(str(exc)) from exc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise QgsProcessingException(f"Network Builder input/output error: {exc}") from exc


class InspectNetworkAlgorithm(StubAlgorithm):
    ALGORITHM_ID = "inspect_network"
    TITLE = "Network Inspector"

    def initAlgorithm(self, config=None):  # noqa: N802
        for parameter in graph_or_source_parameters():
            self.addParameter(parameter)
        self.addParameter(QgsProcessingParameterNumber("QA_NEAR_MISS_M", "Near-miss threshold (m)", optional=True, minValue=0))
        self.addParameter(QgsProcessingParameterFileDestination("QA_GPKG", "QA issues GeoPackage", "GeoPackage files (*.gpkg)"))
        self.addParameter(QgsProcessingParameterFileDestination("SUMMARY_JSON", "QA summary JSON", "JSON files (*.json)"))


class FindRouteAlgorithm(StubAlgorithm):
    ALGORITHM_ID = "find_route"
    TITLE = "Smart Router"

    def initAlgorithm(self, config=None):  # noqa: N802
        for parameter in graph_or_source_parameters():
            self.addParameter(parameter)
        self.addParameter(QgsProcessingParameterString("ROUTE_ID", "Stable route ID"))
        self.addParameter(QgsProcessingParameterPoint("START_POINT", "Start point"))
        self.addParameter(QgsProcessingParameterPoint("END_POINT", "End point"))
        self.addParameter(QgsProcessingParameterCrs("REQUEST_CRS", "Point request CRS"))
        self.addParameter(QgsProcessingParameterNumber("SNAP_TOLERANCE_M", "Snap tolerance (m)", minValue=0))
        self.addParameter(QgsProcessingParameterString("START_EDGE_ID", "Start edge ID to resolve ties", optional=True))
        self.addParameter(QgsProcessingParameterString("END_EDGE_ID", "End edge ID to resolve ties", optional=True))
        self.addParameter(QgsProcessingParameterFileDestination("RESULT_JSON", "Route result JSON", "JSON files (*.json)"))
        self.addParameter(QgsProcessingParameterFileDestination("ROUTES_GPKG", "Proposed routes GeoPackage", "GeoPackage files (*.gpkg)"))


class BatchRoutesAlgorithm(StubAlgorithm):
    ALGORITHM_ID = "batch_routes"
    TITLE = "Batch Route Generator"

    def initAlgorithm(self, config=None):  # noqa: N802
        for parameter in graph_or_source_parameters():
            self.addParameter(parameter)
        self.addParameter(QgsProcessingParameterCrs("PAIRS_CRS", "Request pairs CRS"))
        self.addParameter(QgsProcessingParameterNumber("SNAP_TOLERANCE_M", "Snap tolerance (m)", minValue=0))
        self.addParameter(QgsProcessingParameterFile("PAIRS_CSV", "Request pairs CSV", optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource("PAIRS_LAYER", "Request pairs layer", optional=True))
        self.addParameter(QgsProcessingParameterFileDestination("RESULT_JSON", "Batch results JSON", "JSON files (*.json)"))
        self.addParameter(QgsProcessingParameterFileDestination("ROUTES_GPKG", "Proposed routes GeoPackage", "GeoPackage files (*.gpkg)"))
        self.addParameter(QgsProcessingParameterFileDestination("FAILURES_CSV", "Failures CSV", "CSV files (*.csv)"))


class ExportBundleAlgorithm(StubAlgorithm):
    ALGORITHM_ID = "export_bundle"
    TITLE = "Route Packager"

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterFile("RESULT_JSON", "Route results JSON"))
        self.addParameter(QgsProcessingParameterString("DESTINATION", "Bundle destination path"))
        self.addParameter(QgsProcessingParameterFile("REVIEW_STATE_JSON", "Review state JSON", optional=True))
        self.addParameter(QgsProcessingParameterBoolean("OVERWRITE", "Allow overwrite", defaultValue=False, optional=True))
        self.addOutput(QgsProcessingOutputString("BUNDLE", "Bundle path"))
