from __future__ import annotations

from html import escape
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from stability.domain import AppError, normalize_app_error
from stability.web import payloads as portal_payloads
from stability.web.application_common import WebPortalApplication, bind_web_portal_application
from stability.web.request_context import (
    REQUIRED_TRUSTED_SSO_CLAIMS,
    TRUSTED_SSO_HEADERS,
    WRITABLE_IDENTITY_FORM_FIELDS,
    request_id_from_headers,
)
from stability.web.routes import (
    API_ADMISSION_BASELINE_PREFIX,
    API_ADMISSION_CASE_PREFIX,
    API_ADMISSION_REPORT_PREFIX,
    API_ARCHIVE_TASK_ROUTES,
    API_CONFIGURE_UNATTENDED_ROUTES,
    API_CREATE_RUN_ROUTES,
    API_CREATE_TASK_ROUTES,
    API_EXECUTE_RUN_ROUTES,
    API_GOLDEN_CASE_PREFIX,
    API_PATROL_UNATTENDED_ROUTES,
    API_RELEASE_SUBMISSION_DETAIL_PREFIX,
    API_REPLAY_DEAD_LETTERS_ROUTES,
    API_RUN_ARTIFACTS_PREFIX,
    API_RUN_DETAIL_PREFIX,
    API_RUN_INTEGRATION_WORKER_ROUTES,
    API_RUN_UNATTENDED_ROUND_ROUTES,
    API_SYNC_CI_DECISIONS_ROUTES,
    API_TASK_DETAIL_PREFIX,
    API_UNATTENDED_DETAIL_PREFIX,
    HTML_ADMISSION_BASELINE_PREFIX,
    HTML_ARCHIVE_TASK_ROUTES,
    HTML_CONFIGURE_UNATTENDED_ROUTES,
    HTML_CREATE_RUN_ROUTES,
    HTML_CREATE_TASK_ROUTES,
    HTML_EXECUTE_RUN_ROUTES,
    HTML_GOLDEN_CASE_PREFIX,
    HTML_PATROL_UNATTENDED_ROUTES,
    HTML_REPLAY_DEAD_LETTERS_ROUTES,
    HTML_RUN_ARTIFACTS_PREFIX,
    HTML_RUN_DETAIL_PREFIX,
    HTML_RUN_INTEGRATION_WORKER_ROUTES,
    HTML_RUN_UNATTENDED_ROUND_ROUTES,
    HTML_SYNC_CI_DECISIONS_ROUTES,
    HTML_TASK_DETAIL_PREFIX,
    HTML_UNATTENDED_DETAIL_PREFIX,
    is_api_route,
    route_in,
    route_value_after_prefix,
)
from .application_helpers_admission import ApplicationAdmissionHelpersMixin
from .application_helpers_forms import ApplicationFormHelpersMixin
from .application_helpers_integration import ApplicationIntegrationHelpersMixin
from .application_identity import ApplicationIdentityMixin
from .application_payload_collaboration import ApplicationPayloadCollaborationMixin
from .application_payload_core import ApplicationPayloadCoreMixin
from .pages_core import ApplicationCorePagesMixin
from .pages_help import ApplicationHelpPagesMixin
from .pages_layout import ApplicationLayoutPagesMixin
from .pages_performance_issues import ApplicationPerformanceIssuesPagesMixin
from .responses import ApplicationResponseMixin
from .features.admission.actions import AdmissionActionsMixin as ApplicationIssueAdmissionActionsMixin
from .features.admission.page import (
    AdmissionRecordPageMixin as ApplicationAdmissionRecordPagesMixin,
    GoldenAdmissionPageMixin as ApplicationGoldenAdmissionPagesMixin,
    QualityPageMixin as ApplicationQualityPagesMixin,
)
from .features.admission.payload import AdmissionWorkflowPayloadMixin as ApplicationPayloadAdmissionReportsMixin
from .features.admission.routes import handle_admission_get, handle_admission_post
from .features.devices.actions import DevicesActionsMixin as ApplicationDeviceActionsMixin
from .features.devices.page import DevicesPageMixin as ApplicationDevicesPageMixin
from .features.devices.payload import DevicesPayloadMixin as ApplicationPayloadDevicesMixin
from .features.devices.routes import handle_devices_get, handle_devices_post
from .features.integration.actions import IntegrationActionsMixin as ApplicationIntegrationActionsMixin
from .features.integration.page import IntegrationPageMixin as ApplicationIntegrationPageMixin
from .features.integration.payload import IntegrationPayloadMixin as ApplicationPayloadQualityIntegrationMixin
from .features.integration.routes import handle_integration_get, handle_integration_post
from .features.performance.page import PerformancePageMixin as ApplicationPerformancePageMixin
from .features.performance.payload import PerformancePayloadMixin as ApplicationPerformancePayloadMixin
from .features.performance.routes import handle_performance_get
from .features.quick_adb.actions import QuickAdbActionsMixin as ApplicationQuickAdbActionsMixin
from .features.quick_adb.page import QuickAdbPageMixin as ApplicationQuickAdbPageMixin
from .features.quick_adb.payload import QuickAdbPayloadMixin as ApplicationQuickAdbPayloadMixin
from .features.quick_adb.routes import handle_quick_adb_get, handle_quick_adb_post
from .features.runner.page import (
    RunnerCardsPageMixin as ApplicationRunnerCardsPagesMixin,
    RunnerPageMixin as ApplicationRunnerPagesMixin,
)
from .features.runner.payload import RunnerPayloadMixin as ApplicationPayloadWorkflowsMixin
from .features.runner.routes import handle_runner_get, handle_runner_post
from .features.runner.actions import RunnerActionsMixin as ApplicationRunnerActionsMixin
from .features.tasks.actions import TasksActionsMixin as ApplicationTaskActionsMixin
from .features.tasks.page import (
    TaskDetailPageMixin as ApplicationTaskIntegrationPagesMixin,
    TasksPageMixin as ApplicationRecordPagesMixin,
)
from .features.tasks.payload import TasksPayloadMixin as ApplicationTasksPayloadMixin
from .features.tasks.routes import handle_tasks_get, handle_tasks_post


