from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability import create_v1_bootstrap
from stability.app import ConfigProvider


class ConfigProviderTest(unittest.TestCase):
    def test_env_overrides_file_and_defaults_for_core_config(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "platform.json").write_text(
                json.dumps(
                    {
                        "runtime": {"root": "file-runtime"},
                        "web": {"host": "0.0.0.0", "port": 9000},
                        "outbox": {"dead_letter_threshold": 9},
                    }
                ),
                encoding="utf-8",
            )

            provider = ConfigProvider(
                config_dir=config_dir,
                env={
                    "ASL_RUNTIME_ROOT": "env-runtime",
                    "ASL_WEB_PORT": "9100",
                    "ASL_OUTBOX_DEAD_LETTER_THRESHOLD": "7",
                },
                overrides={"web.host": "127.0.0.2"},
            )

            self.assertEqual(str(provider.runtime_paths().root), "env-runtime")
            self.assertEqual(provider.web().host, "127.0.0.2")
            self.assertEqual(provider.web().port, 9100)
            self.assertEqual(provider.outbox().dead_letter_threshold, 7)

    def test_monitoring_and_thresholds_wrap_existing_file_backed_providers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "monitoring.json").write_text(
                json.dumps({"monitoring": {"backend": "solox", "fallback_backend": "disabled"}}),
                encoding="utf-8",
            )
            thresholds_path = config_dir / "thresholds.json"
            thresholds_path.write_text(
                json.dumps({"defaults": {"memory_growth_min_delta_mb": 64}}),
                encoding="utf-8",
            )

            provider = ConfigProvider(
                config_dir=config_dir,
                env={"ASL_PERFORMANCE_RISK_THRESHOLDS_CONFIG": str(thresholds_path)},
            )

            monitoring = provider.monitoring_settings()
            thresholds = provider.performance_risk_thresholds()

            self.assertEqual(monitoring.backend, "solox")
            self.assertEqual(monitoring.fallback_backend, "disabled")
            self.assertEqual(thresholds.defaults.memory_growth_min_delta_mb, 64)

    def test_in_memory_bootstrap_uses_runtime_and_outbox_config(self) -> None:
        provider = ConfigProvider(
            env={},
            overrides={
                "runtime.root": "tmp-runtime",
                "outbox.root_dir": "tmp-runtime/outbox",
                "outbox.retry_delay_seconds": 11,
                "platform_health.alert_min_severity": "warn",
                "quality_gate.review_warnings_max": 2,
            },
        )

        bundle = create_v1_bootstrap(config_provider=provider)

        self.assertEqual(str(bundle.integration_outbox_service._root_dir), "tmp-runtime/outbox")
        self.assertEqual(bundle.integration_outbox_service._retry_delay, 11)
        self.assertEqual(str(bundle.run_execution_service._artifact_planner.runtime_root), "tmp-runtime")
        self.assertEqual(bundle.platform_health_service._thresholds.alert_min_severity, "warn")
        self.assertEqual(bundle.quality_gate_service._policy.review_warnings_max, 2)

    def test_platform_health_thresholds_read_from_platform_config(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "platform.json").write_text(
                json.dumps(
                    {
                        "platform_health": {
                            "alert_min_severity": "warn",
                            "trend_window_hours": 12,
                            "device_online_rate_min": 0.8,
                            "run_failure_rate_max": 0.2,
                            "instance_failure_rate_max": 0.3,
                            "artifact_failure_rate_max": 0.1,
                            "outbox_dead_letter_max": 2,
                        }
                    }
                ),
                encoding="utf-8",
            )

            thresholds = ConfigProvider(config_dir=config_dir, env={}).platform_health()

        self.assertEqual(thresholds.alert_min_severity, "warn")
        self.assertEqual(thresholds.trend_window_hours, 12)
        self.assertEqual(thresholds.device_online_rate_min, 0.8)
        self.assertEqual(thresholds.run_failure_rate_max, 0.2)
        self.assertEqual(thresholds.instance_failure_rate_max, 0.3)
        self.assertEqual(thresholds.artifact_failure_rate_max, 0.1)
        self.assertEqual(thresholds.outbox_dead_letter_max, 2)

    def test_platform_health_env_and_overrides_take_priority(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "platform.json").write_text(
                json.dumps(
                    {
                        "platform_health": {
                            "alert_min_severity": "fail",
                            "trend_window_hours": 24,
                        }
                    }
                ),
                encoding="utf-8",
            )

            thresholds = ConfigProvider(
                config_dir=config_dir,
                env={"ASL_PLATFORM_HEALTH_TREND_WINDOW_HOURS": "6"},
                overrides={"platform_health.alert_min_severity": "warn"},
            ).platform_health()

        self.assertEqual(thresholds.alert_min_severity, "warn")
        self.assertEqual(thresholds.trend_window_hours, 6)

    def test_quality_gate_policy_reads_platform_config_and_priority_overrides(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "platform.json").write_text(
                json.dumps(
                    {
                        "quality_gate": {
                            "rule_version": "quality-gate-v2",
                            "review_warnings_max": 1,
                            "min_golden_suite_case_count": 2,
                            "scoped_overrides": [
                                {
                                    "name": "smoke",
                                    "match": {"package_name": "com.example.app"},
                                    "values": {"review_warnings_max": 3},
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            policy = ConfigProvider(
                config_dir=config_dir,
                env={
                    "ASL_QUALITY_GATE_HIGH_RISK_FAMILY_HIGH_SEVERITY_MIN": "5",
                    "ASL_QUALITY_GATE_MIN_GOLDEN_SUITE_CASE_COUNT": "4",
                },
                overrides={"quality_gate.review_warnings_max": 2},
            ).quality_gate_policy()

        self.assertEqual(policy.rule_version, "quality-gate-v2")
        self.assertEqual(policy.review_warnings_max, 2)
        self.assertEqual(policy.high_risk_family_high_severity_min, 5)
        self.assertEqual(policy.min_golden_suite_case_count, 4)
        self.assertEqual(len(policy.scoped_overrides), 1)


if __name__ == "__main__":
    unittest.main()
