from __future__ import annotations

import argparse
import atexit
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import urlopen

from stability import create_v1_persistent_bootstrap
from stability.app import ConfigProvider
from stability.cli.handlers.web import _is_local_web_host
from stability.web.server import create_web_portal_server


BootstrapFactory = Callable[..., object]
ServerFactory = Callable[..., object]
ReadinessProbe = Callable[[str, float], None]
WorkspacePreparer = Callable[[str, str], tuple[Path, Path]]
DatabaseConfigurer = Callable[[Path], None]


@dataclass(frozen=True)
class DesktopLaunchConfig:
    """Runtime options for the pywebview desktop shell."""

    host: str = "127.0.0.1"
    port: int = 0
    config_dir: str = "config"
    workspace_dir: str = ""
    start_path: str = "/"
    title: str = "Android Stability Lab"
    width: int = 1440
    height: int = 920
    icon_path: str = ""
    debug: bool = False
    readiness_timeout_seconds: float = 10.0


class DesktopPortalRuntime:
    """Own the embedded localhost Web server used by the desktop shell."""

    def __init__(
        self,
        config: DesktopLaunchConfig,
        *,
        bootstrap_factory: BootstrapFactory = create_v1_persistent_bootstrap,
        server_factory: ServerFactory = create_web_portal_server,
        readiness_probe: ReadinessProbe | None = None,
        workspace_preparer: WorkspacePreparer | None = None,
        database_configurer: DatabaseConfigurer | None = None,
    ) -> None:
        self._config = config
        self._bootstrap_factory = bootstrap_factory
        self._server_factory = server_factory
        self._readiness_probe = readiness_probe or wait_until_ready
        self._workspace_preparer = workspace_preparer or prepare_desktop_workspace
        self._database_configurer = database_configurer or configure_desktop_database
        self._server: Any | None = None
        self._thread: threading.Thread | None = None
        self._url = ""

    @property
    def url(self) -> str:
        return self._url

    def start(self) -> str:
        if self._server is not None:
            return self._url
        if not _is_local_web_host(self._config.host):
            raise ValueError("Desktop shell only binds to localhost/127.x/::1.")
        _workspace_root, config_dir = self._workspace_preparer(self._config.config_dir, self._config.workspace_dir)
        self._database_configurer(config_dir)
        provider = ConfigProvider(config_dir=config_dir)
        bundle = self._bootstrap_factory(config_provider=provider)
        server = self._server_factory(
            host=self._config.host,
            port=int(self._config.port),
            bundle=bundle,
            allow_remote_access=False,
            portal_mode="local_ops_console",
            public_base_url="",
            deployment_label="desktop-shell",
        )
        bound_host, bound_port = server.server_address[:2]
        self._url = build_start_url(str(bound_host or self._config.host), int(bound_port), self._config.start_path)
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="asl-desktop-web", daemon=True)
        self._thread.start()
        self._readiness_probe(self._url, self._config.readiness_timeout_seconds)
        return self._url

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None


def resolve_config_dir(raw_config_dir: str) -> str:
    raw = str(raw_config_dir or "config")
    path = Path(raw)
    if path.exists():
        return str(path)
    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) / raw if getattr(sys, "_MEIPASS", "") else None,
        Path(sys.executable).resolve().parent / raw if getattr(sys, "frozen", False) else None,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return str(candidate)
    return raw


def resolve_desktop_icon_path(raw_icon_path: str = "") -> str:
    raw = str(raw_icon_path or "").strip() or "assets/icons/app_icon.png"
    path = Path(raw).expanduser()
    candidates = [
        path,
        Path(getattr(sys, "_MEIPASS", "")) / raw if getattr(sys, "_MEIPASS", "") else None,
        Path(sys.executable).resolve().parent / raw if getattr(sys, "frozen", False) else None,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return str(candidate)
    return ""


def default_workspace_dir() -> Path:
    configured = os.environ.get("ASL_DESKTOP_WORKSPACE", "").strip()
    if configured:
        return Path(configured).expanduser()
    discovered_workspace = discover_existing_workspace()
    if discovered_workspace is not None:
        return discovered_workspace
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AndroidStabilityLab"
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base).expanduser() / "AndroidStabilityLab"
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    data_root = Path(xdg_data_home).expanduser() if xdg_data_home else Path.home() / ".local" / "share"
    return data_root / "AndroidStabilityLab"


def discover_existing_workspace() -> Path | None:
    candidates = [Path.cwd()]
    if getattr(sys, "frozen", False):
        candidates.extend(Path(sys.executable).resolve().parents)
    for candidate in candidates:
        if is_desktop_workspace(candidate):
            return candidate
    return None


