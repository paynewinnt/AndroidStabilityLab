from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from stability.desktop.launcher import (
    DesktopLaunchConfig,
    DesktopPortalRuntime,
    build_start_url,
    default_workspace_dir,
    discover_existing_workspace,
    is_desktop_workspace,
    resolve_desktop_icon_path,
    resolve_config_dir,
    wait_until_ready,
)


class _FakeServer:
    def __init__(self) -> None:
        self.server_address = ("127.0.0.1", 18030)
        self._closed = threading.Event()
        self.served = False
        self.shutdown_called = False
        self.server_close_called = False

    def serve_forever(self) -> None:
        self.served = True
        self._closed.wait(timeout=1.0)

    def shutdown(self) -> None:
        self.shutdown_called = True
        self._closed.set()

    def server_close(self) -> None:
        self.server_close_called = True


class _ReadyResponse:
    status = 200

    def __enter__(self) -> "_ReadyResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class DesktopLauncherTest(unittest.TestCase):
    def test_build_start_url_normalizes_path_and_ipv6_loopback(self) -> None:
        self.assertEqual(
            build_start_url("::1", 18030, "tasks?status=running"),
            "http://[::1]:18030/tasks?status=running",
        )

    def test_resolve_config_dir_prefers_existing_path(self) -> None:
        config_dir = Path("config")
        self.assertEqual(resolve_config_dir(str(config_dir)), str(config_dir))

    def test_resolve_desktop_icon_path_accepts_existing_path(self) -> None:
        icon_path = Path("assets/icons/androidmetrics_icon.png")
        self.assertEqual(resolve_desktop_icon_path(str(icon_path)), str(icon_path))

    def test_current_directory_workspace_is_default_workspace(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(is_desktop_workspace(Path.cwd()))
            self.assertEqual(default_workspace_dir(), Path.cwd())

    def test_packaged_app_discovers_workspace_from_executable_parent(self) -> None:
        repo_root = Path.cwd()
        fake_executable = repo_root / "dist" / "AndroidStabilityLab.app" / "Contents" / "MacOS" / "AndroidStabilityLab"
        with patch("stability.desktop.launcher.Path.cwd", return_value=Path("/tmp")):
            with patch("stability.desktop.launcher.sys.frozen", True, create=True):
                with patch("stability.desktop.launcher.sys.executable", str(fake_executable)):
                    self.assertEqual(discover_existing_workspace(), repo_root)

    def test_desktop_workspace_env_overrides_current_directory(self) -> None:
        configured = "/tmp/asl-desktop-workspace"
        with patch.dict("os.environ", {"ASL_DESKTOP_WORKSPACE": configured}, clear=True):
            self.assertEqual(default_workspace_dir(), Path(configured))

    def test_wait_until_ready_probes_root_health_endpoint(self) -> None:
        with patch("stability.desktop.launcher.urlopen", return_value=_ReadyResponse()) as probe:
            wait_until_ready("http://127.0.0.1:18030/tasks?status=running", 0.1)

        self.assertEqual(probe.call_args.args[0], "http://127.0.0.1:18030/health")

    def test_runtime_starts_local_server_and_stops_it(self) -> None:
        server = _FakeServer()
        calls: dict[str, object] = {}
        readiness_calls: list[tuple[str, float]] = []

        def bootstrap_factory(**kwargs: object) -> object:
            calls["bootstrap"] = dict(kwargs)
            return SimpleNamespace()

        def server_factory(**kwargs: object) -> _FakeServer:
            calls["server"] = dict(kwargs)
            return server

        runtime = DesktopPortalRuntime(
            DesktopLaunchConfig(port=0, start_path="/tasks", readiness_timeout_seconds=0.2),
            bootstrap_factory=bootstrap_factory,
            server_factory=server_factory,
            readiness_probe=lambda url, timeout: readiness_calls.append((url, timeout)),
            workspace_preparer=lambda *_: (Path.cwd(), Path("config")),
            database_configurer=lambda _: None,
        )

        url = runtime.start()
        runtime.stop()

        self.assertEqual(url, "http://127.0.0.1:18030/tasks")
        self.assertTrue(server.served)
        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.server_close_called)
        self.assertIn("bootstrap", calls)
        self.assertEqual(readiness_calls, [("http://127.0.0.1:18030/tasks", 0.2)])
        self.assertEqual(calls["server"]["host"], "127.0.0.1")
        self.assertEqual(calls["server"]["port"], 0)
        self.assertFalse(calls["server"]["allow_remote_access"])
        self.assertEqual(calls["server"]["portal_mode"], "local_ops_console")
        self.assertEqual(calls["server"]["deployment_label"], "desktop-shell")

    def test_runtime_rejects_non_local_host(self) -> None:
        runtime = DesktopPortalRuntime(
            DesktopLaunchConfig(host="0.0.0.0"),
            bootstrap_factory=lambda **_: SimpleNamespace(),
            server_factory=lambda **_: _FakeServer(),
            readiness_probe=lambda *_: None,
            workspace_preparer=lambda *_: (Path.cwd(), Path("config")),
            database_configurer=lambda _: None,
        )

        with self.assertRaises(ValueError):
            runtime.start()


if __name__ == "__main__":
    unittest.main()
