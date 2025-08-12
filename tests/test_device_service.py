from __future__ import annotations

import unittest

from stability.app import DeviceService
from stability.domain import Device, DeviceAvailabilityState, DeviceConnectionState
from stability.infrastructure.device_adapter import DeviceDescriptor, DeviceDiscoveryAdapter
from stability.repositories import InMemoryDeviceRepository


class _NullDiscoveryAdapter(DeviceDiscoveryAdapter):
    def list_devices(self, include_unavailable: bool = False):
        return []

    def get_device(self, serial: str):
        return None


class _ConnectDiscoveryAdapter(DeviceDiscoveryAdapter):
    def __init__(self) -> None:
        self.connect_calls: list[str] = []
        self.pair_calls: list[tuple[str, str]] = []

    def list_devices(self, include_unavailable: bool = False):
        return []

    def get_device(self, serial: str):
        if serial in self.connect_calls:
            return DeviceDescriptor(serial=serial, status="device", model="Pixel")
        return None

    def connect_device(self, serial: str):
        self.connect_calls.append(serial)
        return {"attempted": True, "success": True, "message": f"connected to {serial}"}

    def pair_device(self, serial: str, pairing_code: str):
        self.pair_calls.append((serial, pairing_code))
        return {"attempted": True, "success": True, "message": f"Successfully paired to {serial}"}


