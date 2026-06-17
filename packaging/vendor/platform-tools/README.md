# Optional Android Platform-Tools Bundling

Android Stability Lab can run with `adb` from `PATH` or from an Android SDK
installation. Desktop packages can also include a platform-specific
`platform-tools` directory when a self-contained lab machine is useful.

Do not commit Android SDK binaries to this repository by default. To build with
a bundled `adb`, either:

- Set `ASL_PLATFORM_TOOLS_DIR` to an existing Android SDK `platform-tools`
  directory before running PyInstaller.
- Or place platform-specific files under one of these ignored local directories:
  - `packaging/vendor/platform-tools/macos/`
  - `packaging/vendor/platform-tools/windows/`
  - `packaging/vendor/platform-tools/linux/`

At runtime, adb resolution order is:

1. `ASL_ADB_PATH` / `ADB_PATH`
2. Bundled `platform-tools`
3. `ANDROID_HOME/platform-tools` / `ANDROID_SDK_ROOT/platform-tools`
4. `adb` from `PATH`
