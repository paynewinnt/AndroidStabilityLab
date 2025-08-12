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
            },
        )

        bundle = create_v1_bootstrap(config_provider=provider)

        self.assertEqual(str(bundle.integration_outbox_service._root_dir), "tmp-runtime/outbox")
        self.assertEqual(bundle.integration_outbox_service._retry_delay, 11)
        self.assertEqual(str(bundle.run_execution_service._artifact_planner.runtime_root), "tmp-runtime")


if __name__ == "__main__":
    unittest.main()
