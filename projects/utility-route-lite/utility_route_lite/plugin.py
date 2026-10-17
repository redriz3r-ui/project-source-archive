"""Plugin lifecycle and the deliberately inactive Route Reviewer dock."""

from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction, QIcon
from qgis.PyQt.QtWidgets import QLabel, QVBoxLayout, QWidget
from qgis.core import QgsApplication
from qgis.gui import QgsDockWidget

from .processing.provider import UtilityRouteLiteProvider


class UtilityRouteLitePlugin:
    MENU = "&Utility Route Lite"

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dock = None

    def initGui(self):  # noqa: N802 - QGIS plugin API spelling
        if self.provider is not None:
            return
        provider = UtilityRouteLiteProvider()
        if not QgsApplication.processingRegistry().addProvider(provider):
            raise RuntimeError("Utility Route Lite Processing provider registration failed")
        self.provider = provider
        try:
            icon = QIcon(str(Path(__file__).with_name("icon.svg")))
            self.action = QAction(icon, "Route Reviewer (NOT IMPLEMENTED)", self.iface.mainWindow())
            self.action.triggered.connect(self.show_reviewer)
            self.iface.addPluginToMenu(self.MENU, self.action)
        except Exception:
            self.unload()
            raise

    def show_reviewer(self):
        if self.dock is None:
            self.dock = QgsDockWidget("Route Reviewer — NOT IMPLEMENTED", self.iface.mainWindow())
            self.dock.setObjectName("UtilityRouteLiteReviewer")
            content = QWidget(self.dock)
            layout = QVBoxLayout(content)
            label = QLabel("NOT IMPLEMENTED: Route Reviewer cannot inspect or approve routes yet.", content)
            label.setWordWrap(True)
            layout.addWidget(label)
            self.dock.setWidget(content)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.dock.raise_()

    def unload(self):
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu(self.MENU, self.action)
            self.action.deleteLater()
            self.action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
