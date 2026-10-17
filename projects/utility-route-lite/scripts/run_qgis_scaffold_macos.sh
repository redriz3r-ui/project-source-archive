#!/bin/bash
set -euo pipefail
qgis_bundle="${1:-/Applications/QGIS-final-4_2_3.app}"
project_root="$(cd "$(dirname "$0")/.." && pwd)"
test_file="${2:-tests/qgis_smoke.py}"
qgis_contents="$qgis_bundle/Contents"
qgis_python="$qgis_contents/MacOS/python3.12"
if [[ ! -x "$qgis_python" ]]; then
  echo "QGIS bundled Python not found: $qgis_python" >&2
  exit 1
fi
export PYTHONHOME="$qgis_contents/Resources"
export PYTHONPATH="$project_root:$qgis_contents/Resources/python3.12:$qgis_contents/Resources/python3.12/lib-dynload:$qgis_contents/Resources/python3.12/site-packages:$qgis_contents/Resources/qgis/python/plugins"
export QGIS_PREFIX_PATH="$qgis_contents/Resources/qgis"
export QT_PLUGIN_PATH="$qgis_contents/PlugIns"
export QT_QPA_PLATFORM=offscreen
export PROJ_DATA="$qgis_contents/Resources/qgis/proj"
export GDAL_DATA="$qgis_contents/Resources/qgis/gdal"
export PYTHONDONTWRITEBYTECODE=1
exec "$qgis_python" "$project_root/$test_file" -v
