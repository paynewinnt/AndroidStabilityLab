from __future__ import annotations

import importlib
import unittest


_SPLIT_MODULES = (
    "tests.test_cli_execution_commands",
    "tests.test_cli_device_task_run_commands",
    "tests.test_cli_unattended_commands",
    "tests.test_cli_analysis_commands",
    "tests.test_cli_analysis_rule_commands",
    "tests.test_cli_admission_rule_replay_commands",
    "tests.test_cli_rule_review_report_commands",
    "tests.test_cli_web_integration_commands",
    "tests.test_cli_ci_integration_commands",
)


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    if pattern is not None:
        # Discovery loads the split modules directly; keep this facade empty to avoid duplicates.
        return unittest.TestSuite()

    suite = unittest.TestSuite()
    for module_name in _SPLIT_MODULES:
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(module_name)))
    return suite


if __name__ == "__main__":
    unittest.main()
