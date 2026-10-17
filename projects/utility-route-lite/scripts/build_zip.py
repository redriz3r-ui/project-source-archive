"""Build a QGIS plugin ZIP from a strict, reviewed file list."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "utility_route_lite"
INCLUDED = (
    "__init__.py",
    "plugin.py",
    "processing/__init__.py",
    "processing/provider.py",
    "processing/algorithms.py",
    "core/__init__.py",
    "core/builder.py",
    "core/serialization.py",
    "qgis_adapters/__init__.py",
    "qgis_adapters/builder.py",
    "qgis_adapters/crs.py",
    "metadata.txt",
    "icon.svg",
)
VERSION = "0.1.0"


def build_zip(destination=None):
    destination = Path(destination) if destination is not None else ROOT / "dist" / f"utility_route_lite-{VERSION}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries = [(PLUGIN / relative, f"utility_route_lite/{relative}") for relative in INCLUDED]
    entries.append((ROOT / "LICENSE", "utility_route_lite/LICENSE"))
    for source, _ in entries:
        if not source.is_file():
            raise FileNotFoundError(source)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for source, arcname in entries:
            info = ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    return destination


if __name__ == "__main__":
    print(build_zip())
