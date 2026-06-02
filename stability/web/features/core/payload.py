from __future__ import annotations

import sys
from typing import Any, Mapping, Sequence
from stability.web import payloads as portal_payloads
from stability.app import ConfigProvider, DoctorService
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class CorePayloadMixin:
    def _home_payload(self, query: dict[str, list[str]], *, request_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        device_sync = self._maybe_sync_devices(query)
        devices = self._device_summaries()
        tasks = self._task_summaries(limit=8)
        runs = self._run_summaries(limit=8)
        issues = self._issue_summaries(limit=8)
        baselines = self._baseline_summaries(limit=6)
        runner = self._runner_snapshot()
        performance = self._recent_monitoring_snapshot(run_limit=40, entry_limit=6)
        platform_health = self._platform_health_payload({}, request_context=request_context)
        surface = self._platform_surface()
        online_count = sum(1 for item in devices if item.get("is_online"))
        schedulable_count = sum(1 for item in devices if item.get("is_schedulable"))
        failed_run_count = sum(1 for item in runs if item.get("run_status") == "failed")
        return {
            "page": "home",
            "title": "Web 首页",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "device_sync": device_sync,
            "summary": {
                "device_count": len(devices),
                "online_device_count": online_count,
                "schedulable_device_count": schedulable_count,
                "task_count": len(self._task_summaries(limit=0)),
                "recent_run_count": len(runs),
                "failed_run_count": failed_run_count,
                "top_issue_count": len(issues),
                "baseline_count": len(baselines),
                "runner_status": str(runner.get("status", "missing") or "missing"),
                "platform_health_status": str(platform_health.get("status", "unknown") or "unknown"),
                "platform_health_severity": str(platform_health.get("severity", "unknown") or "unknown"),
                "platform_health_fail_count": int(
                    dict(platform_health.get("summary", {}) or {}).get("fail_count", 0) or 0
                ),
                "performance_sample_count": int(dict(performance.get("summary", {}) or {}).get("sample_count", 0) or 0),
                "performance_trace_count": int(dict(performance.get("summary", {}) or {}).get("trace_count", 0) or 0),
                "runner_lock_state": str(runner.get("lock_state", "released") or "released"),
                "runner_heartbeat_age_seconds": runner.get("heartbeat_age_seconds"),
                "runner_cycle_count": int(runner.get("cycle_count", 0) or 0),
                "runner_daily_report_date": str(dict(runner.get("latest_daily_report", {}) or {}).get("report_date", "") or ""),
                "runner_daily_report_round_count": int(
                    dict(runner.get("latest_daily_report", {}) or {}).get("round_count", 0) or 0
                ),
                "runner_daily_report_failed_round_count": int(
                    dict(runner.get("latest_daily_report", {}) or {}).get("failed_round_count", 0) or 0
                ),
                "runner_weekly_report_week_key": str(
                    dict(runner.get("latest_weekly_report", {}) or {}).get("week_key", "") or ""
                ),
                "runner_weekly_report_round_count": int(
                    dict(runner.get("latest_weekly_report", {}) or {}).get("round_count", 0) or 0
                ),
                "runner_weekly_report_failed_round_count": int(
                    dict(runner.get("latest_weekly_report", {}) or {}).get("failed_round_count", 0) or 0
                ),
                "runner_last_executed_task_count": int(
                    dict(runner.get("last_patrol", {}) or {}).get("executed_task_count", 0) or 0
                ),
                "runner_quarantined_device_count": int(
                    dict(runner.get("last_patrol", {}) or {}).get("quarantined_device_count", 0) or 0
                ),
            },
            "devices": devices[:6],
            "tasks": tasks,
            "runs": runs,
            "issues": issues,
            "baselines": baselines,
            "runner": runner,
            "performance": performance,
            "platform_health": platform_health,
            "pages": list(surface.get("pages", []) or []),
            "api_endpoints": list(surface.get("api_endpoints", []) or []),
        }

    def _platform_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del query
        config = self._portal_runtime_config()
        readiness = self._platform_readiness()
        surface = self._platform_surface()
        platform_health = self._platform_health_payload({}, request_context=request_context)
        write_boundary = {
            "shared_read_surface": True,
            "same_data_for_all_viewers": True,
            "write_identity_resolution": "server_resolved_identity",
            "identity_capabilities": self._identity_capabilities(),
            "write_audit_fields": [
                "request_id",
                "audit_event_id",
                "permission_check_id",
                "identity_id",
                "session_id",
                "auth_mechanism",
                "identity_provider",
                "external_subject_id",
                "organization_id",
                "team_ids",
            ],
            "request_headers": ["X-Request-ID", "X-ASL-Request-ID"],
            "security_headers_enabled": True,
            "ready_endpoint": "/ready",
            "health_endpoint": "/health",
        }
        return {
            "page": "platform",
            "title": "平台说明",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "request": dict(dict(request_context or {}).get("request", {}) or {}),
            "summary": {
                "portal_mode": self._portal_mode(),
                "deployment_label": self._portal_deployment_label(),
                "public_base_url": self._portal_base_url(),
                "allow_remote_access": bool(config.get("allow_remote_access", False)),
                "page_count": len(surface["pages"]),
                "api_count": len(surface["api_endpoints"]),
                "write_action_count": len(surface["write_actions"]),
                "readiness_ok": bool(readiness.get("ok", False)),
                "platform_health_status": str(platform_health.get("status", "unknown") or "unknown"),
                "missing_check_count": len(readiness.get("missing_checks", [])),
            },
            "deployment": {
                "mode": self._portal_mode(),
                "deployment_label": self._portal_deployment_label(),
                "bound_host": str(config.get("bound_host", "") or "127.0.0.1"),
                "bound_port": int(config.get("bound_port", 8030) or 8030),
                "local_base_url": self._portal_local_base_url(),
                "public_base_url": self._portal_base_url(),
                "allow_remote_access": bool(config.get("allow_remote_access", False)),
                "team_boundary_version": "team_portal_boundary_v1",
            },
            "identity_capabilities": self._identity_capabilities(),
            "readiness": readiness,
            "platform_health": platform_health,
            "write_boundary": write_boundary,
            "surface": surface,
            "api_manifest_path": "/api/manifest",
            "openapi_path": "/api/openapi.json",
            "callback_contract": self._integration_callback_contract_payload(),
            "notes": [
                "平台默认仍是本地部署优先；如需共享，优先通过 public_base_url 或反向代理暴露统一入口。",
                "所有查看者默认看到同一份平台数据，不做按人分视图；写操作继续走服务端解析 identity。",
                "正式 API manifest、OpenAPI 风格描述和最小回调签名边界已经具备；更复杂组织权限仍属于后续阶段。",
            ],
        }

    def _platform_health_payload(
        self,
        query: dict[str, list[str]] | None = None,
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del query, request_context
        service = getattr(self._bundle, "platform_health_service", None)
        if service is None or not hasattr(service, "snapshot"):
            return {
                "contract_version": "asl.platform_health.v1",
                "generated_at": _generated_at_now(),
                "ok": False,
                "status": "degraded",
                "severity": "warn",
                "summary": {"status": "degraded", "warn_count": 1, "fail_count": 0, "skipped_count": 1},
                "checks": [
                    {
                        "name": "平台自监控",
                        "category": "platform_health",
                        "status": "skipped",
                        "summary": "当前 bundle 未提供 PlatformHealthService。",
                        "metrics": {},
                        "details": {},
                        "recommended_action": "确认 bootstrap 已接入 platform_health_service。",
                    }
                ],
                "readiness": {"ok": True, "skipped_checks": ["platform_health"]},
                "trends": {"history_count": 0},
                "links": {"api": "/api/platform-health"},
                "history": [],
            }
        snapshot = service.snapshot(record=True)
        if hasattr(service, "snapshot_payload"):
            return dict(service.snapshot_payload(snapshot))
        return dict(snapshot)

    def _doctor_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self._portal_runtime_config()
        provider = ConfigProvider()
        paths = provider.runtime_paths()
        outbox_config = provider.outbox()
        check_webhooks = str((query.get("check_webhooks") or [""])[0]).strip().lower() in {"1", "true", "yes"}
        device_id = str((query.get("device_id") or [""])[0]).strip()
        package_name = str((query.get("package_name") or [""])[0]).strip()
        keyword = self._str_query(query, "keyword")
        status_filter = self._str_query(query, "status")
        page = max(self._int_query(query, "page", default=1), 1)
        page_size = min(max(self._int_query(query, "page_size", default=20), 1), 100)
        doctor_service_class = DoctorService
        legacy_module = sys.modules.get("stability.web.application_payload_core")
        if legacy_module is not None:
            doctor_service_class = getattr(legacy_module, "DoctorService", doctor_service_class)
        report = doctor_service_class(
            runtime_root=paths.root,
            config_dir=provider.config_dir,
            web_host=str(config.get("bound_host", "") or "127.0.0.1"),
            web_port=int(config.get("bound_port", 8030) or 8030),
            outbox_root=outbox_config.root_dir,
            device_id=device_id,
            package_name=package_name,
            check_webhooks=check_webhooks,
        ).run()
        all_checks = [
            {
                "name": item.name,
                "status": item.status,
                "summary": item.summary,
                "details": dict(item.details),
            }
            for item in report.checks
        ]
        filters = {
            "keyword": keyword,
            "status": status_filter,
            "device_id": device_id,
            "package_name": package_name,
            "check_webhooks": "1" if check_webhooks else "",
            "page": page,
            "page_size": page_size,
        }
        filtered_checks = [item for item in all_checks if self._doctor_check_matches_admin_filters(item, filters)]
        checks = filtered_checks[(page - 1) * page_size:page * page_size]
        return {
            "page": "doctor",
            "title": "诊断中心",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "check_webhooks": check_webhooks,
            "device_id": device_id,
            "package_name": package_name,
            "ok": report.ok,
            "summary": {**dict(report.summary), "filtered": len(filtered_checks), "total": len(all_checks)},
            "filters": filters,
            "filter_options": {
                "statuses": sorted({str(item.get("status", "") or "") for item in all_checks if str(item.get("status", "") or "").strip()}),
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(filtered_checks),
            },
            "checks": checks,
        }

    @staticmethod
    def _doctor_check_matches_admin_filters(item: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        keyword = str(filters.get("keyword", "") or "").lower()
        if keyword:
            details = dict(item.get("details", {}) or {})
            haystack = " ".join(
                [
                    str(item.get("name", "") or ""),
                    str(item.get("status", "") or ""),
                    str(item.get("summary", "") or ""),
                    *[str(key) for key in details],
                    *[str(value) for value in details.values()],
                ]
            ).lower()
            if keyword not in haystack:
                return False
        status = str(filters.get("status", "") or "").lower()
        if status and status != str(item.get("status", "") or "").lower():
            return False
        return True

    def _users_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del query
        profiles, source = self._user_profiles()
        team_counts: dict[str, int] = {}
        provider_counts: dict[str, int] = {}
        for profile in profiles:
            for team_id in list(profile.get("team_ids", []) or []):
                team_counts[str(team_id)] = team_counts.get(str(team_id), 0) + 1
            for identity in list(profile.get("external_identities", []) or []):
                provider = str(dict(identity or {}).get("provider", "") or "unknown")
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
        return {
            "page": "users",
            "title": "用户目录",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "summary": {
                "profile_count": len(profiles),
                "team_count": len(team_counts),
                "external_identity_count": sum(len(list(item.get("external_identities", []) or [])) for item in profiles),
                "source": source,
                "supports_user_profiles": source == "user_profiles",
                "team_counts": team_counts,
                "external_provider_counts": provider_counts,
            },
            "profiles": profiles,
        }

    def _responsibility_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del query
        profiles, profile_source = self._user_profiles()
        profile_by_actor = {
            str(item.get("actor_id", "") or ""): item
            for item in profiles
            if str(item.get("actor_id", "") or "")
        }
        issues = self._issue_summaries(limit=50)
        admissions = self._baseline_summaries(limit=50)
        releases = self._release_submission_summaries_for_responsibility(limit=50)
        issue_items = [self._responsibility_issue_item(item, profile_by_actor=profile_by_actor) for item in issues]
        admission_items = [
            self._responsibility_admission_item(item, profile_by_actor=profile_by_actor)
            for item in admissions
        ]
        release_items = [self._responsibility_release_item(item) for item in releases]
        defect_items = [
            self._responsibility_defect_item(issue=item, defect=defect)
            for item in issues
            for defect in list(item.get("defect_links", []) or [])
        ]
        external_mappings = [
            self._responsibility_external_mapping(profile, identity)
            for profile in profiles
            for identity in list(profile.get("external_identities", []) or [])
        ]
        owner_keys = {
            str(item.get("responsibility_key", "") or "")
            for item in [*issue_items, *admission_items, *defect_items, *release_items]
            if str(item.get("responsibility_key", "") or "")
        }
        return {
            "page": "responsibility",
            "title": "责任同步",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "contract_version": "asl.responsibility_view.v1",
            "summary": {
                "profile_count": len(profiles),
                "profile_source": profile_source,
                "issue_assignment_count": len(issue_items),
                "admission_assignment_count": len(admission_items),
                "defect_team_count": len(defect_items),
                "release_owner_team_count": len(release_items),
                "external_mapping_count": len(external_mappings),
                "responsibility_key_count": len(owner_keys),
            },
            "users": profiles,
            "external_mappings": external_mappings,
            "issues": issue_items,
            "admissions": admission_items,
            "defects": defect_items,
            "releases": release_items,
        }

    def _rules_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "rule_governance_service", None)
        path_override = self._str_query(query, "path") or None
        updates = self._query_overrides(query)
        entrypoint = self._describe_rule_entrypoint_payload(service, path_override=path_override)
        preview: dict[str, Any] = {}
        if updates:
            preview = self._preview_analysis_rule_update_payload(
                service,
                path_override=path_override,
                updates=updates,
                entrypoint=entrypoint,
            )
        governance_state: dict[str, Any] = {}
        if service is not None:
            state_method = getattr(service, "rule_governance_state", None)
            if callable(state_method):
                state = self._call_rule_service_method(
                    state_method,
                    (((), {"path": path_override, "limit": 6}), ((), {"limit": 6}), ((), {})),
                )
                governance_state = state or {}
        validation = dict(entrypoint.get("validation", {}) or {})
        return {
            "page": "rules",
            "title": "规则中心",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "contract_version": "asl.rule_entrypoint.v1",
            "summary": {
                "source": str(entrypoint.get("source", "") or "fallback"),
                "config_path": str(entrypoint.get("config_path", "") or ""),
                "current_version": str(entrypoint.get("current_version", "") or ""),
                "validation_valid": bool(validation.get("valid", False)),
                "error_count": int(validation.get("error_count", 0) or 0),
                "warning_count": int(validation.get("warning_count", 0) or 0),
                "editable_field_count": len(list(entrypoint.get("editable_fields", []) or [])),
                "preview_available": bool(preview),
                "write_policy": str(entrypoint.get("write_policy", "preview_only_no_config_write") or ""),
                "candidate_count": len(list(governance_state.get("candidates", []) or [])),
                "published_version_count": len(list(governance_state.get("versions", []) or [])),
                "permission_binding_count": len(list(governance_state.get("permissions", []) or [])),
            },
            "entrypoint": entrypoint,
            "preview": preview,
            "governance": governance_state,
        }

    def _describe_rule_entrypoint_payload(
        self,
        service: object | None,
        *,
        path_override: str | None,
    ) -> dict[str, Any]:
        if service is not None:
            describe_method = getattr(service, "describe_rule_entrypoint", None)
            if callable(describe_method):
                result = self._call_rule_service_method(
                    describe_method,
                    (
                        ((), {"path": path_override}),
                        ((path_override,), {}),
                        ((), {}),
                    ),
                )
                if result is not None:
                    result.setdefault("source", "service")
                    result.setdefault("write_policy", "governed_candidate_publish")
                    return result

        inspection = object()
        if service is not None and hasattr(service, "inspect_rules"):
            try:
                inspection = service.inspect_rules(path_override)
            except Exception:
                inspection = object()
        validation = self._rule_validation_payload(getattr(inspection, "validation", object()))
        effective_rules = dict(getattr(inspection, "effective_rules", {}) or {})
        source_rules = dict(getattr(inspection, "source_rules", {}) or {})
        config_path = str(getattr(inspection, "path", "") or path_override or "")
        return {
            "source": "fallback",
            "contract_version": "asl.rule_entrypoint.v1",
            "config_path": config_path,
            "current_version": str(
                effective_rules.get("version")
                or source_rules.get("version")
                or effective_rules.get("rule_version")
                or ""
            ),
            "source_exists": bool(getattr(inspection, "source_exists", False)),
            "validation": validation,
            "editable_fields": [
                "version",
                "fingerprint_rules",
                "issue_group_rules",
                "performance_thresholds",
                "risk_policies",
            ],
            "risk_prompts": [
                "规则变更会影响 issue 聚合、准入门禁和历史对比口径。",
                "Web 入口只做预览，不直接写 config 文件；请走审计和 baseline 流程。",
            ],
            "recommended_flow": [
                "describe-rule-entrypoint",
                "preview-analysis-rule-update",
                "diff-analysis-rules",
                "review-analysis-rules",
                "verify-rule-replay-goldens",
                "promote-rule-review-report-baseline",
            ],
            "related_policy_files": [
                config_path,
                "config/stability_rules.json",
                "config/stability_rules.base.json",
                "config/rule_replay_golden_samples.json",
            ],
            "write_policy": "preview_only_no_config_write",
        }

    def _preview_analysis_rule_update_payload(
        self,
        service: object | None,
        *,
        path_override: str | None,
        updates: Mapping[str, Any],
        entrypoint: Mapping[str, Any],
    ) -> dict[str, Any]:
        if service is not None:
            edit_request = self._rule_update_edit_request(updates)
            preview_rule_update_method = getattr(service, "preview_rule_update", None)
            if callable(preview_rule_update_method):
                result = self._call_rule_service_method(
                    preview_rule_update_method,
                    (
                        ((edit_request["patch"],), {"path": path_override}),
                        ((), {"patch": edit_request["patch"], "path": path_override}),
                        ((edit_request["patch"],), {}),
                    ),
                )
                if result is not None:
                    return self._rule_update_service_preview_payload(result, path_override=path_override)

            build_edit_plan_method = getattr(service, "build_rule_edit_plan", None)
            if callable(build_edit_plan_method):
                attempts: list[tuple[tuple[object, ...], dict[str, object]]] = []
                single_edit = edit_request.get("single_edit")
                if isinstance(single_edit, Mapping):
                    attempts.append(
                        (
                            (),
                            {
                                "section": single_edit.get("section"),
                                "key": single_edit.get("key"),
                                "value": single_edit.get("value"),
                                "path": path_override,
                            },
                        )
                    )
                attempts.extend(
                    (
                        ((), {"patch": edit_request["patch"], "path": path_override}),
                        ((), {"patch": edit_request["patch"]}),
                    )
                )
                result = self._call_rule_service_method(build_edit_plan_method, tuple(attempts))
                if result is not None:
                    return self._rule_update_service_preview_payload(result, path_override=path_override)

            preview_method = getattr(service, "preview_analysis_rule_update", None)
            if callable(preview_method):
                result = self._call_rule_service_method(
                    preview_method,
                    (
                        ((), {"path": path_override, "updates": dict(updates)}),
                        ((dict(updates),), {"path": path_override}),
                        ((path_override, dict(updates)), {}),
                        ((), {"updates": dict(updates)}),
                    ),
                )
                if result is not None:
                    result.setdefault("source", "service")
                    result.setdefault("write_policy", "preview_only_no_config_write")
                    return result

        editable_fields = {str(item) for item in list(entrypoint.get("editable_fields", []) or [])}
        requested_fields = [str(key) for key in updates.keys()]
        return {
            "source": "fallback",
            "contract_version": "asl.rule_update_preview.v1",
            "config_path": str(entrypoint.get("config_path", "") or path_override or ""),
            "current_version": str(entrypoint.get("current_version", "") or ""),
            "updates": dict(updates),
            "changed_field_count": len(updates),
            "unknown_fields": [field for field in requested_fields if editable_fields and field not in editable_fields],
            "validation": dict(entrypoint.get("validation", {}) or {}),
            "risk_prompts": list(entrypoint.get("risk_prompts", []) or []),
            "recommended_flow": list(entrypoint.get("recommended_flow", []) or []),
            "related_policy_files": list(entrypoint.get("related_policy_files", []) or []),
            "write_policy": "preview_only_no_config_write",
        }

    @classmethod
    def _rule_update_service_preview_payload(
        cls,
        result: Mapping[str, Any],
        *,
        path_override: str | None,
    ) -> dict[str, Any]:
        payload = dict(result)
        payload.setdefault("source", "service")
        payload.setdefault("write_policy", "preview_only_no_config_write")
        if "config_path" not in payload and payload.get("rule_path"):
            payload["config_path"] = payload["rule_path"]
        if "config_path" not in payload and path_override:
            payload["config_path"] = path_override
        if "changed_field_count" not in payload:
            patch = payload.get("patch", {})
            payload["changed_field_count"] = cls._rule_patch_field_count(patch if isinstance(patch, Mapping) else {})
        return payload

    @classmethod
    def _rule_update_edit_request(cls, updates: Mapping[str, Any]) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        parsed_edits: list[dict[str, Any]] = []
        for raw_key, value in updates.items():
            section, key = cls._rule_update_section_key(str(raw_key))
            if section and key:
                section_patch = patch.setdefault(section, {})
                if isinstance(section_patch, dict):
                    section_patch[key] = value
                parsed_edits.append({"section": section, "key": key, "value": value})
            else:
                patch[str(raw_key)] = value
        return {
            "patch": patch,
            "single_edit": parsed_edits[0] if len(parsed_edits) == 1 and len(updates) == 1 else None,
        }

    @staticmethod
    def _rule_update_section_key(raw_key: str) -> tuple[str | None, str | None]:
        key = raw_key.strip()
        if "." in key:
            section, field = key.split(".", 1)
            section = section.strip()
            field = field.strip()
            if section and field:
                return section, field
        if key == "version":
            return "fingerprint", "version"
        return None, None

    @staticmethod
    def _rule_patch_field_count(patch: Mapping[str, Any]) -> int:
        count = 0
        for value in patch.values():
            if isinstance(value, Mapping):
                count += len(value)
            else:
                count += 1
        return count

    def _call_rule_service_method(
        self,
        method: object,
        attempts: Sequence[tuple[tuple[object, ...], dict[str, object]]],
    ) -> dict[str, Any] | None:
        for args, kwargs in attempts:
            clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
            try:
                result = method(*args, **clean_kwargs)  # type: ignore[misc]
            except TypeError:
                continue
            except Exception:
                return None
            return self._jsonable_mapping(result)
        return None

    @staticmethod
    def _rule_validation_payload(item: object) -> dict[str, Any]:
        return {
            "path": str(getattr(item, "path", "") or ""),
            "source_exists": bool(getattr(item, "source_exists", False)),
            "valid": bool(getattr(item, "valid", False)),
            "error_count": len(getattr(item, "errors", ()) or ()),
            "warning_count": len(getattr(item, "warnings", ()) or ()),
            "errors": list(getattr(item, "errors", ()) or ()),
            "warnings": list(getattr(item, "warnings", ()) or ()),
        }

    def _api_manifest_payload(
        self,
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return portal_payloads.api_manifest_payload(
            portal_mode=self._portal_mode(),
            deployment_label=self._portal_deployment_label(),
            public_base_url=self._portal_base_url(),
            callback_contract=self._integration_callback_contract_payload(),
            performance_risk_detail_fields=self._performance_risk_detail_fields(),
            request_context=request_context,
            surface=self._platform_surface(),
        )

    def _openapi_payload(
        self,
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        manifest = self._api_manifest_payload(request_context=request_context)
        return portal_payloads.openapi_payload(
            portal_mode=self._portal_mode(),
            public_base_url=self._portal_base_url(),
            manifest=manifest,
        )


__all__ = ["CorePayloadMixin"]
