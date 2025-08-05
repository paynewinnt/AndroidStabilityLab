from __future__ import annotations

from .application_common import *
from .pages_task_forms import ApplicationTaskFormsMixin
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class ApplicationTaskIntegrationPagesMixin(ApplicationTaskFormsMixin):
    def _task_detail_payload(
        self,
        task_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_service = getattr(self._bundle, "task_service", None)
        if task_service is None or not hasattr(task_service, "get_task"):
            raise ValueError("Task service is unavailable.")
        task = task_service.get_task(task_id)
        task_payload = self._describe_task_payload(task)
        run_history_service = getattr(self._bundle, "run_history_service", None)
        runs: list[dict[str, Any]] = []
        if run_history_service is not None and hasattr(run_history_service, "list_runs"):
            runs = self._decorate_runs_with_monitoring(list(run_history_service.list_runs(task_id=task_id, limit=30)))
        return {
            "page": "task_detail",
            "title": f"任务详情 · {task_payload.get('task_name', task_id) or task_id}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "query": dict(query or {}),
            "task": {
                **task_payload,
                "detail_path": f"/tasks/task/{quote(task_id, safe='')}",
                "api_path": f"/api/tasks/task/{quote(task_id, safe='')}",
            },
            "runs": runs,
        }

    def _unattended_detail_payload(
        self,
        task_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        unattended_service = getattr(self._bundle, "unattended_service", None)
        if unattended_service is None or not hasattr(unattended_service, "get_task_record"):
            raise ValueError("Unattended service is unavailable.")
        record = unattended_service.get_task_record(task_id)
        daily_report = {}
        weekly_report = {}
        if hasattr(unattended_service, "build_daily_report"):
            try:
                daily_report = self._unattended_daily_report_payload(unattended_service.build_daily_report(task_id=task_id))
            except Exception:
                daily_report = {}
        if hasattr(unattended_service, "build_weekly_report"):
            try:
                weekly_report = self._unattended_weekly_report_payload(unattended_service.build_weekly_report(task_id=task_id))
            except Exception:
                weekly_report = {}
        return {
            "page": "unattended_detail",
            "title": f"无人值守详情 · {task_id}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "query": dict(query or {}),
            "task": self._unattended_task_payload(record),
            "daily_report": daily_report,
            "weekly_report": weekly_report,
        }

    def _render_task_detail(self, payload: dict[str, Any]) -> str:
        task = dict(payload.get("task", {}) or {})
        runs = list(payload.get("runs", []) or [])
        body = [
            self._metric_grid(
                [
                    ("任务", task.get("task_name", "n/a") or "n/a"),
                    ("模板", task.get("template_type", "n/a") or "n/a"),
                    ("设备数", task.get("planned_device_count", 0)),
                    ("最近 Run", len(runs)),
                    ("采样间隔", dict(task.get("sampling_config", {}) or {}).get("interval_seconds", 0)),
                    ("创建人", task.get("created_by", "n/a") or "n/a"),
                ]
            ),
            self._section(
                "任务定义",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(task, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
            ),
            self._section("创建 Run", [self._task_detail_create_run_form(task, current_actor=dict(payload.get("current_actor", {}) or {}))]),
            self._section("关联 Runs", [self._run_table(runs)]),
        ]
        return self._layout(
            "任务详情",
            "这里对应 CLI 的 show-task，先确认任务定义，再从同页直接创建新的 Run。",
            "".join(body),
        )

    def _render_unattended_detail(self, payload: dict[str, Any]) -> str:
        task = dict(payload.get("task", {}) or {})
        daily_report = dict(payload.get("daily_report", {}) or {})
        weekly_report = dict(payload.get("weekly_report", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("Task ID", task.get("task_id", "n/a") or "n/a"),
                    ("启用", "yes" if task.get("enabled") else "no"),
                    ("间隔(分钟)", task.get("interval_minutes", 0)),
                    ("主设备", len(task.get("primary_device_ids", []) or [])),
                    ("备设备", len(task.get("backup_device_ids", []) or [])),
                    ("Due", "yes" if task.get("due") else "no"),
                ]
            ),
            self._section(
                "无人值守配置",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(task, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
            ),
            self._section("执行动作", [self._unattended_detail_actions_form(task, current_actor=dict(payload.get("current_actor", {}) or {}))]),
            self._section(
                "Latest Daily Report",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(daily_report, ensure_ascii=False, indent=2))
                    + "</pre>"
                    if daily_report
                    else self._notice("当前还没有可展示的日报。")
                ],
            ),
            self._section(
                "Latest Weekly Report",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(weekly_report, ensure_ascii=False, indent=2))
                    + "</pre>"
                    if weekly_report
                    else self._notice("当前还没有可展示的周报。")
                ],
            ),
        ]
        return self._layout(
            "无人值守详情",
            "这里对应 CLI 的 show-unattended-task，先看配置，再决定是否手动跑一轮或执行 patrol。",
            "".join(body),
        )

    def _render_integration(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        worker = dict(payload.get("worker", {}) or {})
        events = list(payload.get("events", []) or [])
        webhooks = list(payload.get("webhooks", []) or [])
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        operation_result = dict(payload.get("operation_result", {}) or {})
        if operation_result:
            body.append(
                self._section(
                    "本次操作结果",
                    ["<pre class='mono'>" + escape(json.dumps(operation_result, ensure_ascii=False, indent=2)) + "</pre>"],
                )
            )
        body.extend(
            [
                self._metric_grid(
                    [
                        ("事件数", summary.get("event_count", 0)),
                        ("Webhook 数", summary.get("webhook_count", 0)),
                        ("IM Webhook", summary.get("im_webhook_count", 0)),
                        ("Feishu Webhook", summary.get("feishu_webhook_count", 0)),
                        ("CI Webhook", summary.get("ci_webhook_count", 0)),
                        ("缺陷 Webhook", summary.get("defect_webhook_count", 0)),
                        ("提测 Webhook", summary.get("release_webhook_count", 0)),
                        ("已送达", summary.get("delivered_count", 0)),
                        ("重试中", summary.get("retry_pending_count", 0)),
                        ("死信", summary.get("dead_letter_count", 0)),
                        ("告警事件", summary.get("alerting_event_count", 0)),
                    ]
                ),
                self._section(
                    "当前身份",
                    [
                        self._current_actor_card(
                            current_actor=dict(payload.get("current_actor", {}) or {}),
                            actors=list(self._collaboration_actors()),
                            current_path="/integration",
                        )
                    ],
                ),
                self._section("IM 通知", [self._integration_register_im_webhook_form(payload)]),
                self._section("Feishu/IM 验收摘要", [self._integration_im_acceptance_summary(payload)]),
                self._section("2h/24h 联调 Checklist", [self._integration_im_acceptance_checklist(payload)]),
                self._section("缺陷系统", [self._integration_register_defect_webhook_form(payload)]),
                self._section("提测平台", [self._integration_release_submission_forms(payload)]),
                self._section("Webhook 注册", [self._integration_register_webhook_form(payload)]),
                self._section("投递与 Worker", [self._integration_worker_forms(payload)]),
                self._section(
                    "回调合同",
                    ["<pre class='mono'>" + escape(json.dumps(dict(payload.get("callback_contract", {}) or {}), ensure_ascii=False, indent=2)) + "</pre>"],
                ),
                self._section(
                    "Worker 状态",
                    ["<pre class='mono'>" + escape(json.dumps(worker, ensure_ascii=False, indent=2)) + "</pre>"],
                ),
                self._section("已注册 Webhooks", [self._integration_webhook_cards(webhooks)]),
                self._section("最近事件", [self._integration_event_cards(events)]),
            ]
        )
        return self._layout(
            "集成 Outbox",
            "这里把 webhook 注册、IM 通知、缺陷同步、单轮投递、worker、dead-letter replay 和 CI 准入回传放到同一个本地运维入口里。",
            "".join(body),
        )

    def _task_detail_create_run_form(self, task: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        task_id = str(task.get("task_id", "") or "")
        device_selector = self._task_device_selector(
            [item for item in self._device_summaries() if bool(dict(item).get("is_schedulable", False))],
            allow_empty=False,
            label="目标设备",
        )
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>基于当前任务创建 Run</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            f"{device_selector}"
            "<label>metadata(JSON)<textarea name='metadata' rows='3' placeholder='例如 {\"source\":\"web\"}'></textarea></label>"
            "<div><button type='submit'>创建 Run</button></div>"
            "</form>"
            "</article></div>"
        )

    def _unattended_detail_actions_form(self, task: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        task_id = str(task.get("task_id", "") or "")
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>手动跑一轮</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/run-unattended-round', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            "<option value='default'>default</option>"
            "<option value='solox'>solox</option>"
            "<option value='perfetto'>perfetto</option>"
            "</select></label>"
            "<div><button type='submit'>执行轮次</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>触发 Patrol</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/patrol-unattended', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            "<option value='default'>default</option>"
            "<option value='solox'>solox</option>"
            "<option value='perfetto'>perfetto</option>"
            "</select></label>"
            "<div><button type='submit'>执行 Patrol</button></div>"
            "</form>"
            "</article>"
            "</div>"
        )

    def _integration_register_webhook_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>注册 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-webhook', current_actor=current_actor), quote=True)}' class='stack integration-two-column-form'>"
            "<div class='integration-form-grid'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 ci-sync' /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/webhook' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='admission_case.updated' placeholder='逗号分隔' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "<label>Delivery Channel<input type='text' name='delivery_channel' value='generic' /></label>"
            "</div>"
            "<div class='integration-form-footer'>"
            "<div class='meta'>外放边界：非本地 webhook 默认要求 https + signing_secret；投递头会携带签名、key id、idempotency key 和 delivery contract。</div>"
            "<button type='submit'>注册 Webhook</button>"
            "</div>"
            "</form></article></div>"
        )

    def _integration_register_im_webhook_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>注册 IM 通知 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-im-webhook', current_actor=current_actor), quote=True)}' class='stack integration-two-column-form'>"
            "<div class='integration-form-grid'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 team-im-notify' /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/im-bot' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空使用稳定 IM 事件集' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "</div>"
            "<div class='integration-form-footer'>"
            "<div class='meta'>IM 通知消息体使用 asl.im_notify.v1，会把协作、准入更新和 outbox 告警整理成可读消息再投递。</div>"
            "<button type='submit'>注册 IM Webhook</button>"
            "</div>"
            "</form></article></div>"
        )

    def _integration_register_defect_webhook_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>注册缺陷同步 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-defect-webhook', current_actor=current_actor), quote=True)}' class='stack integration-two-column-form'>"
            "<div class='integration-form-grid'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 defect-sync' /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/defect-bot' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空使用稳定缺陷事件集' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "</div>"
            "<div class='integration-form-footer'>"
            "<div class='meta'>缺陷消息体使用 asl.defect_sync.v1，会把 issue、缺陷映射、动作和 routing 信息整理成稳定合同再投递。</div>"
            "<button type='submit'>注册缺陷 Webhook</button>"
            "</div>"
            "</form></article></div>"
        )

    def _integration_im_acceptance_summary(self, payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("im_acceptance", {}) or {})
        duplicate_risk = dict(summary.get("duplicate_risk", {}) or {})
        noise_check = dict(summary.get("noise_check", {}) or {})
        metric_grid = self._metric_grid(
            [
                ("总事件数", summary.get("total_event_count", 0)),
                ("成功投递", summary.get("delivered_count", 0)),
                ("失败数", summary.get("failed_count", 0)),
                ("重试数", summary.get("retry_count", 0)),
                ("Dead Letter", summary.get("dead_letter_count", 0)),
                ("consumer_receipt", summary.get("consumer_receipt_count", 0)),
                ("deduplicated", summary.get("deduplicated_count", 0)),
                ("重复风险", duplicate_risk.get("level", "low") or "low"),
            ]
        )
        risk_items = "".join(
            f"<li>{escape(str(item))}</li>"
            for item in list(duplicate_risk.get("reasons", []) or [])
        )
        webhooks = ", ".join(str(item) for item in list(summary.get("webhook_names", []) or []) if str(item).strip())
        first_webhook = webhooks.split(", ")[0] if webhooks else ""
        cli_hint = "python -m stability.cli show-im-acceptance-summary --channel feishu_bot"
        if first_webhook:
            cli_hint += f" --webhook-name {first_webhook}"
        return (
            "<div class='stack'>"
            f"{metric_grid}"
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>重复风险提示</h3>"
            f"<ul>{risk_items or '<li>当前摘要未发现明显重复投递风险。</li>'}</ul>"
            f"<div class='meta'>候选重复 receipt={escape(str(duplicate_risk.get('duplicate_candidate_count', 0) or 0))}</div>"
            "</article>"
            "<article class='card stack'>"
            "<h3>噪声检查占位</h3>"
            f"<pre class='mono'>{escape(json.dumps(noise_check, ensure_ascii=False, indent=2))}</pre>"
            "</article>"
            "<article class='card stack'>"
            "<h3>CLI 验收入口</h3>"
            f"<div class='mono'>{escape(cli_hint)}</div>"
            f"<div class='meta'>目标 webhook：{escape(webhooks or '暂无 IM/Feishu webhook')}</div>"
            "</article>"
            "</div>"
            "</div>"
        )

    def _integration_im_acceptance_checklist(self, payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("im_acceptance", {}) or {})
        checklist = dict(summary.get("checklist", {}) or {})

        def _items(title: str, values: list[dict[str, Any]]) -> str:
            rows = "".join(
                "<li>"
                f"<strong>{escape(str(item.get('status', 'manual') or 'manual'))}</strong> "
                f"{escape(str(item.get('item', '') or ''))}"
                "</li>"
                for item in values
            )
            return (
                "<article class='card stack'>"
                f"<h3>{escape(title)}</h3>"
                f"<ul>{rows}</ul>"
                "</article>"
            )

        return (
            "<div class='cards'>"
            + _items("2h 联调", [dict(item) for item in list(checklist.get("two_hour", []) or []) if isinstance(item, Mapping)])
            + _items("24h 联调", [dict(item) for item in list(checklist.get("twenty_four_hour", []) or []) if isinstance(item, Mapping)])
            + "</div>"
        )

    def _integration_release_submission_forms(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        release_device_selector = self._task_device_selector(
            [item for item in self._device_summaries() if bool(dict(item).get("is_schedulable", False))],
            allow_empty=True,
            label="设备",
        )
        metric_selector = self._task_metric_selector(default_selected=("cpu", "memory"))
        return (
            "<div class='cards integration-release-stack'>"
            "<article class='card stack'>"
            "<h3>创建提测请求</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/create-release-submission', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>来源平台<input type='text' name='source_platform' value='' placeholder='例如 release-center' /></label>"
            "<label>来源请求 ID<input type='text' name='source_request_id' value='' placeholder='例如 REL-2026-001' /></label>"
            "<label>包名<input type='text' name='package_name' value='' placeholder='com.example.app' /></label>"
            "<label>版本名<input type='text' name='version_name' value='' placeholder='例如 1.0.1' /></label>"
            "<label>版本号<input type='text' name='version_code' value='' placeholder='例如 101' /></label>"
            "<label>Build ID<input type='text' name='build_id' value='' placeholder='例如 build-101' /></label>"
            "<label>发布通道<input type='text' name='release_channel' value='' placeholder='例如 beta / gray / store' /></label>"
            "<label>Owner Team<input type='text' name='owner_team' value='' placeholder='例如 android-client' /></label>"
            "<label>标题<input type='text' name='submission_title' value='' placeholder='留空则自动生成' /></label>"
            f"<label>模板<select name='template_type'>{self._task_template_options('cold_start_loop')}</select></label>"
            f"{release_device_selector}"
            f"{metric_selector}"
            "<label>采样间隔(秒)<input type='number' name='sampling_interval' value='5' min='0' /></label>"
            "<label>Monitoring Backend<select name='monitoring_backend'><option value=''>default</option><option value='solox'>solox</option><option value='perfetto'>perfetto</option></select></label>"
            "<label>立即执行<select name='execute_immediately'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Max Concurrency<input type='number' name='max_concurrency' value='1' min='1' /></label>"
            "<label>Retry Count<input type='number' name='retry_count' value='0' min='0' /></label>"
            f"{self._task_params_builder(wide=False, upload_url=self._actor_scoped_path('/tasks/actions/upload-apk', current_actor=current_actor), delete_url=self._actor_scoped_path('/tasks/actions/delete-apk', current_actor=current_actor))}"
            f"{self._json_textarea_with_help('task_params(JSON)', 'task_params', '例如 {\"loop_count\": 10}', self._task_params_help(), wide=False, rows=3)}"
            f"{self._json_textarea_with_help('metadata(JSON)', 'metadata', '例如 {\"source\":\"web\"}', self._metadata_help(), wide=False, rows=3)}"
            "<div class='integration-form-actions'><button type='submit'>创建提测请求</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>同步提测准入</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/sync-release-admission', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Submission ID<input type='text' name='submission_id' value='' placeholder='release_submission_...' /></label>"
            "<label>Baseline Key<input type='text' name='baseline_key' value='' placeholder='例如 device_offline_default' /></label>"
            "<div class='integration-form-actions'><button type='submit'>同步准入结论</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>注册提测 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-release-webhook', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 release-sync' /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/release-callback' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空使用稳定提测事件集' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>注册提测 Webhook</button></div>"
            "<div class='meta integration-form-wide'>提测消息体使用 asl.release_submission.v1，会把 submission、执行状态和准入同步结果按稳定合同投递。</div>"
            "</form>"
            "</article>"
            "</div>"
        )

    def _integration_worker_forms(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        worker = dict(payload.get("worker", {}) or {})
        webhook_names = ", ".join(list(worker.get("registered_webhook_names", []) or []))
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>单轮投递</h3>"
            f"<div class='meta'>已注册 webhook：{escape(webhook_names or '暂无')}</div>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/deliver-outbox', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Name<input type='text' name='webhook_name' value='' placeholder='ci-sync' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空表示全部' /></label>"
            "<label>Limit<input type='number' name='limit' value='20' min='1' /></label>"
            "<div class='integration-form-actions'><button type='submit'>执行单轮</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>Outbox Worker</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='逗号分隔；为空表示全部' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Rounds<input type='number' name='rounds' value='1' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<div class='integration-form-actions'><button type='submit'>执行 Worker</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>CI 回传 Worker</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-ci-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部 CI webhook' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='300' min='0' /></label>"
            "<label>Max Rounds<input type='number' name='max_rounds' value='1' min='0' /></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>执行 CI Worker</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>IM 通知 Worker</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-im-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<input type='hidden' name='channel' value='im_notify' />"
            "<label>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部 IM webhook' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='300' min='0' /></label>"
            "<label>Max Rounds<input type='number' name='max_rounds' value='1' min='0' /></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>执行 IM Worker</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>Feishu 通知 Worker</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-im-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<input type='hidden' name='channel' value='feishu_bot' />"
            "<label>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部 Feishu webhook' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='300' min='0' /></label>"
            "<label>Max Rounds<input type='number' name='max_rounds' value='1' min='0' /></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>执行 Feishu Worker</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>缺陷同步 Worker</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-defect-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部缺陷 webhook' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='300' min='0' /></label>"
            "<label>Max Rounds<input type='number' name='max_rounds' value='1' min='0' /></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>执行缺陷 Worker</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>提测同步 Worker</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-release-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部提测 webhook' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='300' min='0' /></label>"
            "<label>Max Rounds<input type='number' name='max_rounds' value='1' min='0' /></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>执行提测 Worker</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>Replay Dead Letters</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/replay-dead-letters', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Event IDs<input type='text' name='event_ids' value='' placeholder='逗号分隔；为空表示按筛选回放' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='逗号分隔' /></label>"
            "<label>Limit<input type='number' name='limit' value='20' min='1' /></label>"
            "<label>Execute<select name='execute'><option value='0'>仅预览</option><option value='1'>实际回放</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>处理 Dead Letter</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>同步 CI Admission 决策</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/sync-ci-decisions', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Name<input type='text' name='webhook_name' value='' placeholder='ci-sync' /></label>"
            "<label>CI Endpoint<input type='text' name='ci_endpoint' value='' placeholder='可选；缺 webhook 时自动注册' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='admission_case.updated' /></label>"
            "<label>Limit<input type='number' name='limit' value='20' min='1' /></label>"
            "<label>Query Limit<input type='number' name='query_limit' value='0' min='0' /></label>"
            "<label>Dry Run<select name='dry_run'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>同步 CI 决策</button></div>"
            "</form>"
            "</article>"
            "</div>"
        )

    def _integration_webhook_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前还没有注册 webhook。")
        return "<div class='cards'>" + "".join(
            "<article class='card stack'>"
            f"<h3>{escape(str(item.get('name', '') or ''))}</h3>"
            f"<div class='meta'>{escape(str(item.get('delivery_channel', '') or 'generic'))} / {escape(str(item.get('failure_policy', '') or 'retryable_http'))}</div>"
            f"<div><span class='mono'>{escape(str(item.get('url', '') or ''))}</span></div>"
            f"<div>event_types={escape(', '.join(item.get('subscribed_event_types', []) or []) or 'all')}</div>"
            f"<div>security_boundary={escape(str(item.get('security_boundary', '') or 'shared_remote_callback'))}</div>"
            + (
                f"<div>key_id={escape(str(item.get('signature_key_id', '') or 'v1'))}</div>"
                if str(item.get("signature_key_id", "") or "").strip()
                else ""
            )
            + "</article>"
            for item in items
        ) + "</div>"

    def _integration_event_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有可展示的 outbox 事件。")
        cards = []
        for item in items[:20]:
            payload = dict(item.get("payload", {}) or {})
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('event_type', '') or ''))}</h3>"
                f"<div class='meta'>{escape(str(item.get('event_id', '') or ''))}</div>"
                f"<div>status={escape(str(item.get('delivery_status', 'pending') or 'pending'))} / attempts={escape(str(item.get('attempt_count', 0) or 0))}</div>"
                f"<div>target={escape(str(item.get('target_type', '') or ''))}:{escape(str(item.get('target_id', '') or ''))}</div>"
                f"<div>idempotency_key=<span class='mono'>{escape(str(item.get('idempotency_key', '') or ''))}</span></div>"
                + (
                    f"<div>final_decision={escape(str(payload.get('final_decision', '') or ''))}</div>"
                    if str(payload.get("final_decision", "") or "").strip()
                    else ""
                )
                + (
                    f"<div class='meta'>last_error={escape(str(item.get('last_error', '') or ''))}</div>"
                    if str(item.get("last_error", "") or "").strip()
                    else ""
                )
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _unattended_task_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前还没有无人值守配置。")
        cards = []
        for item in items:
            task_id = str(item.get("task_id", "") or "")
            detail_path = f"/runner/unattended/{quote(task_id, safe='')}" if task_id else ""
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('task_name', '') or task_id or ''))}</h3>"
                f"<div class='meta'>task_id={escape(task_id)}</div>"
                f"<div>enabled={escape('yes' if item.get('enabled') else 'no')} / interval={escape(str(item.get('interval_minutes', 0) or 0))} min</div>"
                f"<div>primary={escape(', '.join(item.get('primary_device_ids', []) or []) or 'n/a')}</div>"
                f"<div>backup={escape(', '.join(item.get('backup_device_ids', []) or []) or 'n/a')}</div>"
                f"<div>{self._route_link('无人值守详情', detail_path)}</div>"
                "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _unattended_config_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        schedulable_devices = [item for item in self._device_summaries() if bool(dict(item).get("is_schedulable", False))]
        primary_device_selector = self._task_device_selector(
            schedulable_devices,
            allow_empty=True,
            label="主设备",
            field_name="devices",
            empty_title="不指定主设备",
            empty_hint="保存配置后由设备池自动调度",
        )
        backup_device_selector = self._task_device_selector(
            schedulable_devices,
            allow_empty=True,
            label="备设备",
            field_name="backup_devices",
            empty_title="不指定备设备",
            empty_hint="没有备份设备也可以保存",
        )
        task_options = "".join(
            f"<option value='{escape(str(item.get('task_id', '') or ''), quote=True)}'>{escape(str(item.get('task_name', '') or item.get('task_id', '') or ''))}</option>"
            for item in self._task_summaries(limit=100)
            if str(item.get("task_id", "") or "").strip()
        )
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>配置无人值守</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/configure-unattended', current_actor=current_actor), quote=True)}' class='stack unattended-config-form'>"
            "<div class='unattended-config-grid'>"
            "<label>任务<select name='task_id'>" + task_options + "</select></label>"
            "<label>间隔(分钟)<input type='number' name='interval_minutes' value='30' min='1' /></label>"
            "</div>"
            "<div class='unattended-device-grid'>"
            f"<div class='unattended-device-slot'>{primary_device_selector}</div>"
            f"<div class='unattended-device-slot'>{backup_device_selector}</div>"
            "</div>"
            "<div class='unattended-config-grid unattended-config-grid-compact'>"
            "<label>期望设备数<input type='number' name='desired_device_count' value='1' min='0' /></label>"
            "<label>失败阈值<input type='number' name='failure_threshold' value='3' min='0' /></label>"
            "<label>轮转策略<input type='text' name='rotation_strategy' value='round_robin' /></label>"
            "<label>轮转推进<input type='text' name='rotation_advance_policy' value='every_round' /></label>"
            "<label>立即开始<select name='start_now'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<label>禁用<select name='disabled'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "</div>"
            "<div class='unattended-form-actions'><button type='submit'>保存配置</button></div>"
            "</form></article></div>"
        )
