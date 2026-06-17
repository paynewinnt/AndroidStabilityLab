#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT_DIR/build/pyinstaller_config}"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller is not installed. Run: pip install -r requirements-desktop.txt" >&2
  exit 1
fi

if [[ -n "${ASL_PLATFORM_TOOLS_DIR:-}" ]]; then
  echo "Bundling Android platform-tools from: $ASL_PLATFORM_TOOLS_DIR"
fi

"$PYTHON_BIN" -m PyInstaller --noconfirm packaging/pyinstaller/AndroidStabilityLab.spec

echo "Desktop bundle written to: $ROOT_DIR/dist/AndroidStabilityLab"
case "$(uname -s)" in
  Darwin)
    if [[ -d "$ROOT_DIR/dist/AndroidStabilityLab.app" ]]; then
      echo "macOS app bundle written to: $ROOT_DIR/dist/AndroidStabilityLab.app"
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "Windows executable: $ROOT_DIR/dist/AndroidStabilityLab/AndroidStabilityLab.exe"
    ;;
  *)
    echo "Executable: $ROOT_DIR/dist/AndroidStabilityLab/AndroidStabilityLab"
    ;;
esac
