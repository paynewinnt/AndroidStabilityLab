from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode

from stability.app import DeviceService
from stability.domain import Device, DeviceAvailabilityState, DeviceConnectionState
from stability.infrastructure.device_adapter import DeviceDescriptor
from stability.repositories import InMemoryDeviceRepository
from stability.web import WebPortalApplication
from tests.helpers import web_portal as web_portal_helpers


class WebPortalDevicePoolsTest(unittest.TestCase):
    def test_device_pools_api_outputs_group_team_tag_summary(self) -> None:
        bundle = self._bundle()
        bundle.device_service = SimpleNamespace(
            list_device_summaries=lambda: [
                {
                    "device_id": "device-1",
                    "group_name": "lab-a",
                    "team": "checkout",
                    "tags": ["smoke", "android14"],
                    "is_online": True,
                    "is_schedulable": True,
                    "connection_state": "connected",
                    "availability_state": "idle",
                },
                {
                    "device_id": "device-2",
                    "group_name": "lab-a",
                    "team": "checkout",
                    "tags": ["smoke"],
                    "is_online": False,
                    "is_schedulable": False,
                    "connection_state": "offline",
                    "availability_state": "error",
                },
            ]
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/device-pools?group=lab-a&tag=smoke")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["pool_count"], 1)
        self.assertEqual(payload["summary"]["schedulable_device_count"], 1)
        self.assertEqual(payload["summary"]["unschedulable_reason_counts"]["offline"], 1)
        self.assertEqual(payload["pools"][0]["team"], "checkout")

    def test_device_pools_api_prefers_formal_device_service_methods(self) -> None:
        calls: list[object] = []

        def summarize_device_pools(*, group_by: str = "group") -> list[dict[str, object]]:
            calls.append(("summarize", group_by))
            return [{"key": "lab-a", "dimension": group_by, "total_count": 2, "online_count": 1}]

        def suggest_device_candidates(**kwargs: object) -> dict[str, object]:
            calls.append(("suggest", kwargs))
            return {
                "candidates": [
                    {
                        "device_id": "device-1",
                        "serial": "serial-1",
                        "display_name": "Pixel 8",
                        "schedulable": True,
                        "score": 80,
                        "profile": {"group_name": "lab-a", "team_name": "checkout", "tags": ["smoke"]},
                    }
                ],
                "rejected_candidates": [
                    {
                        "device_id": "device-2",
                        "serial": "serial-2",
                        "display_name": "Pixel 7",
                        "schedulable": False,
                        "reasons": ["offline"],
                        "profile": {"group_name": "lab-a", "team_name": "checkout", "tags": ["smoke"]},
                    }
                ],
            }

        bundle = self._bundle()
        bundle.device_service = SimpleNamespace(
            summarize_device_pools=summarize_device_pools,
            suggest_device_candidates=suggest_device_candidates,
            list_device_summaries=lambda: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request("/api/device-pools?group=lab-a&team=checkout&tag=smoke")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(
            [item for item in calls if item[0] == "summarize"],
            [("summarize", "group"), ("summarize", "team"), ("summarize", "tag")],
        )
        self.assertEqual(calls[-1][0], "suggest")
        self.assertEqual(calls[-1][1]["group_name"], "lab-a")
        self.assertEqual(calls[-1][1]["team_name"], "checkout")
        self.assertEqual(calls[-1][1]["tags"], ("smoke",))
        self.assertEqual(payload["summary"]["schedulable_device_count"], 1)
        self.assertEqual(payload["summary"]["unschedulable_reason_counts"]["offline"], 1)

    def test_device_pools_page_renders_user_facing_pool_view(self) -> None:
        bundle = self._bundle()
        bundle.device_service = SimpleNamespace(
            list_device_summaries=lambda: [
                {
                    "device_id": "device-1",
                    "group_name": "lab-a",
                    "team": "checkout",
                    "tags": ["smoke"],
                    "is_online": True,
                    "is_schedulable": True,
                    "connection_state": "connected",
                    "availability_state": "idle",
                }
            ]
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/device-pools")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("设备池", html)
        self.assertIn("lab-a / checkout", html)
        self.assertIn("/api/device-pools", html)
        self.assertIn("form-grid-three", html)
        self.assertIn("device-inline-form", html)
        self.assertIn("编辑标记", html)
        self.assertIn("name='device_id' value='device-1'", html)
        self.assertIn("/device-pools/actions/update-profile?as_session=", html)
        self.assertIn("device-detail-grid", html)
        self.assertIn("<span class='meta'>Tag</span><strong>smoke</strong>", html)
        self.assertIn("<span class='meta'>连接状态</span><strong>在线</strong>", html)
        self.assertIn("<span class='meta'>可用状态</span><strong>空闲</strong>", html)
        self.assertIn("当前没有不可调度设备", html)
        self.assertNotIn("<span class='meta'>不可调度原因</span><strong>n/a</strong>", html)
        self.assertNotIn("设备标记管理", html)
        self.assertNotIn("device-marking-form", html)
        self.assertNotIn("<div>tags：", html)
        self.assertNotIn("<div>不可调度原因：", html)

    def test_device_pool_marking_action_updates_group_team_and_tags(self) -> None:
        repository = InMemoryDeviceRepository()
        repository.add(
            Device(
                device_id="device-1",
                serial="serial-1",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            )
        )
        bundle = self._bundle()
        bundle.device_service = DeviceService(
            repository=repository,
            discovery_adapter=SimpleNamespace(list_devices=lambda include_unavailable=True: [], get_device=lambda serial: None),
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/device-pools/actions/update-profile",
            method="POST",
            content_type="application/x-www-form-urlencoded",
            body=urlencode(
                {
                    "device_id": "device-1",
                    "group_name": "lab-a",
                    "team_name": "android-client",
                    "tags": "smoke,android14",
                }
            ).encode("utf-8"),
            headers={"X-ASL-Session-Token": "asl.session.v1:tester:tester"},
        )

        html = body.decode("utf-8")
        updated = repository.get("device-1")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("已更新设备标记：device-1", html)
        self.assertEqual(updated.group_name, "lab-a")
        self.assertEqual(updated.metadata["team"], "android-client")
        self.assertEqual(updated.tags, ["android14", "smoke"])
        self.assertEqual(updated.metadata["profile_updated_by"], "tester")

    def test_device_pool_marking_form_carries_local_session_without_manual_headers(self) -> None:
        repository = InMemoryDeviceRepository()
        repository.add(
            Device(
                device_id="device-1",
                serial="serial-1",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            )
        )
        bundle = self._bundle()
        bundle.device_service = DeviceService(
            repository=repository,
            discovery_adapter=SimpleNamespace(list_devices=lambda include_unavailable=True: [], get_device=lambda serial: None),
        )
        app = WebPortalApplication(bundle)

        status, _, _ = app.handle_request(
            "/device-pools/actions/update-profile?as_session=asl.session.v1%3Atester%3Atester",
            method="POST",
            content_type="application/x-www-form-urlencoded",
            body=urlencode(
                {
                    "device_id": "device-1",
                    "group_name": "lab-b",
                    "team_name": "qa",
                    "tags": "regression",
                }
            ).encode("utf-8"),
        )

        updated = repository.get("device-1")
        self.assertEqual(status, 200)
        self.assertEqual(updated.group_name, "lab-b")
        self.assertEqual(updated.metadata["team"], "qa")
        self.assertEqual(updated.tags, ["regression"])

    def test_device_pool_page_renders_refresh_and_connect_actions(self) -> None:
        bundle = self._bundle()
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request("/device-pools")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("设备状态刷新", html)
        self.assertIn("刷新 ADB 设备", html)
        self.assertIn("连接并刷新", html)
        self.assertIn("第一次无线调试？先配对再连接", html)
        self.assertIn("配对地址和端口", html)
        self.assertIn("配对码", html)
        self.assertIn("连接地址和端口", html)
        self.assertIn("/device-pools/actions/refresh?as_session=", html)
        self.assertIn("/device-pools/actions/connect?as_session=", html)
        self.assertIn("/device-pools/actions/pair-connect?as_session=", html)

    def test_device_pool_refresh_action_syncs_adb_snapshot(self) -> None:
        repository = InMemoryDeviceRepository()
        bundle = self._bundle()
        bundle.device_service = DeviceService(
            repository=repository,
            discovery_adapter=SimpleNamespace(
                list_devices=lambda include_unavailable=True: [
                    DeviceDescriptor(serial="192.168.31.99:5555", status="device", model="Pixel")
                ],
                get_device=lambda serial: DeviceDescriptor(serial=serial, status="device", model="Pixel"),
            ),
        )
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request(
            "/device-pools/actions/refresh?as_session=asl.session.v1%3Atester%3Atester",
            method="POST",
            content_type="application/x-www-form-urlencoded",
            body=b"",
        )

        html = body.decode("utf-8")
        device = repository.get("192.168.31.99:5555")
        self.assertEqual(status, 200)
        self.assertIsNotNone(device)
        self.assertTrue(device.is_schedulable())
        self.assertIn("已刷新设备快照", html)
        self.assertIn("可调度设备", html)

    def test_device_pool_connect_action_connects_tcp_device_then_syncs(self) -> None:
        repository = InMemoryDeviceRepository()
        connect_calls: list[str] = []

        def get_device(serial: str) -> DeviceDescriptor | None:
            if serial in connect_calls:
                return DeviceDescriptor(serial=serial, status="device", model="Pixel")
            return None

        bundle = self._bundle()
        bundle.device_service = DeviceService(
            repository=repository,
            discovery_adapter=SimpleNamespace(
                list_devices=lambda include_unavailable=True: [],
                get_device=get_device,
                connect_device=lambda serial: connect_calls.append(serial)
                or {"attempted": True, "serial": serial, "success": True, "message": f"connected to {serial}"},
            ),
        )
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request(
            "/device-pools/actions/connect?as_session=asl.session.v1%3Atester%3Atester",
            method="POST",
            content_type="application/x-www-form-urlencoded",
            body=urlencode({"device_id": "192.168.31.99:5555"}).encode("utf-8"),
        )

        html = body.decode("utf-8")
        device = repository.get("192.168.31.99:5555")
        self.assertEqual(status, 200)
        self.assertEqual(connect_calls, ["192.168.31.99:5555"])
        self.assertIsNotNone(device)
        self.assertTrue(device.is_schedulable())
        self.assertIn("已尝试连接设备：192.168.31.99:5555 -> connected", html)

    def test_device_pool_pair_connect_action_pairs_then_connects_wireless_debugging_device(self) -> None:
        repository = InMemoryDeviceRepository()
        pair_calls: list[tuple[str, str]] = []
        connect_calls: list[str] = []

        def get_device(serial: str) -> DeviceDescriptor | None:
            if serial in connect_calls:
                return DeviceDescriptor(serial=serial, status="device", model="Honor")
            return None

        bundle = self._bundle()
        bundle.device_service = DeviceService(
            repository=repository,
            discovery_adapter=SimpleNamespace(
                list_devices=lambda include_unavailable=True: [],
                get_device=get_device,
                pair_device=lambda serial, code: pair_calls.append((serial, code))
                or {"attempted": True, "serial": serial, "success": True, "message": f"Successfully paired to {serial}"},
                connect_device=lambda serial: connect_calls.append(serial)
                or {"attempted": True, "serial": serial, "success": True, "message": f"connected to {serial}"},
            ),
        )
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request(
            "/device-pools/actions/pair-connect?as_session=asl.session.v1%3Atester%3Atester",
            method="POST",
            content_type="application/x-www-form-urlencoded",
            body=urlencode(
                {
                    "pair_device_id": "192.168.31.101:40539",
                    "pairing_code": "645916",
                    "connect_device_id": "192.168.31.101:42201",
                }
            ).encode("utf-8"),
        )

        html = body.decode("utf-8")
        device = repository.get("192.168.31.101:42201")
        self.assertEqual(status, 200)
        self.assertEqual(pair_calls, [("192.168.31.101:40539", "645916")])
        self.assertEqual(connect_calls, ["192.168.31.101:42201"])
        self.assertIsNotNone(device)
        self.assertTrue(device.is_schedulable())
        self.assertIn("已执行无线配对并连接：pair=ok / connect=ok", html)

    @staticmethod
    def _bundle(runner_status_override=None) -> object:
        return web_portal_helpers.bundle(runner_status_override=runner_status_override)


if __name__ == "__main__":
    unittest.main()
