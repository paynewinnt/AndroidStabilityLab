from __future__ import annotations

from .application_common import *


class ApplicationRunnerCardsPagesMixin:
    @staticmethod
    def _platform_health_card(payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        checks = list(payload.get("checks", []) or [])
        status = str(payload.get("status", "unknown") or "unknown")
        severity = str(payload.get("severity", "unknown") or "unknown")
        rows = []
        for item in checks[:6]:
            check = dict(item or {})
            rows.append(
                "<tr>"
                f"<td>{escape(str(check.get('name', '') or check.get('category', 'unknown')))}</td>"
                f"<td>{escape(str(check.get('status', 'unknown') or 'unknown'))}</td>"
                f"<td>{escape(str(check.get('summary', '') or ''))}</td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr><th>检查项</th><th>状态</th><th>说明</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            if rows
            else "<div class='empty-state'>暂无平台健康检查。</div>"
        )
        return (
            "<article class='card stack'>"
            "<div class='runner-summary-row'>"
            f"<span class='runner-summary-chip'><small>平台健康</small><strong>{escape(status)}</strong></span>"
            f"<span class='runner-summary-chip'><small>严重度</small><strong>{escape(severity)}</strong></span>"
            f"<span class='runner-summary-chip'><small>失败检查</small><strong>{escape(str(summary.get('fail_count', 0) or 0))}</strong></span>"
            f"<span class='runner-summary-chip'><small>警告检查</small><strong>{escape(str(summary.get('warn_count', 0) or 0))}</strong></span>"
            "</div>"
            + table
            + "<div class='action-links'><a class='action-link' href='/api/platform-health'>查看平台健康 JSON</a></div>"
            + "</article>"
        )

    def _mini_device_list(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有设备摘要。")
        return (
            "<div class='home-today-list'><h3>设备</h3>"
            + "".join(
                "<article class='home-today-row'>"
                f"<strong>{escape(str(item.get('device_id', '') or 'unknown_device'))}</strong>"
                f"<span>{escape(str(item.get('brand', '') or 'unknown'))} {escape(str(item.get('model', '') or ''))}</span>"
                "<div class='home-today-pills'>"
                f"<span class='pill'>{escape(self._device_state_label(str(item.get('connection_state', '') or ''), empty='未同步'))}</span>"
                f"<span class='pill'>{escape(self._device_state_label(str(item.get('availability_state', '') or ''), empty='未同步'))}</span>"
                "</div>"
                "</article>"
                for item in items[:6]
            )
            + "</div>"
        )

    def _device_pool_cards(self, items: list[dict[str, Any]], *, current_actor: Mapping[str, Any] | None = None) -> str:
        if not items:
            return self._notice("当前过滤条件下没有设备池。")
        cards: list[str] = []
        action_path = self._actor_scoped_path(
            "/device-pools/actions/update-profile",
            current_actor=dict(current_actor or {}),
        )
        for item in items:
            schedulable_devices = list(item.get("schedulable_devices", []) or [])
            unschedulable_devices = list(item.get("unschedulable_devices", []) or [])
            schedulable_open = " open" if schedulable_devices else ""
            unschedulable_open = " open" if unschedulable_devices else ""
            cards.append(
                "<article class='card stack device-pool-card'>"
                f"<h3>{escape(str(item.get('group_name', '') or 'ungrouped'))} / {escape(str(item.get('team', '') or 'unassigned'))}</h3>"
                f"<div class='meta mono'>{escape(str(item.get('pool_key', '') or ''))}</div>"
                "<div>"
                f"<span class='pill'>devices={escape(str(item.get('device_count', 0)))}</span>"
                f"<span class='pill'>online={escape(str(item.get('online_device_count', 0)))}</span>"
                f"<span class='pill'>schedulable={escape(str(item.get('schedulable_device_count', 0)))}</span>"
                f"<span class='pill'>blocked={escape(str(item.get('unschedulable_device_count', 0)))}</span>"
                "</div>"
                f"<details class='device-pool-section'{schedulable_open}><summary>可调度设备</summary>{self._device_pool_device_editor_list(schedulable_devices, pool=item, blocked=False, action_path=action_path)}</details>"
                f"<details class='device-pool-section'{unschedulable_open}><summary>不可调度设备</summary>{self._device_pool_device_editor_list(unschedulable_devices, pool=item, blocked=True, action_path=action_path)}</details>"
                "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _device_pool_device_editor_list(
        self,
        devices: list[dict[str, Any]],
        *,
        pool: Mapping[str, Any],
        blocked: bool,
        action_path: str,
    ) -> str:
        if not devices:
            message = "当前没有不可调度设备" if blocked else "当前没有可调度设备"
            return f"<div class='empty-state'>{escape(message)}</div>"
        return "<div class='device-editor-list'>" + "".join(
            self._device_pool_device_editor(dict(device or {}), pool=pool, blocked=blocked, action_path=action_path)
            for device in devices
        ) + "</div>"

    @staticmethod
    def _device_pool_device_editor(
        device: Mapping[str, Any],
        *,
        pool: Mapping[str, Any],
        blocked: bool,
        action_path: str,
    ) -> str:
        device_id = str(device.get("device_id", "") or "").strip()
        group_name = str(device.get("group_name", "") or pool.get("group_name", "") or "").strip()
        team_name = str(device.get("team_name", "") or device.get("team", "") or pool.get("team", "") or "").strip()
        tags = [str(tag).strip() for tag in list(device.get("tags", []) or []) if str(tag).strip()]
        reasons = list(device.get("unschedulable_reasons", []) or [])
        connection_state = str(device.get("connection_state", "") or "").strip()
        availability_state = str(device.get("availability_state", "") or "").strip()
        if group_name == "ungrouped":
            group_name = ""
        if team_name in {"unassigned", "unteamed"}:
            team_name = ""
        state_text = "blocked" if blocked else "schedulable"
        tag_text = ", ".join(tags) if tags else "未标记"
        connection_text = ApplicationRunnerCardsPagesMixin._device_state_label(connection_state, empty="未同步")
        availability_text = ApplicationRunnerCardsPagesMixin._device_state_label(availability_state, empty="未同步")
        reason_text = ", ".join(str(reason) for reason in reasons) if reasons else "无阻塞"
        reason_block = (
            f"<div><span class='meta'>不可调度原因</span><strong>{escape(reason_text)}</strong></div>"
            if blocked
            else ""
        )
        return (
            "<article class='device-editor-card'>"
            "<div class='device-editor-head'>"
            f"<div><strong>{escape(device_id or 'unknown-device')}</strong><div class='meta'>{escape(state_text)}</div></div>"
            f"<div class='device-detail-grid {'is-blocked' if blocked else 'is-schedulable'}'>"
            f"<div><span class='meta'>Tag</span><strong>{escape(tag_text)}</strong></div>"
            f"<div><span class='meta'>连接状态</span><strong>{escape(connection_text)}</strong></div>"
            f"<div><span class='meta'>可用状态</span><strong>{escape(availability_text)}</strong></div>"
            f"{reason_block}"
            "</div>"
            "<details class='device-edit-section'>"
            "<summary>编辑标记</summary>"
            f"<form method='post' action='{escape(action_path, quote=True)}' class='device-inline-form'>"
            f"<input type='hidden' name='device_id' value='{escape(device_id, quote=True)}' />"
            "<div class='form-grid-three'>"
            f"<label>Group<input type='text' name='group_name' value='{escape(group_name, quote=True)}' placeholder='例如 lab-a' /></label>"
            f"<label>Team<input type='text' name='team_name' value='{escape(team_name, quote=True)}' placeholder='例如 android-client' /></label>"
            f"<label>Tag<input type='text' name='tags' value='{escape(','.join(tags), quote=True)}' placeholder='例如 smoke,android14' /></label>"
            "</div>"
            "<div class='form-actions'><button type='submit'>保存</button></div>"
            "</form>"
            "</details>"
            "</div>"
            "</article>"
        )

    @staticmethod
    def _device_state_label(value: str, *, empty: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return empty
        labels = {
            "connected": "在线",
            "online": "在线",
            "device": "在线",
            "offline": "离线",
            "error": "异常",
            "unauthorized": "未授权",
            "unknown": "未知",
            "idle": "空闲",
            "running": "运行中",
            "reserved": "已预留",
            "quarantined": "已隔离",
        }
        return labels.get(normalized.lower(), normalized)

    def _mini_run_list(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有可展示的 run。")
        return (
            "<div class='home-today-list'><h3>最近 Run</h3>"
            + "".join(
                "<article class='home-today-row'>"
                f"<strong>{escape(str(item.get('task_name', '未命名任务')))}</strong>"
                f"<span class='mono'>{escape(str(item.get('run_id', '') or 'n/a'))}</span>"
                f"<div class='home-today-pills'><span class='pill'>{escape(str(item.get('run_status', '') or 'unknown'))}</span></div>"
                "</article>"
                for item in items[:4]
            )
            + "</div>"
        )

    def _mini_issue_list(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有聚合问题。")
        return (
            "<div class='home-today-list'><h3>Top Issue</h3>"
            + "".join(
                "<article class='home-today-row'>"
                f"<strong>{escape(str(item.get('title', '') or '未命名问题'))}</strong>"
                f"<span>{escape(str(item.get('issue_type', '') or 'unknown'))} / {escape(str(item.get('severity', '') or 'unknown'))}</span>"
                f"<div class='home-today-pills'><span class='pill'>occ={escape(str(item.get('occurrence_count', 0)))}</span></div>"
                "</article>"
                for item in items[:4]
            )
            + "</div>"
        )

    def _runner_status_card(self, runner: Mapping[str, Any], *, include_link: bool = False) -> str:
        if not runner:
            return self._notice("当前没有可展示的 runner 状态。")
        last_patrol = dict(runner.get("last_patrol", {}) or {})
        latest_daily_report = dict(runner.get("latest_daily_report", {}) or {})
        daily_report_paths = dict(runner.get("daily_report_paths", {}) or {})
        latest_weekly_report = dict(runner.get("latest_weekly_report", {}) or {})
        weekly_report_paths = dict(runner.get("weekly_report_paths", {}) or {})
        blocks = [
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(runner.get('status', 'missing') or 'missing'))}</h3>"
            f"<div class='meta'>lock={escape(str(runner.get('lock_state', 'released') or 'released'))} / heartbeat={escape('present' if runner.get('heartbeat_present') else 'missing')}</div>"
            f"<div>pid：<span class='mono'>{escape(str(runner.get('pid', '') or 'n/a'))}</span></div>"
            f"<div>task_id：<span class='mono'>{escape(str(runner.get('task_id', '') or 'n/a'))}</span></div>"
            f"<div>cycle_count：{escape(str(runner.get('cycle_count', 0) or 0))} / active_cycle_index：{escape(str(runner.get('active_cycle_index', 0) or 0))}</div>"
            f"<div>last_heartbeat：{escape(str(runner.get('last_heartbeat_at', '') or 'n/a'))}</div>"
            f"<div>heartbeat_age_seconds：{escape(str(runner.get('heartbeat_age_seconds', 'n/a')))}</div>"
            f"<div>stopped_reason：{escape(str(runner.get('stopped_reason', '') or 'n/a'))}</div>"
            f"<div>paths：<span class='mono'>{escape(str(runner.get('lock_path', '') or 'n/a'))}</span></div>"
            + (
                f"<div>最近 patrol：executed={escape(str(last_patrol.get('executed_task_count', 0) or 0))} / failed_rate={escape(str(last_patrol.get('failed_rate', 0.0) or 0.0))} / offline_rate={escape(str(last_patrol.get('offline_rate', 0.0) or 0.0))}</div>"
                if last_patrol
                else "<div class='meta'>当前还没有最近一轮 patrol 摘要</div>"
            )
            + (
                f"<div>latest daily report：date={escape(str(latest_daily_report.get('report_date', '') or 'n/a'))} / rounds={escape(str(latest_daily_report.get('round_count', 0) or 0))} / failed_rounds={escape(str(latest_daily_report.get('failed_round_count', 0) or 0))}</div>"
                if latest_daily_report
                else "<div class='meta'>当前还没有 latest daily report 摘要</div>"
            )
            + (
                f"<div>daily report path：<span class='mono'>{escape(str(daily_report_paths.get('report_json_path', '') or 'n/a'))}</span></div>"
                if daily_report_paths
                else ""
            )
            + (
                f"<div>latest weekly report：week={escape(str(latest_weekly_report.get('week_key', '') or 'n/a'))} / rounds={escape(str(latest_weekly_report.get('round_count', 0) or 0))} / failed_rounds={escape(str(latest_weekly_report.get('failed_round_count', 0) or 0))}</div>"
                if latest_weekly_report
                else "<div class='meta'>当前还没有 latest weekly report 摘要</div>"
            )
            + (
                f"<div>weekly report path：<span class='mono'>{escape(str(weekly_report_paths.get('report_json_path', '') or 'n/a'))}</span></div>"
                if weekly_report_paths
                else ""
            )
            + (f"<div><a href='/runner'>打开后台巡检状态页</a></div>" if include_link else "")
            + "</article></div>"
        ]
        return "".join(blocks)

    def _runner_home_summary_cards(self, runner: Mapping[str, Any]) -> str:
        if not runner:
            return self._notice("当前没有可展示的 runner 摘要。")
        last_patrol = dict(runner.get("last_patrol", {}) or {})
        items = [
            ("Runner 状态", runner.get("status", "missing"), self._runner_home_metric_tone(kind="status", runner=runner)),
            ("锁状态", runner.get("lock_state", "released"), self._runner_home_metric_tone(kind="lock", runner=runner)),
            (
                "Heartbeat Age(s)",
                runner.get("heartbeat_age_seconds", "n/a"),
                self._runner_home_metric_tone(kind="heartbeat", runner=runner),
            ),
            ("Cycle 数", runner.get("cycle_count", 0), ""),
            ("最近执行任务", last_patrol.get("executed_task_count", 0), ""),
            (
                "今日日报轮次",
                dict(runner.get("latest_daily_report", {}) or {}).get("round_count", 0),
                self._runner_home_metric_tone(kind="daily_report", runner=runner),
            ),
            (
                "今日日报失败轮次",
                dict(runner.get("latest_daily_report", {}) or {}).get("failed_round_count", 0),
                self._runner_home_metric_tone(kind="daily_report_failures", runner=runner),
            ),
            (
                "本周周报轮次",
                dict(runner.get("latest_weekly_report", {}) or {}).get("round_count", 0),
                self._runner_home_metric_tone(kind="weekly_report", runner=runner),
            ),
            (
                "本周周报失败轮次",
                dict(runner.get("latest_weekly_report", {}) or {}).get("failed_round_count", 0),
                self._runner_home_metric_tone(kind="weekly_report_failures", runner=runner),
            ),
            (
                "最近隔离设备",
                last_patrol.get("quarantined_device_count", 0),
                "warning" if int(last_patrol.get("quarantined_device_count", 0) or 0) > 0 else "",
            ),
        ]
        return (
            "<section class='grid runner-home-grid'>"
            + "".join(
                portal_renderers.metric_card(label, value, tone=tone)
                for label, value, tone in items
            )
            + "</section>"
            + self._runner_home_daily_report_notice(runner)
            + self._runner_home_weekly_report_notice(runner)
            + self._runner_home_action_notice(runner)
            + "<p><a href='/runner'>继续查看完整巡检状态</a></p>"
        )

    def _runner_home_daily_report_notice(self, runner: Mapping[str, Any]) -> str:
        latest_daily_report = dict(runner.get("latest_daily_report", {}) or {})
        daily_report_paths = dict(runner.get("daily_report_paths", {}) or {})
        if not latest_daily_report:
            return self._notice("当前还没有 latest daily report。先等待下一轮 patrol 或手动执行日报构建。", tone="danger")
        health = self._runner_report_health(latest_daily_report, failure_tone="danger")
        parts = [
            f"latest daily report：{escape(str(latest_daily_report.get('report_date', '') or 'n/a'))}",
            f"rounds={escape(str(latest_daily_report.get('round_count', 0) or 0))}",
            f"failed_rounds={escape(str(latest_daily_report.get('failed_round_count', 0) or 0))}",
            f"quarantined={escape(str(latest_daily_report.get('quarantined_device_count', 0) or 0))}",
        ]
        if daily_report_paths.get("summary_markdown_path"):
            parts.append(f"summary={escape(str(daily_report_paths.get('summary_markdown_path', '')))}")
        tone = "info" if health["tone"] == "ok" else str(health["tone"])
        return self._notice(" / ".join(parts), tone=tone)

    def _runner_home_weekly_report_notice(self, runner: Mapping[str, Any]) -> str:
        latest_weekly_report = dict(runner.get("latest_weekly_report", {}) or {})
        weekly_report_paths = dict(runner.get("weekly_report_paths", {}) or {})
        if not latest_weekly_report:
            return self._notice("当前还没有 latest weekly report。先等待下一轮 patrol 或手动执行周报构建。")
        health = self._runner_report_health(latest_weekly_report, failure_tone="warning")
        parts = [
            f"latest weekly report：{escape(str(latest_weekly_report.get('week_key', '') or 'n/a'))}",
            f"active_days={escape(str(latest_weekly_report.get('active_day_count', 0) or 0))}",
            f"rounds={escape(str(latest_weekly_report.get('round_count', 0) or 0))}",
            f"failed_rounds={escape(str(latest_weekly_report.get('failed_round_count', 0) or 0))}",
            f"failed_rate={escape(str(latest_weekly_report.get('failed_rate', 0.0) or 0.0))}",
            f"offline_rate={escape(str(latest_weekly_report.get('offline_rate', 0.0) or 0.0))}",
            f"quarantined={escape(str(latest_weekly_report.get('quarantined_device_count', 0) or 0))}",
        ]
        top_issue_types = list(latest_weekly_report.get("top_issue_types", []) or [])
        if top_issue_types:
            top_issue = top_issue_types[0]
            parts.append(
                "top_issue="
                + escape(f"{top_issue.get('issue_type', '')}={top_issue.get('count', 0)}")
            )
        if weekly_report_paths.get("summary_markdown_path"):
            parts.append(f"summary={escape(str(weekly_report_paths.get('summary_markdown_path', '')))}")
        tone = "info" if health["tone"] == "ok" else str(health["tone"])
        return self._notice(" / ".join(parts), tone=tone)

    def _runner_daily_report_card(self, runner: Mapping[str, Any]) -> str:
        latest_daily_report = dict(runner.get("latest_daily_report", {}) or {})
        daily_report_paths = dict(runner.get("daily_report_paths", {}) or {})
        if not latest_daily_report:
            return self._notice("当前还没有 latest daily report。")
        metrics = [
            ("日报日期", latest_daily_report.get("report_date", "n/a") or "n/a"),
            ("轮次数", latest_daily_report.get("round_count", 0)),
            ("执行轮次", latest_daily_report.get("executed_round_count", 0)),
            ("失败轮次", latest_daily_report.get("failed_round_count", 0)),
            ("设备在线率", latest_daily_report.get("device_online_rate", 0.0)),
            ("失败率", latest_daily_report.get("failed_rate", 0.0)),
            ("掉线率", latest_daily_report.get("offline_rate", 0.0)),
            ("恢复成功率", latest_daily_report.get("recovery_success_rate", 0.0)),
            ("隔离设备", latest_daily_report.get("quarantined_device_count", 0)),
        ]
        path_block = ""
        if daily_report_paths:
            path_block = (
                "<pre class='mono'>"
                + escape(json.dumps(daily_report_paths, ensure_ascii=False, indent=2))
                + "</pre>"
            )
        task_summaries = list(latest_daily_report.get("task_summaries", []) or [])
        top_issue_types = list(latest_daily_report.get("top_issue_types", []) or [])
        extra = []
        if task_summaries:
            extra.append(
                "<div class='meta'>任务摘要："
                + " / ".join(
                    escape(
                        f"{item.get('task_id', '')}: rounds={item.get('round_count', 0)} failed={item.get('failed_round_count', 0)}"
                    )
                    for item in task_summaries[:3]
                )
                + "</div>"
            )
        if top_issue_types:
            extra.append(
                "<div class='meta'>Top Issue Types："
                + " / ".join(
                    escape(f"{item.get('issue_type', '')}={item.get('count', 0)}")
                    for item in top_issue_types[:3]
                )
                + "</div>"
            )
        return self._metric_grid(metrics) + "".join(extra) + path_block

    def _runner_weekly_report_card(self, runner: Mapping[str, Any]) -> str:
        latest_weekly_report = dict(runner.get("latest_weekly_report", {}) or {})
        weekly_report_paths = dict(runner.get("weekly_report_paths", {}) or {})
        if not latest_weekly_report:
            return self._notice("当前还没有 latest weekly report。")
        health = self._runner_report_health(latest_weekly_report, failure_tone="warning")
        metrics = [
            ("周键", latest_weekly_report.get("week_key", "n/a") or "n/a"),
            ("锚点日期", latest_weekly_report.get("anchor_date", "n/a") or "n/a"),
            ("周起始", latest_weekly_report.get("week_start_date", "n/a") or "n/a"),
            ("周结束", latest_weekly_report.get("week_end_date", "n/a") or "n/a"),
            ("轮次数", latest_weekly_report.get("round_count", 0)),
            ("执行轮次", latest_weekly_report.get("executed_round_count", 0)),
            ("失败轮次", latest_weekly_report.get("failed_round_count", 0)),
            ("活跃天数", latest_weekly_report.get("active_day_count", 0)),
            ("设备在线率", latest_weekly_report.get("device_online_rate", 0.0)),
            ("失败率", latest_weekly_report.get("failed_rate", 0.0)),
            ("掉线率", latest_weekly_report.get("offline_rate", 0.0)),
            ("恢复成功率", latest_weekly_report.get("recovery_success_rate", 0.0)),
            ("隔离设备", latest_weekly_report.get("quarantined_device_count", 0)),
        ]
        path_block = ""
        if weekly_report_paths:
            path_block = (
                "<pre class='mono'>"
                + escape(json.dumps(weekly_report_paths, ensure_ascii=False, indent=2))
                + "</pre>"
            )
        notice_block = ""
        if health["has_failures"] or health["has_quarantined"]:
            notice_block = self._notice(
                "本周周报已经累计失败轮次或隔离设备，建议结合 Daily Summaries、周任务摘要和最近异常 patrol 历史一起排查。",
                tone=str(health["tone"]),
            )
        elif health["has_rate_warning"]:
            notice_block = self._notice(
                "本周周报已经出现失败率或掉线率波动，建议结合 Daily Summaries 持续追踪异常是否持续扩散。",
                tone="warning",
            )
        daily_summaries = list(latest_weekly_report.get("daily_summaries", []) or [])
        task_summaries = list(latest_weekly_report.get("task_summaries", []) or [])
        interruption_rounds = list(latest_weekly_report.get("interruption_rounds", []) or [])
        top_issue_types = list(latest_weekly_report.get("top_issue_types", []) or [])
        extra = []
        if task_summaries:
            extra.append(
                "<div class='meta'>周任务摘要："
                + " / ".join(
                    escape(
                        f"{item.get('task_id', '')}: rounds={item.get('round_count', 0)} failed={item.get('failed_round_count', 0)}"
                    )
                    for item in task_summaries[:3]
                )
                + "</div>"
            )
        if daily_summaries:
            extra.append(
                "<div class='meta'>Daily Summaries："
                + " / ".join(
                    escape(
                        f"{item.get('report_date', '')}: rounds={item.get('round_count', 0)} failed={item.get('failed_round_count', 0)} offline={item.get('offline_event_count', 0)} quarantined={item.get('quarantined_device_count', 0)}"
                    )
                    for item in daily_summaries[:3]
                )
                + "</div>"
            )
        if interruption_rounds:
            extra.append(
                "<div class='meta'>Interruption Rounds："
                + " / ".join(
                    escape(
                        f"{item.get('task_id', '')}/{item.get('round_id', '')}: {item.get('status', '')}"
                    )
                    for item in interruption_rounds[:3]
                )
                + "</div>"
            )
        if top_issue_types:
            extra.append(
                "<div class='meta'>Top Issue Types："
                + " / ".join(
                    escape(f"{item.get('issue_type', '')}={item.get('count', 0)}")
                    for item in top_issue_types[:3]
                )
                + "</div>"
            )
        return notice_block + self._metric_grid(metrics) + "".join(extra) + path_block

    @staticmethod
    def _runner_home_metric_tone(*, kind: str, runner: Mapping[str, Any]) -> str:
        status = str(runner.get("status", "missing") or "missing").lower()
        lock_state = str(runner.get("lock_state", "released") or "released").lower()
        heartbeat_present = bool(runner.get("heartbeat_present", False))
        latest_daily_report = dict(runner.get("latest_daily_report", {}) or {})
        latest_weekly_report = dict(runner.get("latest_weekly_report", {}) or {})
        daily_health = WebPortalApplication._runner_report_health(latest_daily_report, failure_tone="danger")
        weekly_health = WebPortalApplication._runner_report_health(latest_weekly_report, failure_tone="warning")
        if kind == "status":
            if status in {"failed", "missing"}:
                return "danger"
            if status in {"running"}:
                return "ok" if lock_state == "active" else "warning"
            return "warning" if status in {"stopped"} else ""
        if kind == "lock":
            if lock_state == "stale":
                return "danger"
            if lock_state == "active":
                return "ok"
            return "warning" if heartbeat_present else ""
        if kind == "heartbeat":
            if not heartbeat_present:
                return "danger"
            if bool(runner.get("is_stale", False)):
                return "danger"
            return "ok" if status == "running" else ""
        if kind == "daily_report":
            if not latest_daily_report:
                return "warning"
            return str(daily_health["tone"])
        if kind == "daily_report_failures":
            if not latest_daily_report:
                return "warning"
            if daily_health["has_failures"]:
                return "danger"
            return "ok"
        if kind == "weekly_report":
            if not latest_weekly_report:
                return "warning"
            return str(weekly_health["tone"])
        if kind == "weekly_report_failures":
            if not latest_weekly_report:
                return "warning"
            if weekly_health["has_quarantined"]:
                return "danger"
            if weekly_health["has_failures"]:
                return "warning"
            return "ok"
        return ""

    def _runner_home_action_notice(self, runner: Mapping[str, Any]) -> str:
        status = str(runner.get("status", "missing") or "missing").lower()
        lock_state = str(runner.get("lock_state", "released") or "released").lower()
        heartbeat_present = bool(runner.get("heartbeat_present", False))
        latest_daily_report = dict(runner.get("latest_daily_report", {}) or {})
        latest_weekly_report = dict(runner.get("latest_weekly_report", {}) or {})
        daily_health = self._runner_report_health(latest_daily_report, failure_tone="danger")
        weekly_health = self._runner_report_health(latest_weekly_report, failure_tone="warning")
        if lock_state == "stale" or bool(runner.get("is_stale", False)):
            return self._notice_with_actions(
                "建议动作：先打开 `/runner` 确认 stale lock，再结合 JSON 心跳摘要判断旧 runner 是否仍存活。",
                tone="danger",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if not heartbeat_present or status == "missing":
            return self._notice_with_actions(
                "建议动作：先确认是否已经启动 `run-unattended-patrol-runner`，再用巡检页或 JSON 确认 `runner_status.json` 是否已生成。",
                tone="danger",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if status == "failed":
            return self._notice_with_actions(
                "建议动作：先查看 `stopped_reason` 和最近一轮 patrol 摘要，再决定是否重启 runner。",
                tone="danger",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if daily_health["has_failures"] or daily_health["has_quarantined"]:
            return self._notice_with_actions(
                "建议动作：runner 仍在运行，但今日日报已经出现失败轮次或隔离设备。先打开 `/runner` 对照 latest daily report、最近 patrol 和隔离设备变化。",
                tone="danger",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if latest_daily_report and daily_health["has_rate_warning"]:
            return self._notice_with_actions(
                "建议动作：今日日报已经出现失败率或掉线率波动。建议先打开 `/runner` 查看 latest daily report 和最近异常轮次。",
                tone="warning",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if status == "stopped":
            return self._notice_with_actions(
                "建议动作：当前 runner 已停止；如果需要持续巡检，先确认停止原因，再重新启动后台 runner。",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if weekly_health["has_failures"] or weekly_health["has_quarantined"]:
            return self._notice_with_actions(
                "建议动作：本周周报已经累计失败轮次或隔离设备。建议打开 `/runner` 对照 latest weekly report、Daily Summaries 和最近异常 patrol 历史。",
                tone="danger" if weekly_health["has_quarantined"] else "warning",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        if latest_weekly_report and weekly_health["has_rate_warning"]:
            return self._notice_with_actions(
                "建议动作：本周周报已经出现失败率或掉线率波动。建议打开 `/runner` 查看 latest weekly report、Daily Summaries 和最近异常轮次。",
                tone="warning",
                actions=[
                    ("打开 /runner", "/runner"),
                    ("查看 /api/runner", "/api/runner"),
                ],
            )
        return self._notice_with_actions(
            "当前 runner 状态正常，可直接下钻到巡检页或查看 JSON 摘要，继续确认最近一轮 patrol 细节。",
            actions=[
                ("打开 /runner", "/runner"),
                ("查看 /api/runner", "/api/runner"),
            ],
        )

    @staticmethod
    def _runner_report_health(
        report: Mapping[str, Any],
        *,
        failure_tone: str,
        quarantine_tone: str = "danger",
    ) -> dict[str, Any]:
        report_dict = dict(report or {})
        failed_round_count = int(report_dict.get("failed_round_count", 0) or 0)
        quarantined_device_count = int(report_dict.get("quarantined_device_count", 0) or 0)
        failed_rate = float(report_dict.get("failed_rate", 0.0) or 0.0)
        offline_rate = float(report_dict.get("offline_rate", 0.0) or 0.0)
        has_failures = failed_round_count > 0
        has_quarantined = quarantined_device_count > 0
        has_rate_warning = failed_rate > 0.0 or offline_rate > 0.0
        tone = "ok"
        if has_quarantined:
            tone = quarantine_tone
        elif has_failures:
            tone = failure_tone
        elif has_rate_warning:
            tone = "warning"
        return {
            "failed_round_count": failed_round_count,
            "quarantined_device_count": quarantined_device_count,
            "failed_rate": failed_rate,
            "offline_rate": offline_rate,
            "has_failures": has_failures,
            "has_quarantined": has_quarantined,
            "has_rate_warning": has_rate_warning,
            "tone": tone,
        }

    def _notice_with_actions(
        self,
        message: str,
        *,
        tone: str = "info",
        actions: list[tuple[str, str]] | None = None,
    ) -> str:
        class_name = "notice"
        if tone == "danger":
            class_name = "notice danger"
        elif tone == "warning":
            class_name = "notice warning"
        action_links = ""
        if actions:
            action_links = "<div class='action-links'>" + "".join(
                f"<a class='action-link' href='{escape(href, quote=True)}'>{escape(label)}</a>"
                for label, href in actions
            ) + "</div>"
        return f"<div class='{class_name}'>{escape(message)}{action_links}</div>"
