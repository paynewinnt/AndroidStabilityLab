# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa: F821

import os
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


ROOT_DIR = Path(SPECPATH).parents[1]
ICON_DIR = ROOT_DIR / "assets" / "icons"
try:
    import webview

    WEBVIEW_HOOK_DIR = Path(webview.__file__).resolve().parent / "__pyinstaller"
except Exception:
    WEBVIEW_HOOK_DIR = None

hiddenimports = collect_submodules("stability") + [
    "webview",
    "pymysql",
    "sqlalchemy.dialects.mysql.pymysql",
]

def platform_name():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def adb_executable_name():
    return "adb.exe" if sys.platform.startswith("win") else "adb"


def platform_tools_dir():
    configured = os.environ.get("ASL_PLATFORM_TOOLS_DIR", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(ROOT_DIR / "packaging" / "vendor" / "platform-tools" / platform_name())
    for candidate in candidates:
        if (candidate / adb_executable_name()).exists():
            return candidate
    return None


def pyinstaller_icon_path():
    if sys.platform.startswith("win"):
        icon = ICON_DIR / "app_icon.ico"
    elif sys.platform == "darwin":
        icon = ICON_DIR / "app_icon.icns"
    else:
        icon = ICON_DIR / "app_icon.png"
    return str(icon) if icon.exists() else None


bundled_platform_tools_dir = platform_tools_dir()

datas = [
    (str(ROOT_DIR / "assets"), "assets"),
    (str(ROOT_DIR / "config"), "config"),
    (str(ROOT_DIR / "runtime.example"), "runtime.example"),
]
if bundled_platform_tools_dir is not None:
    datas.append((str(bundled_platform_tools_dir), "platform-tools"))

icon_path = pyinstaller_icon_path()

a = Analysis(
    [str(ROOT_DIR / "stability" / "desktop" / "__main__.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(WEBVIEW_HOOK_DIR)] if WEBVIEW_HOOK_DIR is not None and WEBVIEW_HOOK_DIR.exists() else [],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AndroidStabilityLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AndroidStabilityLab",
)

if sys.platform == "darwin" and icon_path is not None:
    app = BUNDLE(
        coll,
        name="AndroidStabilityLab.app",
        icon=icon_path,
        bundle_identifier="dev.androidstabilitylab.desktop",
    )
