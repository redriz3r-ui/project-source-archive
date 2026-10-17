"""The single QGIS Processing provider."""

from qgis.core import QgsProcessingProvider

from .algorithms import (
    BatchRoutesAlgorithm,
    BuildNetworkAlgorithm,
    ExportBundleAlgorithm,
    FindRouteAlgorithm,
    InspectNetworkAlgorithm,
)


class UtilityRouteLiteProvider(QgsProcessingProvider):
    def id(self):
        return "utilityroutelite"

    def name(self):
        return "Utility Route Lite (experimental)"

    def longName(self):  # noqa: N802 - QGIS API spelling
        return self.name()

    def loadAlgorithms(self):  # noqa: N802 - QGIS API spelling
        for algorithm in (
            BuildNetworkAlgorithm,
            InspectNetworkAlgorithm,
            FindRouteAlgorithm,
            BatchRoutesAlgorithm,
            ExportBundleAlgorithm,
        ):
            self.addAlgorithm(algorithm())