class DeviceServiceTeamPoolTest(unittest.TestCase):
    def test_describe_device_profile_reads_team_scheduling_metadata(self) -> None:
        service = self._build_service(
            [
                Device(
                    device_id="device-1",
                    serial="serial-1",
                    group_name="cn-lab",
                    tags=["smoke", "pixel"],
                    metadata={
                        "team": "payments",
                        "owner": "qa-a",
                        "priority": "8",
                        "capabilities": "monkey,cold_start",
                        "maintenance": True,
                        "maintenance_reason": "usb hub replacement",
                        "reserved_by": "nightly",
                    },
                )
            ]
        )

        profile = service.describe_device_profile(service.require_device("device-1"))
        summary = service.describe_device(service.require_device("device-1"))

        self.assertEqual(profile.group_name, "cn-lab")
        self.assertEqual(profile.team_name, "payments")
        self.assertEqual(profile.owner, "qa-a")
        self.assertEqual(profile.priority, 8)
        self.assertEqual(profile.capabilities, ("cold_start", "monkey"))
        self.assertTrue(profile.maintenance)
        self.assertEqual(profile.maintenance_reason, "usb hub replacement")
        self.assertFalse(summary["is_schedulable"])
        self.assertEqual(summary["team_name"], "payments")
        self.assertEqual(summary["capabilities"], ["cold_start", "monkey"])

    def test_summarize_device_pools_groups_counts_and_risk_devices(self) -> None:
        service = self._build_service(
            [
                self._device(
                    "device-idle",
                    group_name="lab-a",
                    tags=["smoke"],
                    metadata={"team": "payments", "capabilities": ["monkey"]},
                ),
                self._device(
                    "device-running",
                    group_name="lab-a",
                    availability_state=DeviceAvailabilityState.RUNNING,
                    tags=["regression"],
                    metadata={"team": "payments"},
                ),
                self._device(
                    "device-quarantined",
                    group_name="lab-b",
                    availability_state=DeviceAvailabilityState.QUARANTINED,
                    tags=["smoke"],
                    metadata={"team": "search", "quarantine_reason": "flaky usb"},
                ),
                self._device(
                    "device-maintenance",
                    group_name="lab-b",
                    tags=["smoke"],
                    metadata={"team": "search", "maintenance": True},
                ),
            ]
        )

        by_group = {item.key: item for item in service.summarize_device_pools(group_by="group")}
        by_team = {item.key: item for item in service.summarize_device_pools(group_by="team")}
        by_tag = {item.key: item for item in service.summarize_device_pools(group_by="tag")}

        self.assertEqual(by_group["lab-a"].total_count, 2)
        self.assertEqual(by_group["lab-a"].schedulable_device_ids, ("device-idle",))
        self.assertEqual(by_group["lab-a"].running_count, 1)
        self.assertEqual(by_group["lab-b"].quarantined_count, 1)
        self.assertEqual(by_group["lab-b"].maintenance_count, 1)
        self.assertEqual(by_group["lab-b"].risk_device_ids, ("device-maintenance", "device-quarantined"))
        self.assertEqual(by_team["payments"].online_count, 2)
        self.assertEqual(by_tag["smoke"].total_count, 3)
        self.assertEqual(by_tag["smoke"].schedulable_device_ids, ("device-idle",))

    def test_suggest_device_candidates_explains_unschedulable_devices(self) -> None:
        service = self._build_service(
            [
                self._device(
                    "device-best",
                    group_name="lab-a",
                    tags=["smoke", "pixel"],
                    metadata={"team": "payments", "capabilities": ["monkey", "cold_start"], "priority": 9},
                ),
                self._device(
                    "device-offline",
                    group_name="lab-a",
                    connection_state=DeviceConnectionState.OFFLINE,
                    availability_state=DeviceAvailabilityState.ERROR,
                    tags=["smoke", "pixel"],
                    metadata={"team": "payments", "capabilities": ["monkey", "cold_start"], "priority": 10},
                ),
                self._device(
                    "device-reserved",
                    group_name="lab-a",
                    availability_state=DeviceAvailabilityState.RESERVED,
                    tags=["smoke", "pixel"],
                    metadata={"team": "payments", "capabilities": ["monkey", "cold_start"], "priority": 8},
                ),
                self._device(
                    "device-maintenance",
                    group_name="lab-a",
                    tags=["smoke", "pixel"],
                    metadata={"team": "payments", "capabilities": ["monkey", "cold_start"], "maintenance": True},
                ),
                self._device(
                    "device-tag-mismatch",
                    group_name="lab-a",
                    tags=["regression"],
                    metadata={"team": "payments", "capabilities": ["monkey", "cold_start"]},
                ),
                self._device(
                    "device-capability-mismatch",
                    group_name="lab-a",
                    tags=["smoke", "pixel"],
                    metadata={"team": "payments", "capabilities": ["monkey"]},
                ),
                self._device(
                    "device-team-mismatch",
                    group_name="lab-a",
                    tags=["smoke", "pixel"],
                    metadata={"team": "search", "capabilities": ["monkey", "cold_start"]},
                ),
                self._device(
                    "device-group-mismatch",
                    group_name="lab-b",
                    tags=["smoke", "pixel"],
                    metadata={"team": "payments", "capabilities": ["monkey", "cold_start"]},
                ),
            ]
        )

        plan = service.suggest_device_candidates(
            group_name="lab-a",
            team_name="payments",
            tags=["smoke", "pixel"],
            capabilities=["cold_start"],
            requested_count=1,
        )
        rejected = {item.device_id: item.reasons for item in plan.rejected_candidates}

        self.assertTrue(plan.has_capacity)
        self.assertEqual(plan.selected_device_ids, ("device-best",))
        self.assertEqual([item.device_id for item in plan.candidates], ["device-best"])
        self.assertIn("offline", rejected["device-offline"])
        self.assertIn("reserved", rejected["device-reserved"])
        self.assertIn("maintenance", rejected["device-maintenance"])
        self.assertIn("tag_mismatch", rejected["device-tag-mismatch"])
        self.assertIn("capability_mismatch", rejected["device-capability-mismatch"])
        self.assertIn("team_mismatch", rejected["device-team-mismatch"])
        self.assertIn("group_mismatch", rejected["device-group-mismatch"])

    def test_update_device_profile_persists_group_team_tags_and_audit_metadata(self) -> None:
        service = self._build_service(
            [
                self._device(
                    "device-1",
                    group_name="",
                    tags=[],
                    metadata={},
                )
            ]
        )

        updated = service.update_device_profile(
            "device-1",
            group_name="lab-a",
            team_name="android-client",
            tags="smoke, android14, smoke",
            actor="tester",
        )

        profile = service.describe_device_profile(updated)
        self.assertEqual(profile.group_name, "lab-a")
        self.assertEqual(profile.team_name, "android-client")
        self.assertEqual(profile.tags, ("android14", "smoke"))
        self.assertEqual(updated.metadata["profile_updated_by"], "tester")
        self.assertIn("profile_updated_at", updated.metadata)

    def test_connect_device_invokes_adapter_and_syncs_online_device(self) -> None:
        repository = InMemoryDeviceRepository()
        adapter = _ConnectDiscoveryAdapter()
        service = DeviceService(repository=repository, discovery_adapter=adapter)

        result = service.connect_device("192.168.31.99:5555")

        synced = repository.get("192.168.31.99:5555")
        self.assertEqual(adapter.connect_calls, ["192.168.31.99:5555"])
        self.assertTrue(result.attempted)
        self.assertTrue(result.connected)
        self.assertIsNotNone(synced)
        self.assertTrue(synced.is_schedulable())

    def test_pair_and_connect_device_pairs_then_syncs_online_device(self) -> None:
        repository = InMemoryDeviceRepository()
        adapter = _ConnectDiscoveryAdapter()
        service = DeviceService(repository=repository, discovery_adapter=adapter)

        result = service.pair_and_connect_device(
            pair_serial="192.168.31.101:40539",
            pairing_code="645916",
            connect_serial="192.168.31.101:42201",
        )

        synced = repository.get("192.168.31.101:42201")
        self.assertEqual(adapter.pair_calls, [("192.168.31.101:40539", "645916")])
        self.assertEqual(adapter.connect_calls, ["192.168.31.101:42201"])
        self.assertTrue(result.paired)
        self.assertTrue(result.connected)
        self.assertIsNotNone(synced)
        self.assertTrue(synced.is_schedulable())

    @staticmethod
    def _build_service(devices: list[Device]) -> DeviceService:
        repository = InMemoryDeviceRepository()
        for device in devices:
            repository.add(device)
        return DeviceService(repository=repository, discovery_adapter=_NullDiscoveryAdapter())

    @staticmethod
    def _device(
        device_id: str,
        *,
        group_name: str,
        connection_state: DeviceConnectionState = DeviceConnectionState.ONLINE,
        availability_state: DeviceAvailabilityState = DeviceAvailabilityState.IDLE,
        tags: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Device:
        return Device(
            device_id=device_id,
            serial=device_id,
            connection_state=connection_state,
            availability_state=availability_state,
            group_name=group_name,
            tags=list(tags or []),
            metadata=dict(metadata or {}),
        )


if __name__ == "__main__":
    unittest.main()
