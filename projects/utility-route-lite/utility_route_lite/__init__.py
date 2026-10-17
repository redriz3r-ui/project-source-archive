"""QGIS plugin entry point for Utility Route Lite."""


def classFactory(iface):  # noqa: N802 - QGIS plugin API spelling
    from .plugin import UtilityRouteLitePlugin

    return UtilityRouteLitePlugin(iface)
