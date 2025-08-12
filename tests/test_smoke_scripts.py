from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class SmokeScriptContractTest(unittest.TestCase):
    def test_foreground_background_smoke_exercises_cli_e2e_flow(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_foreground_background_loop_smoke.sh"

        script = script_path.read_text(encoding="utf-8")

        self.assertIn("--template-type foreground_background_loop", script)
        self.assertIn("create-task", script)
        self.assertIn("create-run", script)
        self.assertIn("execute-run", script)
        self.assertIn("run_status", script)
        self.assertIn("first_instance_status", script)
        self.assertIn("report_path", script)

    def test_v1_acceptance_includes_foreground_background_smoke(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_v1_acceptance.sh"

        script = script_path.read_text(encoding="utf-8")

        self.assertIn("--run-foreground-background-smoke", script)
        self.assertIn("verify_foreground_background_loop_smoke.sh", script)
        self.assertIn("foreground_background_smoke", script)

    def test_web_tasks_foreground_background_smoke_uses_html_task_actions(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_web_tasks_foreground_background_smoke.sh"

        script = script_path.read_text(encoding="utf-8")

        self.assertIn("serve-web", script)
        self.assertIn("/tasks", script)
        self.assertIn("/tasks/actions/create-task", script)
        self.assertIn("/tasks/actions/create-run", script)
        self.assertIn("/tasks/actions/execute-run", script)
        self.assertIn("foreground_background_loop", script)
        self.assertIn("/api/runs/${RUN_ID}", script)

    def test_v1_acceptance_includes_web_tasks_foreground_background_smoke(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_v1_acceptance.sh"

        script = script_path.read_text(encoding="utf-8")

        self.assertIn("--run-web-foreground-background-smoke", script)
        self.assertIn("verify_web_tasks_foreground_background_smoke.sh", script)
        self.assertIn("web_foreground_background_smoke", script)

    def test_extended_device_cycle_smoke_scripts_exercise_cli_e2e_flow(self) -> None:
        expectations = {
            "verify_install_uninstall_loop_smoke.sh": "install_uninstall_loop",
            "verify_reboot_loop_smoke.sh": "reboot_loop",
            "verify_standby_wake_loop_smoke.sh": "standby_wake_loop",
        }

        for script_name, template_type in expectations.items():
            with self.subTest(script_name=script_name):
                script = (REPO_ROOT / "scripts" / script_name).read_text(encoding="utf-8")
                self.assertIn(f"--template-type {template_type}", script)
                self.assertIn("create-task", script)
                self.assertIn("create-run", script)
                self.assertIn("execute-run", script)
                self.assertIn("run_status", script)
                self.assertIn("first_instance_status", script)
                self.assertIn("report_path", script)

    def test_extended_device_cycle_web_smoke_scripts_use_html_task_actions(self) -> None:
        expectations = {
            "verify_web_tasks_install_uninstall_smoke.sh": "install_uninstall_loop",
            "verify_web_tasks_reboot_loop_smoke.sh": "reboot_loop",
            "verify_web_tasks_standby_wake_smoke.sh": "standby_wake_loop",
        }

        for script_name, template_type in expectations.items():
            with self.subTest(script_name=script_name):
                script = (REPO_ROOT / "scripts" / script_name).read_text(encoding="utf-8")
                self.assertIn("serve-web", script)
                self.assertIn("/tasks", script)
                self.assertIn("/tasks/actions/create-task", script)
                self.assertIn("/tasks/actions/create-run", script)
                self.assertIn("/tasks/actions/execute-run", script)
                self.assertIn(template_type, script)
                self.assertIn("/api/runs/${RUN_ID}", script)

    def test_v1_acceptance_includes_extended_device_cycle_smokes(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_v1_acceptance.sh"

        script = script_path.read_text(encoding="utf-8")

        for flag, script_name, step_name in (
            ("--run-install-uninstall-smoke", "verify_install_uninstall_loop_smoke.sh", "install_uninstall_smoke"),
            ("--run-web-install-uninstall-smoke", "verify_web_tasks_install_uninstall_smoke.sh", "web_install_uninstall_smoke"),
            ("--run-reboot-smoke", "verify_reboot_loop_smoke.sh", "reboot_smoke"),
            ("--run-web-reboot-smoke", "verify_web_tasks_reboot_loop_smoke.sh", "web_reboot_smoke"),
            ("--run-standby-wake-smoke", "verify_standby_wake_loop_smoke.sh", "standby_wake_smoke"),
            ("--run-web-standby-wake-smoke", "verify_web_tasks_standby_wake_smoke.sh", "web_standby_wake_smoke"),
        ):
            with self.subTest(flag=flag):
                self.assertIn(flag, script)
                self.assertIn(script_name, script)
                self.assertIn(step_name, script)

    def test_real_device_long_run_smoke_keeps_short_product_path_and_stability_entries(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_real_device_long_run_smoke.sh"

        script = script_path.read_text(encoding="utf-8")

        self.assertIn("foreground_background_loop", script)
        self.assertIn("standby_wake_loop", script)
        self.assertIn("create-task", script)
        self.assertIn("create-run", script)
        self.assertIn("execute-run", script)
        self.assertIn("configure-unattended-task", script)
        self.assertIn("run-unattended-round", script)
        self.assertIn("patrol-unattended-tasks", script)
        self.assertIn("run-unattended-patrol-runner", script)
        self.assertIn("executed_rounds", script)
        self.assertIn("--duration-minutes", script)
        self.assertIn("--run-hours", script)
        self.assertIn("--require-human-disconnect-check", script)
        self.assertIn("monitoring_snapshot_path", script)
        self.assertIn("issue_summary_count", script)
        self.assertIn("${BASE_URL}/tasks", script)
        self.assertIn("${BASE_URL}/runner", script)
        self.assertIn("${BASE_URL}/performance", script)

    def test_real_device_long_run_smoke_bash_syntax(self) -> None:
        script_path = REPO_ROOT / "scripts" / "verify_real_device_long_run_smoke.sh"

        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
