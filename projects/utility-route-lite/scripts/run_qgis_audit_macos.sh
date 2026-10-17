#!/bin/bash
# Run only the original feasibility probes; never load an upstream plugin.
set -euo pipefail
audit_bundle="${1:-/Applications/QGIS-final-4_2_3.app}"
audit_root="$(cd "$(dirname "$0")/.." && pwd)"
audit_contents="$audit_bundle/Contents"
audit_python="$audit_contents/MacOS/python3.12"
if [[ ! -x "$audit_python" ]]; then
  echo "QGIS bundled Python not found: $audit_python" >&2
  exit 1
fi
export PYTHONHOME="$audit_contents/Resources"
export PYTHONPATH="$audit_contents/Resources/python3.12:$audit_contents/Resources/python3.12/lib-dynload:$audit_contents/Resources/python3.12/site-packages:$audit_contents/Resources/qgis/python/plugins"
export QGIS_PREFIX_PATH="$audit_contents/Resources/qgis"
export QT_PLUGIN_PATH="$audit_contents/PlugIns"
export QT_QPA_PLATFORM=offscreen
export PROJ_DATA="$audit_contents/Resources/qgis/proj"
export GDAL_DATA="$audit_contents/Resources/qgis/gdal"
export PYTHONDONTWRITEBYTECODE=1
exec "$audit_python" "$audit_root/tests/audit/test_qgis_feasibility.py" -v
