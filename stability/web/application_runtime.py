from __future__ import annotations

from html import escape
from typing import Any

from stability.web import payloads as portal_payloads


class ApplicationRuntimeMixin:
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