def is_desktop_workspace(path: Path) -> bool:
    candidate = Path(path).expanduser()
    return (candidate / "config" / "database.json").exists() and (
        (candidate / "data").exists() or (candidate / "runtime").exists()
    )


def prepare_desktop_workspace(raw_config_dir: str, raw_workspace_dir: str) -> tuple[Path, Path]:
    workspace_root = Path(raw_workspace_dir).expanduser() if str(raw_workspace_dir or "").strip() else default_workspace_dir()
    workspace_root.mkdir(parents=True, exist_ok=True)
    target_config_dir = workspace_root / "config"
    target_config_dir.mkdir(parents=True, exist_ok=True)
    source_config_dir = Path(resolve_config_dir(raw_config_dir))
    if source_config_dir.exists():
        for source in source_config_dir.glob("*.json"):
            target = target_config_dir / source.name
            if not target.exists():
                shutil.copy2(source, target)
    (workspace_root / "data").mkdir(parents=True, exist_ok=True)
    (workspace_root / "runtime").mkdir(parents=True, exist_ok=True)
    os.chdir(workspace_root)
    return workspace_root, target_config_dir


def configure_desktop_database(config_dir: Path) -> None:
    try:
        import stability.infrastructure.persistence as persistence_module
        import stability.infrastructure.persistence.connection as connection_module
        from stability.infrastructure.persistence.connection import DatabaseConnectionManager
    except ModuleNotFoundError:
        return
    manager = DatabaseConnectionManager(config_file=str(config_dir / "database.json"))
    connection_module.db_manager = manager
    persistence_module.db_manager = manager


def build_start_url(host: str, port: int, start_path: str) -> str:
    normalized_path = str(start_path or "/").strip() or "/"
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    safe_path = quote(normalized_path, safe="/?=&%#:-._~")
    if host == "::1":
        host = "[::1]"
    return f"http://{host}:{int(port)}{safe_path}"


def wait_until_ready(url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + max(0.1, float(timeout_seconds or 10.0))
    parsed = urlsplit(url)
    health_url = urlunsplit((parsed.scheme, parsed.netloc, "/health", "", ""))
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=1.0) as response:  # noqa: S310 - local localhost probe
                if 200 <= int(response.status) < 500:
                    return
        except (OSError, URLError) as exc:
            last_error = exc
            time.sleep(0.1)
    if last_error is not None:
        raise RuntimeError(f"Embedded Web server did not become ready: {last_error}") from last_error
    raise RuntimeError("Embedded Web server did not become ready.")


def launch_desktop(config: DesktopLaunchConfig) -> int:
    try:
        import webview
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pywebview is not installed. Install desktop dependencies with: "
            "pip install -r requirements-desktop.txt"
        ) from exc

    runtime = DesktopPortalRuntime(config)
    url = runtime.start()
    atexit.register(runtime.stop)
    webview.create_window(
        config.title,
        url,
        width=max(900, int(config.width)),
        height=max(640, int(config.height)),
        confirm_close=True,
    )
    try:
        icon_path = resolve_desktop_icon_path(config.icon_path)
        webview.start(debug=bool(config.debug), icon=icon_path or None)
    finally:
        runtime.stop()
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch Android Stability Lab as a desktop app.")
    parser.add_argument("--host", default="127.0.0.1", help="Local host to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Local port. Use 0 for an available random port.")
    parser.add_argument("--config-dir", default="config", help="Config directory. Default: config")
    parser.add_argument(
        "--workspace-dir",
        default="",
        help="Writable desktop workspace. Default: current ASL workspace or OS application data directory.",
    )
    parser.add_argument("--start-path", default="/", help="Initial portal path, for example /tasks.")
    parser.add_argument("--title", default="Android Stability Lab", help="Desktop window title.")
    parser.add_argument("--width", type=int, default=1440, help="Initial window width.")
    parser.add_argument("--height", type=int, default=920, help="Initial window height.")
    parser.add_argument("--icon-path", default="", help="Desktop window icon path. Default: bundled app icon.")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug mode.")
    return parser


def config_from_args(args: argparse.Namespace) -> DesktopLaunchConfig:
    return DesktopLaunchConfig(
        host=str(args.host or "127.0.0.1"),
        port=int(args.port or 0),
        config_dir=str(args.config_dir or "config"),
        workspace_dir=str(args.workspace_dir or ""),
        start_path=str(args.start_path or "/"),
        title=str(args.title or "Android Stability Lab"),
        width=int(args.width or 1440),
        height=int(args.height or 920),
        icon_path=str(args.icon_path or ""),
        debug=bool(args.debug),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return launch_desktop(config_from_args(args))
