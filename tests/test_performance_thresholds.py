from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from stability.infrastructure import FileBackedPerformanceRiskThresholdProvider


class FileBackedPerformanceRiskThresholdProviderTest(unittest.TestCase):
    def test_loads_defaults_and_scoped_overrides(self) -> None:
        with TemporaryDirectory() as tempdir:
            config_path = Path(tempdir) / "thresholds.json"
            config_path.write_text(
                """
{
  "defaults": {
    "oom_memory_pss_peak_mb": 2048,
    "fps_drop_ratio": 0.25
  },
  "overrides": [
    {
      "source": "performance_thresholds.foreground",
      "template_type": "foreground_background_loop",
      "memory_growth_min_delta_mb": 64,
      "memory_growth_min_ratio": 0.1
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )

            config = FileBackedPerformanceRiskThresholdProvider(config_path).load()
            default_match = config.resolve({"template_type": "cold_start_loop"})
            override_match = config.resolve({"template_type": "foreground_background_loop"})

            self.assertEqual(default_match.values.oom_memory_pss_peak_mb, 2048.0)
            self.assertEqual(default_match.values.fps_drop_ratio, 0.25)
            self.assertEqual(override_match.threshold_source, "performance_thresholds.foreground")
            self.assertEqual(override_match.matched_scope, {"template_type": "foreground_background_loop"})
            self.assertEqual(override_match.values.memory_growth_min_delta_mb, 64.0)
            self.assertEqual(override_match.values.memory_growth_min_ratio, 0.1)


if __name__ == "__main__":
    unittest.main()
