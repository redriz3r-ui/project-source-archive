"""Internal macOS app bundle. A build is not a consumer release."""

import os
from pathlib import Path


ROOT = Path(SPECPATH).resolve().parent
IDENTITY = os.environ.get("SELF_PLEASURE_SIGNING_IDENTITY") or None
ENTITLEMENTS = str(ROOT / "packaging" / "entitlements.plist") if IDENTITY else None
MODELS = ROOT / ".models"
for filename in ("face_landmarker.task", "hand_landmarker.task"):
    if not (MODELS / filename).is_file():
        raise SystemExit(f"Missing bundled local model: {MODELS / filename}")

a = Analysis(
    [str(ROOT / "app" / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "app" / "web"), "app/web"),
           (str(MODELS), ".models")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops.auto",
                   "uvicorn.protocols.http.auto", "uvicorn.lifespan.on"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="SelfPleasure", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    codesign_identity=IDENTITY, entitlements_file=ENTITLEMENTS,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name="SelfPleasure")
app = BUNDLE(
    coll, name="SelfPleasure.app", icon=None,
    bundle_identifier="org.selfpleasure.local", version="0.1.0",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSCameraUsageDescription": "SelfPleasure uses the camera only after you start a local tracking session.",
        "LSMinimumSystemVersion": "13.0",
    },
)
