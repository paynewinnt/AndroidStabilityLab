from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from stability import bootstrap
from stability.domain import TaskTemplateType
from stability.scenario import (
    ColdStartLoopScenarioRunner,
    CustomAutomationScenarioRunner,
    ForegroundBackgroundLoopScenarioRunner,
    InstallUninstallLoopScenarioRunner,
    MonkeyScenarioRunner,
    RebootLoopScenarioRunner,
    StandbyWakeLoopScenarioRunner,
)


class BootstrapMonitoringTest(unittest.TestCase):
    def test_default_scenario_runners_cover_all_task_templates(self) -> None:
        runners = bootstrap.build_default_scenario_runners()

        self.assertEqual(set(runners), {item.value for item in TaskTemplateType})
        self.assertIsInstance(runners["monkey"], MonkeyScenarioRunner)
        self.assertIsInstance(runners["cold_start_loop"], ColdStartLoopScenarioRunner)
        self.assertIsInstance(runners["foreground_background_loop"], ForegroundBackgroundLoopScenarioRunner)
        self.assertIsInstance(runners["install_uninstall_loop"], InstallUninstallLoopScenarioRunner)
        self.assertIsInstance(runners["reboot_loop"], RebootLoopScenarioRunner)
        self.assertIsInstance(runners["standby_wake_loop"], StandbyWakeLoopScenarioRunner)
        self.assertIsInstance(runners["custom"], CustomAutomationScenarioRunner)

    def test_build_persistent_monitoring_adapter_loads_config_and_applies_override(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "monitoring.json"
            path.write_text(
                json.dumps(
                    {
                        "monitoring": {
                            "backend": "solox",
                            "fallback_backend": "adb_collector",
                        }
                    }
                ),
                encoding="utf-8",
            )
            marker = object()

            with patch("stability.bootstrap.build_monitoring_adapter", return_value=(marker, "solox")) as builder:
                adapter, backend = bootstrap._build_persistent_monitoring_adapter(
                    monitoring_backend="auto",
                    monitoring_config_path=path,
                )

        self.assertIs(adapter, marker)
        self.assertEqual(backend, "solox")
        self.assertEqual(builder.call_args.kwargs["requested_backend"], "auto")
        self.assertEqual(builder.call_args.kwargs["settings"].backend, "solox")
        self.assertEqual(builder.call_args.kwargs["settings"].fallback_backend, "adb_collector")


if __name__ == "__main__":
    unittest.main()
