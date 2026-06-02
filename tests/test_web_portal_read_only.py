from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability.app.doctor_service import DoctorCheck, DoctorReport
from stability.web import WebPortalApplication
from stability.web.manifest import platform_surface
from tests.helpers import web_portal as web_portal_helpers


class WebPortalReadOnlyPagesTest(unittest.TestCase):

    def test_home_page_renders_navigation_and_summary_content(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Web 首页", html)
        self.assertIn("任务大厅", html)
        self.assertIn("性能采样", html)
        self.assertIn("问题中心", html)
        self.assertIn("巡检状态", html)
        self.assertIn("Golden Suite", html)
        self.assertIn("准入中心", html)
        self.assertIn("Calculator Cold Start", html)
        self.assertIn("device_offline_default", html)
        self.assertIn("Golden Suite", html)
        self.assertIn("后台巡检", html)
        self.assertIn("Runner 摘要卡", html)
        self.assertIn("锁状态", html)
        self.assertIn("Heartbeat Age(s)", html)
        self.assertIn("最近执行任务", html)
        self.assertIn("最近性能采样", html)
        self.assertIn("backend summary", html)
        self.assertIn("backend=solox", html)
        self.assertIn("今日日报轮次", html)
        self.assertIn("今日日报失败轮次", html)
        self.assertIn("本周周报轮次", html)
        self.assertIn("本周周报失败轮次", html)
        self.assertIn("latest daily report", html)
        self.assertIn("latest weekly report", html)
        self.assertIn("继续查看完整巡检状态", html)
        self.assertIn("打开后台巡检状态页", html)
        self.assertIn("metric-ok", html)
        self.assertIn("metric-danger", html)
        self.assertIn("今日日报已经出现失败轮次或隔离设备", html)
        self.assertIn("打开 /runner", html)
        self.assertIn("查看 /api/runner", html)
        self.assertNotIn("可用 API", html)

    def test_home_page_shows_local_ops_console_notice_by_default(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("当前 Web 入口按本地运维控制台设计", html)

    def test_platform_page_renders_team_entry_boundary_summary(self) -> None:
        bundle = self._bundle()
        bundle.web_portal_config = {
            "mode": "team_entry",
            "bound_host": "127.0.0.1",
            "bound_port": 8030,
            "allow_remote_access": False,
            "public_base_url": "https://stability.example.internal",
            "deployment_label": "team-shared",
        }
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/platform")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("平台说明", html)
        self.assertIn("团队共享入口模式", html)
        self.assertIn("team-shared", html)
        self.assertIn("https://stability.example.internal", html)
        self.assertIn("admin-page-header", html)
        self.assertIn("平台定位", html)
        self.assertIn("面向 Android 稳定性验证和值班排障", html)
        self.assertIn("平台用途", html)
        self.assertIn("覆盖链路", html)
        self.assertIn("边界原则", html)
        self.assertIn("运行边界", html)
        self.assertIn("就绪检查", html)
        self.assertIn("安全与合同", html)
        self.assertIn("/ready", html)
        self.assertIn("/health", html)
        self.assertIn("/api/manifest", html)
        self.assertIn("/api/openapi.json", html)
        self.assertNotIn("不再重复提供各模块跳转入口", html)
        self.assertNotIn("左侧菜单是唯一主导航", html)
        self.assertNotIn("不作为二级导航中心", html)
        self.assertNotIn("核心使用链路", html)
        self.assertNotIn("JSON/API 入口", html)
        self.assertNotIn("写操作入口", html)
        self.assertNotIn("platform-pages-table", html)
        self.assertNotIn("platform-api-table", html)
        self.assertNotIn("platform-write-table", html)
        self.assertNotIn("页面与 API 清单", html)
        self.assertNotIn("<h3>页面入口</h3>", html)
        self.assertNotIn("<h3>API 入口</h3>", html)

    def test_doctor_page_and_api_render_diagnostics(self) -> None:
        fake_report = DoctorReport(
            generated_at="2025-07-29 10:00:00",
            ok=True,
            checks=(DoctorCheck(name="python", status="ok", summary="Python ok", details={"version": "3.12"}),),
            summary={"total": 1, "ok": 1, "warn": 0, "fail": 0, "skipped": 0},
        )
        app = WebPortalApplication(self._bundle())

        with patch("stability.web.features.core.payload.DoctorService") as service_class:
            service_class.return_value.run.return_value = fake_report
            html_status, html_type, html_body = app.handle_request("/doctor?device_id=dev-a&package_name=com.example")
            api_status, api_type, api_body = app.handle_request("/api/doctor?device_id=dev-a&package_name=com.example")

        self.assertEqual(html_status, 200)
        self.assertIn("text/html", html_type)
        html = html_body.decode("utf-8")
        self.assertIn("诊断中心", html)
        self.assertIn("单设备深度诊断", html)
        self.assertIn("python", html)
        self.assertEqual(api_status, 200)
        self.assertIn("application/json", api_type)
        payload = json.loads(api_body.decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["device_id"], "dev-a")
        self.assertEqual(payload["package_name"], "com.example")
        self.assertEqual(payload["checks"][0]["name"], "python")

    def test_home_page_highlights_remote_access_warning_when_enabled(self) -> None:
        bundle = self._bundle()
        bundle.web_portal_config = {
            "mode": "local_ops_console",
            "bound_host": "0.0.0.0",
            "bound_port": 8030,
            "allow_remote_access": True,
        }
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("已显式允许远程绑定到 0.0.0.0", html)
        self.assertIn("缺少正式认证、授权和审计边界", html)

    def test_home_page_highlights_daily_report_anomalies(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("今日日报失败轮次", html)
        self.assertIn("metric-danger", html)
        self.assertIn("今日日报已经出现失败轮次或隔离设备", html)
        self.assertIn("latest daily report：2025-07-22", html)
        self.assertIn("failed_rounds=1", html)
        self.assertIn("quarantined=1", html)

    def test_home_page_highlights_weekly_report_anomalies_when_daily_is_clean(self) -> None:
        base_runner = self._bundle().unattended_runner_service.show_status()
        runner_payload = dict(base_runner.__dict__)
        runner_payload["latest_daily_report"] = {
            **dict(base_runner.latest_daily_report),
            "failed_round_count": 0,
            "failed_rate": 0.0,
            "offline_rate": 0.0,
            "quarantined_device_count": 0,
        }
        runner_payload["latest_weekly_report"] = {
            **dict(base_runner.latest_weekly_report),
            "failed_round_count": 2,
            "failed_rate": 0.286,
            "offline_rate": 0.143,
            "quarantined_device_count": 1,
        }
        weekly_only_runner = SimpleNamespace(**runner_payload)
        app = WebPortalApplication(self._bundle(runner_status_override=weekly_only_runner))

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("latest weekly report：2025-W30", html)
        self.assertIn("active_days=3", html)
        self.assertIn("failed_rate=0.286", html)
        self.assertIn("offline_rate=0.143", html)
        self.assertIn("top_issue=device_offline=2", html)
        self.assertIn("metric-danger", html)
        self.assertIn("建议动作：本周周报已经累计失败轮次或隔离设备", html)
        self.assertIn("打开 /runner", html)
        self.assertIn("查看 /api/runner", html)

    def test_home_page_highlights_abnormal_runner_state(self) -> None:
        stale_runner = SimpleNamespace(
            observed_at="2025-07-22T20:10:00",
            root_dir="runtime/unattended_runner",
            lock_path="runtime/unattended_runner/runner.lock",
            heartbeat_path="runtime/unattended_runner/runner_status.json",
            lock_present=True,
            heartbeat_present=True,
            lock_state="stale",
            status="running",
            pid=4242,
            started_at="2025-07-22T20:00:00",
            finished_at=None,
            last_heartbeat_at="2025-07-22T19:00:00",
            heartbeat_age_seconds=3700,
            stale_after_seconds=300,
            is_stale=True,
            interval_seconds=60,
            max_iterations=0,
            task_id="task-unattended-1",
            force=False,
            cycle_count=4,
            active_cycle_index=5,
            stopped_reason="",
            last_patrol={
                "generated_at": "2025-07-22T19:00:00",
                "executed_task_count": 0,
                "quarantined_device_count": 2,
            },
        )
        app = WebPortalApplication(self._bundle(runner_status_override=stale_runner))

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("metric-danger", html)
        self.assertIn("metric-warning", html)
        self.assertIn("stale", html)
        self.assertIn("确认 stale lock", html)
        self.assertIn("打开 /runner", html)
        self.assertIn("查看 /api/runner", html)

    def test_home_page_gracefully_handles_baseline_without_latest_audit(self) -> None:
        bundle = self._bundle_with_missing_latest_audit()
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Web 首页", html)
        self.assertIn("device_offline_audit_auto_smoke", html)

    def test_goldens_api_returns_case_listing(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/goldens")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["case_count"], 2)
        self.assertEqual(payload["summary"]["layer_count"], 2)
        self.assertEqual(payload["cases"][0]["case_id"], "crash_regroup_ignore_raw_key")

    def test_golden_case_detail_api_returns_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/goldens/case/crash_regroup_ignore_raw_key")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["case_id"], "crash_regroup_ignore_raw_key")
        self.assertEqual(payload["summary"]["layer"], "merge_semantics")
        self.assertEqual(payload["expected"]["change_summary"]["regrouped"], 1)

    def test_golden_diff_api_returns_diff_summary(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request(
            "/api/goldens/diff?left_path=config/rule_replay_golden_samples.json&right_path=/tmp/golden-right.json"
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertTrue(payload["comparison_ready"])
        self.assertEqual(payload["summary"]["diff_count"], 2)
        self.assertEqual(payload["summary"]["total_diff_count"], 2)
        self.assertEqual(payload["summary"]["change_counts"]["modified"], 1)
        self.assertEqual(payload["entries"][0]["case_id"], "crash_regroup_ignore_raw_key")
        self.assertEqual(payload["entries"][0]["field_diff_summary"][0]["field"], "description")
        self.assertEqual(payload["entries"][0]["block_diff_summary"][0]["key"], "baseline_rules")
        self.assertEqual(payload["entries"][0]["block_diff_summary"][0]["left_status"], "present")

    def test_golden_diff_api_filters_by_change_type(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, _, body = app.handle_request(
            "/api/goldens/diff?left_path=config/rule_replay_golden_samples.json&right_path=/tmp/golden-right.json&change_type=added"
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["filters"]["change_type"], "added")
        self.assertEqual(payload["summary"]["diff_count"], 1)
        self.assertEqual(payload["summary"]["total_diff_count"], 2)
        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["case_id"], "diff_smoke_added_case")

    def test_golden_diff_api_filters_by_case_query(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, _, body = app.handle_request(
            "/api/goldens/diff?left_path=config/rule_replay_golden_samples.json&right_path=/tmp/golden-right.json&case_query=crash_regroup"
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["filters"]["case_query"], "crash_regroup")
        self.assertEqual(payload["summary"]["diff_count"], 1)
        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["case_id"], "crash_regroup_ignore_raw_key")

    def test_golden_diff_api_filters_by_changed_field(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, _, body = app.handle_request(
            "/api/goldens/diff?left_path=config/rule_replay_golden_samples.json&right_path=/tmp/golden-right.json&changed_field=description"
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["filters"]["changed_field"], "description")
        self.assertEqual(payload["summary"]["diff_count"], 1)
        self.assertEqual(payload["summary"]["total_diff_count"], 2)
        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["case_id"], "crash_regroup_ignore_raw_key")

    def test_runner_api_returns_heartbeat_and_lock_summary(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/runner")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["page"], "runner")
        self.assertEqual(payload["summary"]["status"], "running")
        self.assertEqual(payload["summary"]["lock_state"], "active")
        self.assertEqual(payload["summary"]["cycle_count"], 4)
        self.assertEqual(payload["summary"]["latest_patrol_severity"], "严重")
        self.assertEqual(payload["summary"]["daily_report_date"], "2025-07-22")
        self.assertEqual(payload["summary"]["daily_report_round_count"], 4)
        self.assertEqual(payload["summary"]["weekly_report_week_key"], "2025-W30")
        self.assertEqual(payload["summary"]["weekly_report_round_count"], 7)
        self.assertEqual(payload["summary"]["weekly_report_failed_round_count"], 2)
        self.assertEqual(payload["summary"]["weekly_report_active_day_count"], 3)
        self.assertEqual(payload["runner"]["task_id"], "task-unattended-1")
        self.assertEqual(payload["runner"]["latest_daily_report"]["round_count"], 4)
        self.assertEqual(payload["runner"]["latest_weekly_report"]["week_key"], "2025-W30")
        self.assertIn("report_json_path", payload["runner"]["daily_report_paths"])
        self.assertIn("report_json_path", payload["runner"]["weekly_report_paths"])
        self.assertEqual(payload["last_patrol"]["executed_task_count"], 2)
        self.assertEqual(payload["last_patrol"]["severity"]["level"], "critical")
        self.assertEqual(payload["filters"]["patrol_filter"], "")
        self.assertEqual(payload["filters"]["severity_filter"], "")
        self.assertEqual(payload["filters"]["history_count_total"], 3)
        self.assertEqual(payload["filters"]["history_count_filtered"], 3)
        self.assertEqual(payload["filters"]["filter_counts"]["failed"], 1)
        self.assertEqual(payload["filters"]["filter_counts"]["offline"], 2)
        self.assertEqual(payload["filters"]["filter_counts"]["quarantined"], 1)
        self.assertEqual(payload["filters"]["severity_counts"]["normal"], 1)
        self.assertEqual(payload["filters"]["severity_counts"]["medium"], 1)
        self.assertEqual(payload["filters"]["severity_counts"]["high"], 0)
        self.assertEqual(payload["filters"]["severity_counts"]["critical"], 1)
        self.assertEqual(payload["latest_patrol_relation"]["status"], "anomalous")
        self.assertEqual(payload["latest_patrol_relation"]["cycle_index"], 4)
        self.assertEqual(payload["latest_patrol_relation"]["labels"], ["失败", "掉线", "隔离"])
        self.assertEqual(payload["latest_patrol_relation"]["severity"]["level"], "critical")
        self.assertEqual(payload["latest_patrol_relation"]["severity"]["label"], "严重")
        self.assertEqual(
            payload["latest_patrol_relation"]["impact_message"],
            "任务影响范围：task_count=2 / due_task_count=1 / executed_task_count=2 / skipped_task_count=1",
        )
        self.assertIn("/api/long-run-templates", payload["long_run_templates"]["api_path"])
        self.assertEqual(len(payload["recent_patrols"]), 3)
        self.assertEqual(payload["recent_patrols"][-1]["cycle_index"], 4)
        self.assertEqual(payload["recent_patrols"][0]["severity"]["level"], "normal")
        self.assertEqual(payload["recent_patrols"][1]["severity"]["level"], "medium")
        self.assertEqual(payload["recent_patrols"][2]["severity"]["level"], "critical")

    def test_long_run_templates_api_prefers_service_templates_and_plan(self) -> None:
        calls: list[object] = []
        bundle = self._bundle()
        bundle.unattended_service = SimpleNamespace()
        bundle.unattended_service.list_long_run_templates = lambda: calls.append("list") or [
            {
                "template_id": "service_soak",
                "name": "Service Soak",
                "default_template_type": "monkey",
                "default_interval_minutes": 15,
                "default_max_rounds": 4,
                "recommended_device_count": 1,
                "recommended_rotation_strategy": "round_robin",
            }
        ]
        bundle.unattended_service.plan_long_run_template = (
            lambda template_key, *, overrides: calls.append(("plan", template_key, overrides))
            or {
                "template_key": template_key,
                "effective_defaults": {"interval_minutes": overrides["interval_minutes"]},
                "overrides": overrides,
            }
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/long-run-templates?template_key=service_soak&override=interval_minutes=45"
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls[0], "list")
        self.assertEqual(calls[1], ("plan", "service_soak", {"interval_minutes": 45}))
        self.assertEqual(payload["source"], "service")
        self.assertEqual(payload["template"]["template_id"], "service_soak")
        self.assertEqual(payload["template"]["template_key"], "service_soak")
        self.assertEqual(payload["template"]["defaults"]["interval_minutes"], 15)
        self.assertIn("interval_minutes", payload["template"]["overridable_parameters"])
        self.assertNotIn("session_token", payload["current_actor"])
        self.assertNotIn("session_id", payload["current_actor"])
        self.assertEqual(payload["plan"]["effective_defaults"]["interval_minutes"], 45)

    def test_long_run_templates_api_calls_service_build_plan_with_overrides(self) -> None:
        calls: list[object] = []
        bundle = self._bundle()
        bundle.unattended_service = SimpleNamespace()
        bundle.unattended_service.list_long_run_templates = lambda: calls.append("list") or [
            {
                "template_key": "service_soak",
                "name": "Service Soak",
                "defaults": {"interval_minutes": 15, "desired_device_count": 1},
                "overridable_parameters": ["interval_minutes", "task_name"],
            }
        ]

        def build_long_run_plan(template_id: str, **kwargs: object) -> dict[str, object]:
            calls.append(("build", template_id, kwargs))
            return {
                "template_key": template_id,
                "source": "build",
                "effective_defaults": {"interval_minutes": kwargs["interval_minutes"]},
                "overrides": kwargs,
            }

        bundle.unattended_service.build_long_run_plan = build_long_run_plan
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/long-run-templates?template_key=service_soak&override=interval_minutes=45&override=task_name=Nightly%20Soak"
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls[0], "list")
        self.assertEqual(
            calls[1],
            ("build", "service_soak", {"interval_minutes": 45}),
        )
        self.assertEqual(payload["source"], "service")
        self.assertEqual(payload["plan"]["source"], "build")
        self.assertEqual(payload["plan"]["effective_defaults"]["interval_minutes"], 45)

    def test_long_run_templates_page_and_manifest_expose_entry(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/long-run-templates")
        html = body.decode("utf-8")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("长稳运行模板", html)
        self.assertIn("/api/long-run-templates", html)
        self.assertIn("soak_2h", html)
        self.assertIn("预览计划", html)
        self.assertIn("/long-run-templates?template_key=soak_2h&amp;preview_only=1", html)
        self.assertIn("data-file-preview-link='1'", html)
        self.assertIn("套用创建任务", html)
        self.assertIn("/tasks?long_run_template=soak_2h", html)
        self.assertIn("去 Runner 配置", html)
        self.assertIn("类型", html)
        self.assertIn("间隔", html)
        self.assertIn("中文解释", html)
        self.assertIn("作用", html)
        self.assertIn("两小时快速长稳", html)

        _, _, manifest_body = app.handle_request("/api/manifest")
        manifest = json.loads(manifest_body.decode("utf-8"))
        self.assertIn("/api/long-run-templates", [item["path"] for item in manifest["read_endpoints"]])
        self.assertIn("/long-run-templates", [item["path"] for item in manifest["pages"]])

    def test_long_run_template_preview_only_page_omits_template_list(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/long-run-templates?template_key=soak_2h&preview_only=1")
        html = body.decode("utf-8")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("模板计划预览", html)
        self.assertIn("soak_2h", html)
        self.assertIn("name='preview_only' value='1'", html)
        self.assertNotIn("模板列表", html)
        self.assertNotIn("long-run-templates-admin-table", html)

    def test_tasks_page_can_apply_long_run_template_defaults(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request(
            "/tasks?long_run_template=soak_2h&override=package_name=com.example.demo&override=task_name=Demo%20Long%20Run"
        )
        html = body.decode("utf-8")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("data-task-auto-open='long-run-task'", html)
        self.assertIn("已套用长稳模板", html)
        self.assertIn("value='Demo Long Run'", html)
        self.assertIn("value='com.example.demo'", html)
        self.assertIn("name='runtime_hours' value='2'", html)
        self.assertIn("name='interval_minutes' value='30'", html)
        self.assertIn("name='desired_device_count' value='1'", html)
        self.assertIn("name='long_run_template_key' value='soak_2h'", html)

    def test_runner_api_filters_failed_patrol_rounds(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/runner?patrol_filter=failed")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["filters"]["patrol_filter"], "failed")
        self.assertEqual(payload["filters"]["history_count_total"], 3)
        self.assertEqual(payload["filters"]["history_count_filtered"], 1)
        self.assertEqual(len(payload["recent_patrols"]), 1)
        self.assertEqual(payload["recent_patrols"][0]["cycle_index"], 4)

    def test_runner_api_filters_patrol_rounds_by_severity(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/runner?severity_filter=critical")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["filters"]["patrol_filter"], "")
        self.assertEqual(payload["filters"]["severity_filter"], "critical")
        self.assertEqual(payload["filters"]["history_count_total"], 3)
        self.assertEqual(payload["filters"]["history_count_filtered"], 1)
        self.assertEqual(len(payload["recent_patrols"]), 1)
        self.assertEqual(payload["recent_patrols"][0]["cycle_index"], 4)
        self.assertEqual(payload["recent_patrols"][0]["severity"]["level"], "critical")

    def test_runner_page_renders_status_and_last_patrol(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/runner")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("后台巡检状态", html)
        self.assertIn("Runner 状态", html)
        self.assertIn("锁状态", html)
        self.assertIn("最新异常严重度", html)
        self.assertIn("严重", html)
        self.assertIn("Latest Daily Report", html)
        self.assertIn("Latest Weekly Report", html)
        self.assertIn("日报日期", html)
        self.assertIn("周键", html)
        self.assertIn("unattended-config-form", html)
        self.assertIn("unattended-config-grid", html)
        self.assertIn("unattended-device-grid", html)
        self.assertIn("name='backup_devices'", html)
        self.assertIn("2025-W30", html)
        self.assertIn("周报活跃天数", html)
        self.assertIn("周报隔离设备", html)
        self.assertIn("失败轮次", html)
        self.assertIn("最新心跳关联提示", html)
        self.assertIn("最新心跳对应的最新 patrol 第 4 轮 仍属于异常轮次", html)
        self.assertIn("异常严重度分层", html)
        self.assertIn("已出现隔离设备，或失败已伴随任务跳过", html)
        self.assertIn("任务影响范围：task_count=2 / due_task_count=1 / executed_task_count=2 / skipped_task_count=1", html)
        self.assertIn("跳到失败轮次过滤", html)
        self.assertIn("最近一轮 Patrol", html)
        self.assertIn("最近 Patrol 历史", html)
        self.assertIn("异常轮次快捷入口", html)
        self.assertIn("一键看失败轮次 (1)", html)
        self.assertIn("一键看掉线轮次 (2)", html)
        self.assertIn("一键看隔离轮次 (1)", html)
        self.assertIn("history 过滤", html)
        self.assertIn("严重度过滤", html)
        self.assertIn("全部严重度", html)
        self.assertIn("严重 (1)", html)
        self.assertIn("失败轮次", html)
        self.assertIn("掉线轮次", html)
        self.assertIn("隔离轮次", html)
        self.assertIn("中", html)
        self.assertIn("本周周报已经累计失败轮次或隔离设备", html)
        self.assertIn("周任务摘要", html)
        self.assertIn("Interruption Rounds", html)
        self.assertIn("offline=1", html)
        self.assertIn("quarantined=1", html)
        self.assertIn("展开异常详情", html)
        self.assertIn("probe_attempts", html)
        self.assertIn("Cycle", html)
        self.assertIn("task-unattended-1", html)
        self.assertIn("runner.lock", html)
        self.assertIn("running", html)
        self.assertIn("active", html)

    def test_goldens_pages_render_listing_and_detail(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/goldens")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Golden Suite", html)
        self.assertIn("Golden Cases", html)
        self.assertIn("crash_regroup_ignore_raw_key", html)
        self.assertIn("/goldens/case/crash_regroup_ignore_raw_key", html)

        status, content_type, body = app.handle_request("/goldens/case/crash_regroup_ignore_raw_key")
        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Golden Case", html)
        self.assertIn("Baseline Rules", html)
        self.assertIn("Candidate Rules", html)
        self.assertIn("Dataset", html)
        self.assertIn("返回 Golden Suite", html)

    def test_goldens_diff_page_renders_summary_and_links(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request(
            "/goldens/diff?left_path=config/rule_replay_golden_samples.json&right_path=/tmp/golden-right.json"
        )

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Golden Suite Diff", html)
        self.assertIn("Diff 过滤", html)
        self.assertIn("搜索 case_id", html)
        self.assertIn("全部字段", html)
        self.assertIn("description", html)
        self.assertIn("字段差异摘要", html)
        self.assertIn("Crash regroup case [candidate]", html)
        self.assertIn("展开关键块摘要", html)
        self.assertIn("Baseline Rules", html)
        self.assertIn("Candidate Rules", html)
        self.assertIn("Filters", html)
        self.assertIn("Expected", html)
        self.assertIn("Changed Cases", html)
        self.assertIn("crash_regroup_ignore_raw_key", html)
        self.assertIn("查看 Left Case", html)
        self.assertIn("查看 Right Case", html)

    def test_tasks_api_returns_json_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/tasks")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["task_count"], 1)
        self.assertEqual(payload["summary"]["run_count"], 1)
        self.assertEqual(payload["summary"]["monitored_run_count"], 1)
        self.assertEqual(payload["summary"]["trace_run_count"], 1)
        self.assertEqual(payload["runs"][0]["run_id"], "run-1")
        self.assertEqual(payload["runs"][0]["monitoring_summary"]["sample_count"], 1)
        self.assertEqual(payload["runs"][0]["monitoring_summary"]["trace_count"], 1)
        self.assertEqual(payload["runs"][0]["monitoring_summary"]["backend_counts"]["solox"], 1)
        self.assertEqual(payload["runs"][0]["detail_path"], "/runs/run-1")

    def test_tasks_page_renders_monitoring_visibility(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/tasks")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("有监控 Run", html)
        self.assertIn("带 Trace Run", html)
        self.assertIn("backend=solox", html)
        self.assertIn("Run 详情", html)
        self.assertIn("Run JSON", html)
        self.assertIn("href='/runs'><strong>Run</strong>", html)
        self.assertIn("Run 列表", html)
        self.assertIn("产物列表", html)
        self.assertIn("data-file-preview-title='Run JSON'", html)
        self.assertIn("file-preview-modal", html)
        self.assertIn("href='/artifacts'><strong>产物</strong>", html)
        self.assertIn(
            "href='/artifacts/run/run-1' data-file-preview-link='1' data-file-preview-title='产物'",
            html,
        )
        self.assertNotIn("href='/json-api'><strong>产物</strong>", html)

    def test_runs_page_renders_run_list(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/runs")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Run 列表", html)
        self.assertIn("Calculator Cold Start", html)
        self.assertIn(
            "href='/runs/run-1' data-file-preview-link='1' data-file-preview-title='查看详情'",
            html,
        )
        self.assertIn(
            "href='/artifacts/run/run-1' data-file-preview-link='1' data-file-preview-title='产物'",
            html,
        )
        self.assertIn("data-file-preview-title='Run JSON'", html)
        self.assertIn("href='/runs'><strong>Run</strong>", html)

    def test_runs_api_returns_run_list_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/runs")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["page"], "runs")
        self.assertEqual(payload["summary"]["run_count"], 1)
        self.assertEqual(payload["summary"]["monitored_run_count"], 1)
        self.assertEqual(payload["runs"][0]["detail_path"], "/runs/run-1")

    def test_artifacts_page_renders_run_artifact_list(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/artifacts")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("产物中心", html)
        self.assertIn("Run 产物列表", html)
        self.assertIn("Calculator Cold Start", html)
        self.assertIn(
            "href='/artifacts/run/run-1' data-file-preview-link='1' data-file-preview-title='查看详情'",
            html,
        )
        self.assertIn(
            "href='/runs/run-1' data-file-preview-link='1' data-file-preview-title='Run 详情'",
            html,
        )
        self.assertIn("data-file-preview-title='Run JSON'", html)
        self.assertIn("报告", html)
        self.assertIn("Trace", html)

    def test_artifacts_api_returns_run_artifact_summary(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/artifacts")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["page"], "artifacts")
        self.assertEqual(payload["summary"]["run_count"], 1)
        self.assertEqual(payload["summary"]["report_count"], 1)
        self.assertEqual(payload["summary"]["trace_count"], 1)
        self.assertEqual(payload["summary"]["monitoring_snapshot_count"], 1)
        self.assertEqual(payload["items"][0]["artifact_path"], "/artifacts/run/run-1")

    def test_run_detail_api_returns_monitoring_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/runs/run-1")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["run"]["run_id"], "run-1")
        self.assertEqual(payload["run"]["monitoring_summary"]["sample_count"], 1)
        self.assertEqual(payload["run"]["instances"][0]["monitoring"]["backend"], "solox")
        self.assertEqual(payload["run"]["instances"][0]["monitoring"]["metrics"]["fps"], 58.0)
        self.assertTrue(payload["run"]["instances"][0]["monitoring"]["trace_available"])

    def test_run_detail_page_renders_monitoring_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/runs/run-1")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Run 详情", html)
        self.assertIn("Monitoring Overview", html)
        self.assertIn("backend=solox", html)
        self.assertIn("Execution Instances", html)
        self.assertIn("key metrics", html)
        self.assertIn("/artifacts/run/run-1", html)
        self.assertIn("返回 Run 列表", html)
        self.assertIn("返回任务大厅", html)
        self.assertIn("返回任务详情", html)
        self.assertIn("查看 Run 产物", html)
        self.assertIn("data-file-preview-title='Run JSON'", html)

    def test_run_artifacts_page_groups_report_trace_monitoring_and_issues(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/artifacts/run/run-1")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Run 产物", html)
        self.assertIn("任务 -> Run -> 性能 -> 产物", html)
        self.assertIn("返回产物列表", html)
        self.assertIn("返回 Run 列表", html)
        self.assertIn("返回任务大厅", html)
        self.assertIn("返回 Run 详情", html)
        self.assertIn("返回任务详情", html)
        self.assertIn("Report", html)
        self.assertIn("Trace", html)
        self.assertIn("Monitoring Snapshot", html)
        self.assertIn("Issue Summary", html)
        self.assertIn("Snapshot JSON", html)
        self.assertIn("data-file-preview-title='Snapshot JSON'", html)
        self.assertIn("startup_timeout", html)

    def test_run_artifacts_api_returns_grouped_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/artifacts/run/run-1")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["page"], "run_artifacts")
        self.assertEqual(payload["summary"]["report_count"], 1)
        self.assertEqual(payload["summary"]["trace_count"], 1)
        self.assertEqual(payload["summary"]["monitoring_snapshot_count"], 1)
        self.assertEqual(payload["issues"][0]["exit_reason"], "startup_timeout")

    def test_performance_api_returns_recent_monitoring_summary(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/performance")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["sample_count"], 1)
        self.assertEqual(payload["summary"]["trace_count"], 1)
        self.assertEqual(payload["summary"]["backend_counts"]["solox"], 1)
        self.assertEqual(payload["entries"][0]["backend"], "solox")
        self.assertEqual(payload["entries"][0]["metrics"]["memory_pss"], 256.0)
        self.assertIn("threshold_source", payload["risk_detail_fields"])

    def test_tasks_page_create_form_lists_extended_template_options(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/tasks")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("foreground_background_loop", html)
        self.assertIn("install_uninstall_loop", html)
        self.assertIn("reboot_loop", html)
        self.assertIn("standby_wake_loop", html)
        self.assertIn("cold_start_loop - 冷启动循环", html)
        self.assertIn("monkey - Monkey 稳定性", html)
        self.assertIn("foreground_background_loop - 前后台切换", html)
        self.assertIn("default - 基础 ADB 快照", html)
        self.assertIn("solox - 实时性能采样", html)
        self.assertIn("perfetto - 系统 Trace", html)
        self.assertIn("long-run-monitoring-grid", html)
        self.assertIn("long-run-monitoring-controls", html)
        self.assertIn("task-create-layout", html)
        self.assertIn("task-create-target", html)
        self.assertIn("task-create-metrics", html)
        self.assertIn("task-target-controls", html)
        self.assertIn("基础信息", html)
        self.assertIn("执行目标", html)
        self.assertIn("监控指标", html)
        self.assertIn("参数表单", html)
        self.assertIn("form-grid-three", html)
        self.assertIn("form-field-wide", html)
        self.assertIn("task-operation-hub", html)
        self.assertIn("task-operation-button", html)
        self.assertIn("data-task-modal-target='long-run-task'", html)
        self.assertIn("data-task-modal-target='standard-task'", html)
        self.assertIn("data-task-modal-target='create-run'", html)
        self.assertIn("data-task-modal-target='execute-run'", html)
        self.assertIn("task-modal-long-run-task", html)
        self.assertIn("task-list-split", html)
        self.assertIn("task-list-panel", html)
        self.assertIn("不物理删除，只从默认列表隐藏并记录审计事件。", html)
        self.assertIn("归档并隐藏", html)
        self.assertIn("归档隐藏", html)
        self.assertIn("closeTaskModal", html)
        self.assertNotIn("task-run-actions", html)
        self.assertIn("device-choice-grid", html)
        self.assertIn("device-choice-card", html)
        self.assertIn("name='devices' value='192.168.31.99:5555'", html)
        self.assertIn("name='sampling_interval' value='5' min='0'", html)
        self.assertIn("metric-choice-grid", html)
        self.assertIn("metric-choice-card", html)
        self.assertIn("name='metrics' value='cpu' checked", html)
        self.assertIn("name='metrics' value='memory' checked", html)
        self.assertIn("name='metrics' value='fps'", html)
        self.assertIn("name='metrics' value='gpu'", html)
        self.assertIn("name='metrics' value='trace'", html)
        self.assertIn("name='metrics' value='network'", html)
        self.assertIn("name='metrics' value='battery'", html)
        self.assertNotIn("<label>指标<input", html)
        self.assertIn("json-param-help", html)
        self.assertIn("查看参数", html)
        self.assertIn("name='task_params'", html)
        self.assertIn("data-task-param-key='loop_count'", html)
        self.assertIn("data-apk-manager='1'", html)
        self.assertIn("data-apk-upload-button='1'", html)
        self.assertIn("上传 APK", html)
        self.assertIn("data-apk-delete-button='1'", html)
        self.assertIn("已管理 APK", html)
        self.assertIn("data-apk-select='1'", html)
        self.assertIn("data-apk-upload-url=", html)
        self.assertIn("data-apk-delete-url=", html)
        self.assertIn("data-task-param-key='apk_path'", html)
        self.assertIn("asl.managedApks.v1", html)
        self.assertIn("setupApkManager", html)
        self.assertIn("cold_start_loop 冷启动", html)
        self.assertIn("event_count", html)
        self.assertIn("automation_mode / execution_mode", html)
        self.assertIn("data-template-scope='cold_start_loop'", html)
        self.assertIn("data-template-scope='monkey'", html)
        self.assertIn("data-template-scope='foreground_background_loop'", html)
        self.assertIn("applyTemplateHelpFilter", html)
        self.assertIn("data-task-param-builder", html)
        self.assertIn("task-param-builder-section", html)
        self.assertIn("data-task-param-key='loop_count'", html)
        self.assertIn("data-task-param-key='event_count'", html)
        self.assertIn("syncTaskParamsBuilder", html)
        self.assertIn("JSON.stringify(payload, null, 2)", html)
        self.assertIn("select[name=\"template_type\"]", html)
        self.assertIn("label:has(input[required]", html)
        self.assertIn('content:"必填"', html)
        self.assertIn("validateRequiredGroups", html)
        self.assertIn("name='task_name' value='' placeholder='例如 首页冷启动回归' required", html)
        self.assertIn("name='package_name' value='' placeholder='com.example.app' required", html)
        self.assertIn("<label>模板<select name='template_type' required>", html)
        self.assertIn("<label>任务<select name='task_id' required>", html)
        self.assertIn("data-required-group='1' data-required-message='请至少选择一台设备。'", html)
        self.assertIn("source", html)
        self.assertIn("build_id", html)
        self.assertNotIn("name='devices' value='192.168.31.99:5555' required", html)
        self.assertNotIn("select name='devices' multiple", html)
        self.assertNotIn("device-multi-select", html)
        self.assertIn("自动调度（不指定设备）", html)
        self.assertIn("执行时按设备池选择", html)
        self.assertIn("Magic / 未分组 / 未分配", html)
        self.assertIn("可勾选一台或多台", html)
        self.assertIn("必须勾选至少一台可调度设备", html)
        self.assertIn("Calculator Cold Start / cold_start_loop - 冷启动循环 / com.hihonor.calculator / id:task-1 / 2025-07-20 09:00", html)
        self.assertIn("cold_start_loop", html)
        self.assertIn("冷启动循环", html)
        self.assertIn("重复启动 App，观察启动耗时/崩溃", html)
        self.assertIn("2025-07-20 09:00:00", html)
        self.assertIn("2025-07-20 09:01:00", html)
        self.assertIn("定义要测什么 App、用什么模板、可选哪些设备。", html)
        self.assertIn("基于某个任务生成一次具体执行批次。", html)
        self.assertIn("真正开始跑，并选择 monitoring backend、并发、重试等执行参数。", html)

        detail_app = WebPortalApplication(self._writable_bundle())
        status, content_type, body = detail_app.handle_request("/tasks/task/task-1")
        detail_html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("基于当前任务创建 Run", detail_html)
        self.assertIn("目标设备", detail_html)
        self.assertIn("device-choice-card", detail_html)
        self.assertIn("返回任务大厅", detail_html)
        self.assertNotIn("目标设备<input", detail_html)

    def test_json_api_menu_page_renders_html_index(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/json-api?page_size=50")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("JSON API", html)
        self.assertNotIn("接口中心先给你展示可读入口", html)
        self.assertNotIn("不会再直接弹出一大串 JSON", html)
        self.assertIn("打开 JSON", html)
        self.assertIn("/api/platform", html)
        self.assertIn("/api/manifest", html)
        self.assertIn("/api/openapi.json", html)
        self.assertIn("/api/home", html)
        self.assertIn("/api/admission/cases", html)
        self.assertIn("/api/integration/outbox", html)
        self.assertIn("curl http://127.0.0.1:8030/api/platform", html)
        self.assertIn("curl http://127.0.0.1:8030/api/manifest", html)
        self.assertIn("curl http://127.0.0.1:8030/api/home", html)
        self.assertIn("evidence_signals", html)
        self.assertIn("confidence_score", html)
        self.assertIn("recommended_next_steps", html)
        self.assertIn("threshold_source", html)

    def test_platform_api_returns_boundary_and_surface_manifest(self) -> None:
        bundle = self._bundle()
        bundle.web_portal_config = {
            "mode": "team_entry",
            "bound_host": "127.0.0.1",
            "bound_port": 8030,
            "allow_remote_access": False,
            "public_base_url": "https://stability.example.internal",
            "deployment_label": "team-shared",
        }
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/platform")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["deployment"]["mode"], "team_entry")
        self.assertEqual(payload["deployment"]["public_base_url"], "https://stability.example.internal")
        self.assertTrue(payload["write_boundary"]["shared_read_surface"])
        self.assertTrue(payload["identity_capabilities"]["local_session"])
        self.assertTrue(payload["identity_capabilities"]["trusted_sso_header"])
        self.assertIn("X-ASL-SSO-Provider", payload["identity_capabilities"]["trusted_sso_headers"])
        self.assertIn("X-ASL-External-Subject", payload["identity_capabilities"]["trusted_sso_required_headers"])
        self.assertIn("/api/platform", [item["path"] for item in payload["surface"]["api_endpoints"]])
        self.assertIn("/api/platform-health", [item["path"] for item in payload["surface"]["api_endpoints"]])
        self.assertIn("/api/manifest", [item["path"] for item in payload["surface"]["api_endpoints"]])
        self.assertEqual(payload["callback_contract"]["contract_version"], "asl.webhook_callback.v1")
        self.assertIn("/ready", [item["path"] for item in payload["surface"]["api_endpoints"]])

    def test_platform_health_api_returns_persisted_snapshot_contract(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/platform-health")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["contract_version"], "asl.platform_health.v1")
        self.assertIn(payload["status"], {"ready", "degraded", "blocked"})
        self.assertIn("checks", payload)
        self.assertIn("readiness", payload)

    def test_api_manifest_returns_formal_api_contract(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/manifest")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["contract_version"], "asl.api_manifest.v1")
        self.assertEqual(payload["api_version"], "v1")
        self.assertIn("/api/openapi.json", [item["path"] for item in payload["read_endpoints"]])
        self.assertIn("/api/rules", [item["path"] for item in payload["read_endpoints"]])
        self.assertIn("/api/admission/reports/<baseline_key>", [item["path"] for item in payload["read_endpoints"]])
        self.assertEqual(payload["callback_contract"]["contract_version"], "asl.webhook_callback.v1")
        self.assertEqual(payload["rule_entrypoint_contract"]["write_policy"], "preview_only_no_config_write")
        self.assertIn("evidence_signals", payload["advanced_anomaly_fields"]["issue_fields"])
        self.assertIn("confidence_score", payload["advanced_anomaly_fields"]["attribution_fields"])
        self.assertIn("recommended_next_steps", payload["advanced_anomaly_fields"]["attribution_fields"])
        self.assertIn("threshold_source", payload["advanced_anomaly_fields"]["performance_risk_fields"])

    def test_api_surfaces_use_shared_manifest(self) -> None:
        app = WebPortalApplication(self._bundle())
        expected = platform_surface()

        _, _, manifest_body = app.handle_request("/api/manifest")
        _, _, platform_body = app.handle_request("/api/platform")
        _, _, home_body = app.handle_request("/api/home")

        manifest = json.loads(manifest_body.decode("utf-8"))
        platform = json.loads(platform_body.decode("utf-8"))
        home = json.loads(home_body.decode("utf-8"))
        self.assertEqual(expected["pages"], manifest["pages"])
        self.assertEqual(expected["api_endpoints"], manifest["read_endpoints"])
        self.assertEqual(expected["write_actions"], [{key: item[key] for key in ("label", "path", "description")} for item in manifest["write_endpoints"]])
        self.assertEqual(expected["pages"], platform["surface"]["pages"])
        self.assertEqual(expected["api_endpoints"], platform["surface"]["api_endpoints"])
        self.assertEqual(expected["api_endpoints"], home["api_endpoints"])

    def test_openapi_endpoint_returns_spec_like_payload(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/openapi.json")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["openapi"], "3.1.0")
        self.assertIn("/api/manifest", payload["paths"])
        self.assertIn("/api/rules", payload["paths"])
        self.assertIn("/api/admission/reports/<baseline_key>", payload["paths"])
        self.assertIn("/api/tasks/actions/create-task", payload["paths"])
        self.assertEqual(payload["x-asl-manifest-version"], "asl.api_manifest.v1")

    def test_performance_page_renders_recent_monitoring_summary(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/performance")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("性能采样", html)
        self.assertIn("返回任务大厅", html)
        self.assertIn("href='/runs'><strong>Run</strong>", html)
        self.assertIn("href='/artifacts'><strong>产物</strong>", html)
        self.assertIn("sidebar-nav", html)
        self.assertIn("class='active'>性能采样</a>", html)
        self.assertNotIn('<section class="hero">', html)
        self.assertIn("三步上手", html)
        self.assertIn("list-runs", html)
        self.assertIn("execute-run --run-id &lt;run_id&gt; --monitoring-backend solox", html)
        self.assertIn("compare-performance-trends --help", html)
        self.assertIn("性能风险解释字段", html)
        self.assertIn("threshold_source", html)
        self.assertIn("Backend 分布", html)
        self.assertIn("性能趋势图", html)
        self.assertIn("任务性能趋势", html)
        self.assertIn("performance-task-panel", html)
        self.assertIn("任务性能趋势图", html)
        self.assertIn("查看具体性能数据", html)
        self.assertIn("Backend 分布图", html)
        self.assertIn("performance-chart-grid", html)
        self.assertIn("performance-line-chart", html)
        self.assertIn("performance-bar-row", html)
        self.assertIn("performance-mini-bars", html)
        self.assertIn("最近监控快照", html)
        self.assertIn("solox", html)
        self.assertIn("Snapshot JSON", html)
        self.assertIn("Trace", html)

    def test_health_endpoint_returns_ok(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/health")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertTrue(payload["ok"])

    def test_ready_endpoint_returns_platform_readiness(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/ready")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "local_ops_console")
        self.assertTrue(payload["readiness"]["checks"]["quality_gate"])
        self.assertEqual(payload["deployment_label"], "Android Stability Lab")

    @staticmethod
    def _bundle(runner_status_override=None) -> object:
        return web_portal_helpers.bundle(runner_status_override=runner_status_override)

    @staticmethod
    def _writable_bundle() -> object:
        return web_portal_helpers.writable_bundle()

    @staticmethod
    def _bundle_with_missing_latest_audit() -> object:
        return web_portal_helpers.bundle_with_missing_latest_audit()