class WebPortalApplication(
    ApplicationIdentityMixin,
    ApplicationPayloadCoreMixin,
    ApplicationTasksPayloadMixin,
    ApplicationPayloadDevicesMixin,
    ApplicationQuickAdbPayloadMixin,
    ApplicationPerformancePayloadMixin,
    ApplicationPayloadWorkflowsMixin,
    ApplicationPayloadCollaborationMixin,
    ApplicationPayloadAdmissionReportsMixin,
    ApplicationIssueAdmissionActionsMixin,
    ApplicationPayloadQualityIntegrationMixin,
    ApplicationDevicesPageMixin,
    ApplicationQuickAdbPageMixin,
    ApplicationCorePagesMixin,
    ApplicationRunnerPagesMixin,
    ApplicationRecordPagesMixin,
    ApplicationLayoutPagesMixin,
    ApplicationHelpPagesMixin,
    ApplicationRunnerCardsPagesMixin,
    ApplicationPerformancePageMixin,
    ApplicationPerformanceIssuesPagesMixin,
    ApplicationAdmissionRecordPagesMixin,
    ApplicationGoldenAdmissionPagesMixin,
    ApplicationQualityPagesMixin,
    ApplicationTaskIntegrationPagesMixin,
    ApplicationIntegrationPageMixin,
    ApplicationTaskActionsMixin,
    ApplicationQuickAdbActionsMixin,
    ApplicationRunnerActionsMixin,
    ApplicationDeviceActionsMixin,
    ApplicationIntegrationActionsMixin,
    ApplicationIntegrationHelpersMixin,
    ApplicationFormHelpersMixin,
    ApplicationResponseMixin,
    ApplicationAdmissionHelpersMixin,
):
    """Serve a lightweight HTML portal and matching JSON endpoints from the service layer."""

    _trusted_sso_headers = TRUSTED_SSO_HEADERS
    _required_trusted_sso_claims = REQUIRED_TRUSTED_SSO_CLAIMS
    _writable_identity_form_fields = WRITABLE_IDENTITY_FORM_FIELDS

    def __init__(self, bundle: object, *, title: str = "Android Stability Lab") -> None:
        self._bundle = bundle
        self._title = title

    @staticmethod
    def _normalized_portal_mode(value: str) -> str:
        mode = str(value or "").strip().lower()
        if mode in {"team_entry", "team-entry", "team"}:
            return "team_entry"
        return "local_ops_console"

    def _portal_runtime_config(self) -> dict[str, Any]:
        payload = getattr(self._bundle, "web_portal_config", None)
        if not payload:
            return {}
        config = dict(payload or {})
        config["mode"] = self._normalized_portal_mode(str(config.get("mode", "") or "local_ops_console"))
        return config

    def _portal_mode(self) -> str:
        config = self._portal_runtime_config()
        return self._normalized_portal_mode(str(config.get("mode", "") or "local_ops_console"))

    def _portal_local_base_url(self) -> str:
        config = self._portal_runtime_config()
        host = str(config.get("bound_host", "") or "127.0.0.1")
        port = int(config.get("bound_port", 8030) or 8030)
        return f"http://{host}:{port}/"

    def _portal_base_url(self) -> str:
        config = self._portal_runtime_config()
        explicit = str(config.get("public_base_url", "") or "").strip()
        return explicit or self._portal_local_base_url()

    def _portal_deployment_label(self) -> str:
        config = self._portal_runtime_config()
        explicit = str(config.get("deployment_label", "") or "").strip()
        return explicit or "Android Stability Lab"

    def _platform_surface(self) -> dict[str, list[dict[str, str]]]:
        return portal_payloads.platform_surface()

    def _platform_readiness(self) -> dict[str, Any]:
        config = self._portal_runtime_config()
        mode = self._portal_mode()
        checks = {
            "device_registry": bool(getattr(self._bundle, "device_service", None)),
            "task_query": bool(getattr(self._bundle, "task_service", None)),
            "run_history": bool(getattr(self._bundle, "run_history_service", None)),
            "issue_analysis": bool(getattr(self._bundle, "analysis_service", None)),
            "runner": bool(getattr(self._bundle, "unattended_runner_service", None)),
            "golden_suite": bool(getattr(self._bundle, "rule_replay_golden_suite_service", None)),
            "quality_gate": bool(getattr(self._bundle, "quality_gate_service", None)),
            "admission_case": bool(getattr(self._bundle, "admission_case_service", None)),
            "collaboration": bool(getattr(self._bundle, "collaboration_service", None)),
            "integration_outbox": bool(getattr(self._bundle, "integration_outbox_service", None)),
            "release_submission": bool(getattr(self._bundle, "release_submission_service", None)),
        }
        missing = [key for key, value in checks.items() if not value]
        team_boundary_ready = (
            mode != "team_entry"
            or bool(str(config.get("public_base_url", "") or "").strip())
        )
        overall_ready = not missing and team_boundary_ready
        return {
            "ok": bool(overall_ready),
            "checks": checks,
            "missing_checks": missing,
            "team_boundary_ready": bool(team_boundary_ready),
            "team_boundary_reason": (
                ""
                if team_boundary_ready
                else "team_entry 模式要求显式 public_base_url，供团队共享入口和 API 清单使用。"
            ),
        }

    def _identity_capabilities(self) -> dict[str, Any]:
        return {
            "local_session": True,
            "trusted_sso_header": self._trusted_sso_header_enabled(),
            "trusted_sso_headers": list(self._trusted_sso_headers.values()),
            "trusted_sso_required_headers": [
                self._trusted_sso_headers[key] for key in self._required_trusted_sso_claims
            ],
            "trusted_sso_session_source": "header:trusted_sso",
        }

    def _trusted_sso_header_enabled(self) -> bool:
        service = getattr(self._bundle, "collaboration_service", None)
        return bool(service is not None and hasattr(service, "resolve_sso_actor"))

    def _portal_mode_notice(self) -> str:
        config = self._portal_runtime_config()
        if not config:
            return self._notice("当前 Web 入口按本地运维控制台设计，适合值班和排查，不适合作为团队生产平台直接外放。", tone="warning")
        mode = self._portal_mode()
        host = str(config.get("bound_host", "") or "")
        base_url = self._portal_base_url()
        if mode == "team_entry":
            return self._notice(
                "当前 Web 入口已按团队共享入口模式启动。所有查看者默认看到同一份平台数据；"
                "写操作继续要求服务端解析 identity，并稳定记录 request_id / audit_event_id / permission_check_id。"
                f" 当前共享入口：{escape(base_url)}",
                tone="ok",
            )
        if bool(config.get("allow_remote_access", False)):
            return self._notice(
                f"当前 Web 入口已显式允许远程绑定到 {escape(host)}。它仍是本地运维控制台形态，缺少正式认证、授权和审计边界，不建议直接暴露到团队生产网络。",
                tone="danger",
            )
        return self._notice(
            f"当前 Web 入口绑定在 {escape(host or '127.0.0.1')}，默认仅用于本地值班和排查。",
            tone="warning",
        )

    def handle_request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str = "",
        headers: Mapping[str, str] | None = None,
        client_address: str = "",
    ) -> tuple[int, str, bytes]:
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            return self._json_response(405, {"error": "Method not allowed."})
        parsed = urlparse(path or "/")
        query = parse_qs(parsed.query, keep_blank_values=False)
        request_headers = {
            str(key): str(value)
            for key, value in dict(headers or {}).items()
            if str(key).strip()
        }
        request_id = request_id_from_headers(request_headers)
        route = parsed.path or "/"
        wants_json = is_api_route(route)
        try:
            form = self._request_payload(
                method=normalized_method,
                body=body or b"",
                content_type=content_type,
            )
            request_context = self._request_context(
                query=query,
                form=form,
                headers=request_headers,
                client_address=client_address,
                method=normalized_method,
                route=route,
                strict_actor_resolution=normalized_method == "POST",
            )
            if normalized_method == "POST":
                self._assert_no_identity_override_fields(form)
                if route == "/tasks/actions/upload-apk":
                    result = self._handle_apk_upload(body=body or b"", content_type=content_type)
                    return self._json_response(200, result)
                for feature_handler in (
                    handle_tasks_post,
                    handle_devices_post,
                    handle_quick_adb_post,
                    handle_runner_post,
                    handle_integration_post,
                    handle_admission_post,
                ):
                    feature_response = feature_handler(self, route, query, form, request_context)
                    if feature_response is not None:
                        return feature_response
                if route == "/tasks/actions/delete-apk":
                    result = self._handle_apk_delete(form)
                    return self._json_response(200, result)
                if route_in(route, HTML_CREATE_TASK_ROUTES):
                    result = self._handle_task_create(form, request_context=request_context)
                    payload = self._tasks_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已创建任务：{result.get('task_name', '') or result.get('task_id', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_tasks(payload))
                if route_in(route, HTML_ARCHIVE_TASK_ROUTES):
                    result = self._handle_task_archive(form, request_context=request_context)
                    payload = self._tasks_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": str(result.get("message", "") or "任务已归档。")}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_tasks(payload))
                if route_in(route, HTML_CREATE_RUN_ROUTES):
                    result = self._handle_run_create(form, request_context=request_context)
                    payload = self._tasks_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已创建 Run：{result.get('run_id', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_tasks(payload))
                if route_in(route, HTML_EXECUTE_RUN_ROUTES):
                    result = self._handle_run_execute(form, request_context=request_context)
                    payload = self._run_detail_payload(str(result.get("run_id", "") or ""), query=query)
                    payload["flash"] = {"tone": "ok", "message": f"已执行 Run：{result.get('run_id', '')} -> {result.get('run_status', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_run_detail(payload))
                if route_in(route, HTML_CONFIGURE_UNATTENDED_ROUTES):
                    result = self._handle_unattended_configure(form, request_context=request_context)
                    payload = self._runner_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已更新无人值守配置：{result.get('task_name', '') or result.get('task_id', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_runner(payload))
                if route_in(route, HTML_RUN_UNATTENDED_ROUND_ROUTES):
                    result = self._handle_unattended_run_round(form, request_context=request_context)
                    payload = self._runner_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已触发无人值守轮次：{result.get('task', {}).get('task_id', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_runner(payload))
                if route_in(route, HTML_PATROL_UNATTENDED_ROUTES):
                    result = self._handle_unattended_patrol(form, request_context=request_context)
                    payload = self._runner_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已触发巡检：executed={result.get('patrol', {}).get('executed_task_count', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_runner(payload))
                if route == "/device-pools/actions/update-profile":
                    result = self._handle_device_profile_update(form, request_context=request_context)
                    payload = self._device_pools_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已更新设备标记：{result.get('device_id', '')}",
                    }
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_device_pools(payload))
                if route == "/device-pools/actions/refresh":
                    result = self._handle_device_registry_refresh(form, request_context=request_context)
                    payload = self._device_pools_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已刷新设备快照：scanned={result.get('scanned_count', 0)} updated={result.get('updated_count', 0)}",
                    }
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_device_pools(payload))
                if route == "/device-pools/actions/connect":
                    result = self._handle_device_connect(form, request_context=request_context)
                    payload = self._device_pools_payload(query, request_context=request_context)
                    tone = "ok" if bool(result.get("connected", False)) else "warning"
                    payload["flash"] = {
                        "tone": tone,
                        "message": f"已尝试连接设备：{result.get('serial', '')} -> {'connected' if result.get('connected') else 'not connected'}",
                    }
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_device_pools(payload))
                if route == "/device-pools/actions/pair-connect":
                    result = self._handle_device_pair_connect(form, request_context=request_context)
                    payload = self._device_pools_payload(query, request_context=request_context)
                    tone = "ok" if bool(result.get("paired", False)) and bool(result.get("connected", False)) else "warning"
                    payload["flash"] = {
                        "tone": tone,
                        "message": (
                            f"已执行无线配对并连接：pair={'ok' if result.get('paired') else 'failed'} / "
                            f"connect={'ok' if result.get('connected') else 'failed'}"
                        ),
                    }
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_device_pools(payload))
                if route == "/integration/actions/register-webhook":
                    result = self._handle_register_integration_webhook(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已注册 webhook：{result.get('webhook', {}).get('name', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/register-im-webhook":
                    result = self._handle_register_im_webhook(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已注册 IM 通知 webhook：{result.get('webhook', {}).get('name', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/register-defect-webhook":
                    result = self._handle_register_defect_webhook(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已注册缺陷同步 webhook：{result.get('webhook', {}).get('name', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/create-release-submission":
                    result = self._handle_create_release_submission(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已创建提测请求：{result.get('release_submission', {}).get('submission_id', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/sync-release-admission":
                    result = self._handle_sync_release_submission_admission(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已同步提测准入：{result.get('release_submission', {}).get('submission_id', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/register-release-webhook":
                    result = self._handle_register_release_webhook(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已注册提测 webhook：{result.get('webhook', {}).get('name', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/deliver-outbox":
                    result = self._handle_deliver_integration_outbox(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已执行单轮投递：{result.get('delivery', {}).get('webhook_name', '')}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route_in(route, HTML_RUN_INTEGRATION_WORKER_ROUTES):
                    result = self._handle_run_integration_worker(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已执行 worker：rounds={result.get('delivery', {}).get('rounds_executed', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/run-ci-worker":
                    result = self._handle_run_ci_sync_worker(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已执行 CI 回传 worker：rounds={result.get('delivery', {}).get('rounds_executed', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/run-im-worker":
                    result = self._handle_run_im_notify_worker(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已执行 IM 通知 worker：rounds={result.get('delivery', {}).get('rounds_executed', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/run-defect-worker":
                    result = self._handle_run_defect_sync_worker(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已执行缺陷同步 worker：rounds={result.get('delivery', {}).get('rounds_executed', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/integration/actions/run-release-worker":
                    result = self._handle_run_release_sync_worker(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"已执行提测同步 worker：rounds={result.get('delivery', {}).get('rounds_executed', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route_in(route, HTML_REPLAY_DEAD_LETTERS_ROUTES):
                    result = self._handle_replay_dead_letters(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"dead-letter 处理完成：replayed={result.get('dead_letter_replay', {}).get('replayed_count', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route_in(route, HTML_SYNC_CI_DECISIONS_ROUTES):
                    result = self._handle_sync_ci_decisions(form, request_context=request_context)
                    payload = self._integration_payload(query, request_context=request_context)
                    payload["flash"] = {"tone": "ok", "message": f"CI 准入同步完成：pending={result.get('query', {}).get('pending_count', 0)}"}
                    payload["operation_result"] = result
                    return self._html_response(200, self._render_integration(payload))
                if route == "/issues/actions/assign":
                    result = self._handle_issue_assign(form, request_context=request_context)
                    payload = self._issues_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已更新问题认领：{result['fingerprint']} -> {result['assignee_display_name'] or result['assignee_id']}",
                    }
                    return self._html_response(200, self._render_issues(payload))
                if route == "/issues/actions/comment":
                    result = self._handle_issue_comment(form, request_context=request_context)
                    payload = self._issues_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已记录问题评论：{result['fingerprint']}",
                    }
                    return self._html_response(200, self._render_issues(payload))
                if route == "/issues/actions/transition":
                    result = self._handle_issue_transition(form, request_context=request_context)
                    payload = self._issues_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已更新问题状态：{result['fingerprint']} -> {result['workflow_state']}",
                    }
                    return self._html_response(200, self._render_issues(payload))
                if route == "/issues/actions/create-defect":
                    result = self._handle_issue_create_defect(form, request_context=request_context)
                    payload = self._issues_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已创建缺陷请求：{result['fingerprint']} -> {result.get('latest_defect_system_key', '')}",
                    }
                    return self._html_response(200, self._render_issues(payload))
                if route == "/issues/actions/sync-defect":
                    result = self._handle_issue_sync_defect(form, request_context=request_context)
                    payload = self._issues_payload(query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已同步缺陷状态：{result['fingerprint']} -> {result.get('latest_defect_status', '')}",
                    }
                    return self._html_response(200, self._render_issues(payload))
                if route == "/admission/actions/override":
                    result = self._handle_admission_override(form, request_context=request_context)
                    payload = self._baseline_detail_payload(str(result["baseline_key"]), query=query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": (
                            f"已记录人工覆盖：{result['baseline_key']} "
                            f"{result['automatic_decision']} -> {result['final_decision']}"
                        ),
                    }
                    return self._html_response(200, self._render_admission_detail(payload))
                if route == "/admission/actions/assign":
                    result = self._handle_admission_assign(form, request_context=request_context)
                    payload = self._baseline_detail_payload(str(result["baseline_key"]), query=query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已更新准入单认领：{result['baseline_key']} -> {result['assignee_display_name'] or result['assignee_id']}",
                    }
                    return self._html_response(200, self._render_admission_detail(payload))
                if route == "/admission/actions/comment":
                    result = self._handle_admission_comment(form, request_context=request_context)
                    payload = self._baseline_detail_payload(str(result["baseline_key"]), query=query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已记录准入单评论：{result['baseline_key']}",
                    }
                    return self._html_response(200, self._render_admission_detail(payload))
                if route == "/admission/actions/transition":
                    result = self._handle_admission_transition(form, request_context=request_context)
                    payload = self._baseline_detail_payload(str(result["baseline_key"]), query=query, request_context=request_context)
                    payload["flash"] = {
                        "tone": "ok",
                        "message": f"已更新准入单状态：{result['baseline_key']} -> {result['workflow_state']}",
                    }
                    return self._html_response(200, self._render_admission_detail(payload))
                if route == "/api/issues/actions/assign":
                    return self._json_response(200, self._handle_issue_assign(form, request_context=request_context))
                if route == "/api/issues/actions/comment":
                    return self._json_response(200, self._handle_issue_comment(form, request_context=request_context))
                if route == "/api/issues/actions/transition":
                    return self._json_response(200, self._handle_issue_transition(form, request_context=request_context))
                if route == "/api/issues/actions/create-defect":
                    return self._json_response(200, self._handle_issue_create_defect(form, request_context=request_context))
                if route == "/api/issues/actions/sync-defect":
                    return self._json_response(200, self._handle_issue_sync_defect(form, request_context=request_context))
                if route == "/api/admission/actions/override":
                    return self._json_response(200, self._handle_admission_override(form, request_context=request_context))
                if route == "/api/admission/actions/assign":
                    return self._json_response(200, self._handle_admission_assign(form, request_context=request_context))
                if route == "/api/admission/actions/comment":
                    return self._json_response(200, self._handle_admission_comment(form, request_context=request_context))
                if route == "/api/admission/actions/transition":
                    return self._json_response(200, self._handle_admission_transition(form, request_context=request_context))
                if route_in(route, API_CREATE_TASK_ROUTES):
                    return self._json_response(200, self._handle_task_create(form, request_context=request_context))
                if route_in(route, API_ARCHIVE_TASK_ROUTES):
                    return self._json_response(200, self._handle_task_archive(form, request_context=request_context))
                if route_in(route, API_CREATE_RUN_ROUTES):
                    return self._json_response(200, self._handle_run_create(form, request_context=request_context))
                if route_in(route, API_EXECUTE_RUN_ROUTES):
                    return self._json_response(200, self._handle_run_execute(form, request_context=request_context))
                if route_in(route, API_CONFIGURE_UNATTENDED_ROUTES):
                    return self._json_response(200, self._handle_unattended_configure(form, request_context=request_context))
                if route_in(route, API_RUN_UNATTENDED_ROUND_ROUTES):
                    return self._json_response(200, self._handle_unattended_run_round(form, request_context=request_context))
                if route_in(route, API_PATROL_UNATTENDED_ROUTES):
                    return self._json_response(200, self._handle_unattended_patrol(form, request_context=request_context))
                if route == "/api/device-pools/actions/update-profile":
                    return self._json_response(200, self._handle_device_profile_update(form, request_context=request_context))
                if route == "/api/device-pools/actions/refresh":
                    return self._json_response(200, self._handle_device_registry_refresh(form, request_context=request_context))
                if route == "/api/device-pools/actions/connect":
                    return self._json_response(200, self._handle_device_connect(form, request_context=request_context))
                if route == "/api/device-pools/actions/pair-connect":
                    return self._json_response(200, self._handle_device_pair_connect(form, request_context=request_context))
                if route == "/api/integration/actions/register-webhook":
                    return self._json_response(200, self._handle_register_integration_webhook(form, request_context=request_context))
                if route == "/api/integration/actions/register-im-webhook":
                    return self._json_response(200, self._handle_register_im_webhook(form, request_context=request_context))
                if route == "/api/integration/actions/register-defect-webhook":
                    return self._json_response(200, self._handle_register_defect_webhook(form, request_context=request_context))
                if route == "/api/release-submissions/actions/create":
                    return self._json_response(200, self._handle_create_release_submission(form, request_context=request_context))
                if route == "/api/release-submissions/actions/sync-admission":
                    return self._json_response(200, self._handle_sync_release_submission_admission(form, request_context=request_context))
                if route == "/api/integration/actions/register-release-webhook":
                    return self._json_response(200, self._handle_register_release_webhook(form, request_context=request_context))
                if route == "/api/integration/actions/deliver-outbox":
                    return self._json_response(200, self._handle_deliver_integration_outbox(form, request_context=request_context))
                if route_in(route, API_RUN_INTEGRATION_WORKER_ROUTES):
                    return self._json_response(200, self._handle_run_integration_worker(form, request_context=request_context))
                if route == "/api/integration/actions/run-ci-worker":
                    return self._json_response(200, self._handle_run_ci_sync_worker(form, request_context=request_context))
                if route == "/api/integration/actions/run-im-worker":
                    return self._json_response(200, self._handle_run_im_notify_worker(form, request_context=request_context))
                if route == "/api/integration/actions/run-defect-worker":
                    return self._json_response(200, self._handle_run_defect_sync_worker(form, request_context=request_context))
                if route == "/api/integration/actions/run-release-worker":
                    return self._json_response(200, self._handle_run_release_sync_worker(form, request_context=request_context))
                if route_in(route, API_REPLAY_DEAD_LETTERS_ROUTES):
                    return self._json_response(200, self._handle_replay_dead_letters(form, request_context=request_context))
                if route_in(route, API_SYNC_CI_DECISIONS_ROUTES):
                    return self._json_response(200, self._handle_sync_ci_decisions(form, request_context=request_context))
                if wants_json:
                    return self._json_response(404, {"error": "API endpoint not found.", "path": route})
                return self._html_response(404, self._render_not_found(route))
            if route == "/health":
                return self._json_response(200, {"ok": True, "service": "web_portal"})
            if route == "/ready":
                readiness = self._platform_readiness()
                payload = {
                    "ok": bool(readiness.get("ok", False)),
                    "service": "web_portal",
                    "mode": self._portal_mode(),
                    "public_base_url": self._portal_base_url(),
                    "deployment_label": self._portal_deployment_label(),
                    "readiness": readiness,
                }
                return self._json_response(200 if payload["ok"] else 503, payload)
            if route == "/":
                payload = self._home_payload(query, request_context=request_context)
                return self._html_response(200, self._render_home(payload))
            if route == "/platform":
                payload = self._platform_payload(query, request_context=request_context)
                return self._html_response(200, self._render_platform(payload))
            if route == "/doctor":
                payload = self._doctor_payload(query, request_context=request_context)
                return self._html_response(200, self._render_doctor(payload))
            for feature_handler in (
                handle_devices_get,
                handle_quick_adb_get,
                handle_tasks_get,
                handle_runner_get,
                handle_integration_get,
                handle_performance_get,
                handle_admission_get,
            ):
                feature_response = feature_handler(self, route, query, request_context)
                if feature_response is not None:
                    return feature_response
            if route == "/device-pools":
                payload = self._device_pools_payload(query, request_context=request_context)
                return self._html_response(200, self._render_device_pools(payload))
            if route == "/tasks":
                payload = self._tasks_payload(query, request_context=request_context)
                return self._html_response(200, self._render_tasks(payload))
            if route == "/long-run-templates":
                payload = self._long_run_templates_payload(query, request_context=request_context)
                return self._html_response(200, self._render_long_run_templates(payload))
            if route == "/performance":
                payload = self._performance_payload(query, request_context=request_context)
                return self._html_response(200, self._render_performance(payload))
            if route == "/integration":
                payload = self._integration_payload(query, request_context=request_context)
                return self._html_response(200, self._render_integration(payload))
            if route == "/json-api":
                payload = self._home_payload(query, request_context=request_context)
                return self._html_response(200, self._render_json_api_index(payload))
            if route == "/issues":
                payload = self._issues_payload(query, request_context=request_context)
                return self._html_response(200, self._render_issues(payload))
            if route == "/runner":
                payload = self._runner_payload(query, request_context=request_context)
                return self._html_response(200, self._render_runner(payload))
            if route == "/goldens":
                payload = self._goldens_payload(query, request_context=request_context)
                return self._html_response(200, self._render_goldens(payload))
            if route == "/goldens/diff":
                payload = self._golden_diff_payload(query, request_context=request_context)
                return self._html_response(200, self._render_golden_diff(payload))
            if route == "/admission":
                payload = self._admission_payload(query, request_context=request_context)
                return self._html_response(200, self._render_admission(payload))
            if route == "/rules":
                payload = self._rules_payload(query, request_context=request_context)
                return self._html_response(200, self._render_rules(payload))
            if route == "/admission/view":
                file_path = self._required_query_value(query, "path")
                return self._file_response(file_path)
            if (case_id := route_value_after_prefix(route, HTML_GOLDEN_CASE_PREFIX)) is not None:
                payload = self._golden_case_detail_payload(case_id, query=query)
                return self._html_response(200, self._render_golden_case_detail(payload))
            if (run_id := route_value_after_prefix(route, HTML_RUN_ARTIFACTS_PREFIX)) is not None:
                payload = self._run_detail_payload(run_id, query=query)
                return self._html_response(200, self._render_run_artifacts(payload))
            if (run_id := route_value_after_prefix(route, HTML_RUN_DETAIL_PREFIX)) is not None:
                payload = self._run_detail_payload(run_id, query=query)
                return self._html_response(200, self._render_run_detail(payload))
            if (task_id := route_value_after_prefix(route, HTML_TASK_DETAIL_PREFIX)) is not None:
                payload = self._task_detail_payload(task_id, query=query, request_context=request_context)
                return self._html_response(200, self._render_task_detail(payload))
            if (task_id := route_value_after_prefix(route, HTML_UNATTENDED_DETAIL_PREFIX)) is not None:
                payload = self._unattended_detail_payload(task_id, query=query, request_context=request_context)
                return self._html_response(200, self._render_unattended_detail(payload))
            if (baseline_key := route_value_after_prefix(route, HTML_ADMISSION_BASELINE_PREFIX)) is not None:
                payload = self._baseline_detail_payload(baseline_key, query=query, request_context=request_context)
                return self._html_response(200, self._render_admission_detail(payload))
            if route == "/api/home":
                return self._json_response(200, self._home_payload(query, request_context=request_context))
            if route == "/api/platform":
                return self._json_response(200, self._platform_payload(query, request_context=request_context))
            if route == "/api/platform-health":
                return self._json_response(200, self._platform_health_payload(query, request_context=request_context))
            if route == "/api/doctor":
                return self._json_response(200, self._doctor_payload(query, request_context=request_context))
            if route == "/api/users":
                return self._json_response(200, self._users_payload(query, request_context=request_context))
            if route == "/api/responsibility":
                return self._json_response(200, self._responsibility_payload(query, request_context=request_context))
            if route == "/api/device-pools":
                return self._json_response(200, self._device_pools_payload(query, request_context=request_context))
            if route == "/api/manifest":
                return self._json_response(200, self._api_manifest_payload(request_context=request_context))
            if route == "/api/openapi.json":
                return self._json_response(200, self._openapi_payload(request_context=request_context))
            if route == "/api/tasks":
                return self._json_response(200, self._tasks_payload(query, request_context=request_context))
            if route == "/api/long-run-templates":
                return self._json_response(200, self._long_run_templates_payload(query, request_context=request_context))
            if route == "/api/performance":
                return self._json_response(200, self._performance_payload(query, request_context=request_context))
            if route == "/api/release-submissions":
                return self._json_response(200, self._release_submissions_payload(query, request_context=request_context))
            if route == "/api/integration":
                return self._json_response(200, self._integration_payload(query, request_context=request_context))
            if route == "/api/issues":
                return self._json_response(200, self._issues_payload(query, request_context=request_context))
            if route == "/api/runner":
                return self._json_response(200, self._runner_payload(query, request_context=request_context))
            if route == "/api/goldens":
                return self._json_response(200, self._goldens_payload(query, request_context=request_context))
            if route == "/api/goldens/diff":
                return self._json_response(200, self._golden_diff_payload(query, request_context=request_context))
            if route == "/api/admission":
                return self._json_response(200, self._admission_payload(query, request_context=request_context))
            if route == "/api/admission/cases":
                return self._json_response(200, self._admission_payload(query, request_context=request_context))
            if (baseline_key := route_value_after_prefix(route, API_ADMISSION_REPORT_PREFIX)) is not None:
                return self._json_response(200, self._admission_report_response_payload(baseline_key))
            if route == "/api/rules":
                return self._json_response(200, self._rules_payload(query, request_context=request_context))
            if route == "/api/integration/outbox":
                return self._json_response(200, self._integration_payload(query, request_context=request_context))
            if (case_id := route_value_after_prefix(route, API_GOLDEN_CASE_PREFIX)) is not None:
                return self._json_response(200, self._golden_case_detail_payload(case_id, query=query))
            if (run_id := route_value_after_prefix(route, API_RUN_ARTIFACTS_PREFIX)) is not None:
                payload = self._run_detail_payload(run_id, query=query)
                return self._json_response(200, self._run_artifacts_payload(payload))
            if (run_id := route_value_after_prefix(route, API_RUN_DETAIL_PREFIX)) is not None:
                return self._json_response(200, self._run_detail_payload(run_id, query=query))
            if (submission_id := route_value_after_prefix(route, API_RELEASE_SUBMISSION_DETAIL_PREFIX)) is not None:
                return self._json_response(200, self._release_submission_detail_payload(submission_id, query=query, request_context=request_context))
            if (task_id := route_value_after_prefix(route, API_TASK_DETAIL_PREFIX)) is not None:
                return self._json_response(200, self._task_detail_payload(task_id, query=query, request_context=request_context))
            if (task_id := route_value_after_prefix(route, API_UNATTENDED_DETAIL_PREFIX)) is not None:
                return self._json_response(200, self._unattended_detail_payload(task_id, query=query, request_context=request_context))
            if (baseline_key := route_value_after_prefix(route, API_ADMISSION_BASELINE_PREFIX)) is not None:
                return self._json_response(200, self._baseline_detail_payload(baseline_key, query=query, request_context=request_context))
            if (baseline_key := route_value_after_prefix(route, API_ADMISSION_CASE_PREFIX)) is not None:
                return self._json_response(200, self._baseline_detail_payload(baseline_key, query=query, request_context=request_context))
            if wants_json:
                return self._json_response(404, {"error": "API endpoint not found.", "path": route})
            return self._html_response(404, self._render_not_found(route))
        except AppError as exc:
            error = exc.with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, f"{error.code}: {error.message}"))
        except PermissionError as exc:
            error = normalize_app_error(exc).with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, error.message))
        except ValueError as exc:
            error = normalize_app_error(exc).with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, error.message))
        except Exception as exc:  # pragma: no cover - defensive path for runtime failures
            error = normalize_app_error(exc).with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, error.message))


bind_web_portal_application(WebPortalApplication)


def serve_web_portal(
    *,
    host: str,
    port: int,
    bundle: object,
    allow_remote_access: bool = False,
    portal_mode: str = "local_ops_console",
    public_base_url: str = "",
    deployment_label: str = "",
) -> None:
    """Start a blocking HTTP server for the Web portal."""
    from .server import serve_web_portal as _serve_web_portal

    _serve_web_portal(
        host=host,
        port=port,
        bundle=bundle,
        allow_remote_access=allow_remote_access,
        portal_mode=portal_mode,
        public_base_url=public_base_url,
        deployment_label=deployment_label,
    )
