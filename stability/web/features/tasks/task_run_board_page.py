from __future__ import annotations

from html import escape
from urllib.parse import quote
from typing import Any, Mapping, Sequence


class TaskRunBoardPageMixin:
    def _task_run_board(self, payload: Mapping[str, Any]) -> str:
        tasks = list(payload.get("tasks", []) or [])
        if not tasks:
            return self._notice("当前没有任务定义。")
        current_actor = dict(payload.get("current_actor", {}) or {})
        cards: list[str] = []
        modals: list[str] = []
        for task in tasks:
            task_payload = dict(task or {})
            task_id = str(task_payload.get("task_id", "") or "")
            modal_id = f"task-runs-{self._dom_id_fragment(task_id)}"
            task_name = str(
                task_payload.get("task_name", "") or task_id or "未命名任务"
            )
            cards.append(
                self._task_run_row(
                    task_payload, modal_id=modal_id, current_actor=current_actor
                )
            )
            modals.append(
                self._task_modal(
                    modal_id,
                    f"Run 列表 · {task_name}",
                    self._task_run_modal_body(
                        task_payload, payload=payload, current_actor=current_actor
                    ),
                )
            )
        return (
            "<div class='task-run-board'>"
            "<div class='task-run-board-head'>"
            "<div><h3>任务列表</h3><span>每个任务直接管理自己的 Run：创建、执行、停止、查看详情和归档都在同一行完成。</span></div>"
            "<a class='action-link' href='/tasks?show_archived=1'>查看归档任务</a>"
            "</div>"
            "<div class='task-run-list'>"
            + "".join(cards)
            + "</div></div>"
            + "".join(modals)
        )

    def _task_run_row(
        self,
        task: Mapping[str, Any],
        *,
        modal_id: str,
        current_actor: Mapping[str, Any],
    ) -> str:
        task_id = str(task.get("task_id", "") or "")
        task_name = str(task.get("task_name", "") or task_id or "未命名任务")
        package_name = str(task.get("package_name", "") or "n/a")
        template_cell = self._task_template_cell(
            str(task.get("template_type", "") or "")
        )
        created_at = self._display_datetime(task.get("created_at", "")) or "n/a"
        archived = bool(task.get("archived") or task.get("hidden"))
        latest_status = str(task.get("latest_run_status", "") or "no_run")
        run_count = int(task.get("run_count", 0) or 0)
        active_count = int(task.get("active_run_count", 0) or 0)
        archive_action = (
            self._task_archive_inline_form(task_id, current_actor=dict(current_actor))
            if task_id and not archived
            else ""
        )
        return (
            f"<article class='task-run-row{' archived-record' if archived else ''}'>"
            "<div class='task-run-main'>"
            f"<h3 title='{escape(task_name, quote=True)}'>{escape(task_name)}</h3>"
            "<div class='task-run-subline'>"
            f"<div>{template_cell}</div>"
            f"<span class='mono' title='{escape(package_name, quote=True)}'>{escape(package_name)}</span>"
            f"<span class='mono' title='{escape(task_id, quote=True)}'>id:{escape(task_id)}</span>"
            f"<span>{escape(created_at)}</span>"
            "</div>"
            "</div>"
            "<div class='task-run-metrics'>"
            + self._task_run_metric("Run", run_count)
            + self._task_run_metric("最新", latest_status)
            + self._task_run_metric("运行中", active_count)
            + "</div>"
            "<div class='task-row-actions'>"
            f"<button type='button' class='task-run-primary-button' data-task-modal-target='{escape(modal_id, quote=True)}'>Run</button>"
            + self._route_link_new_tab(
                "任务详情", f"/tasks/task/{quote(task_id, safe='')}" if task_id else ""
            )
            + archive_action
            + ("<span class='pill'>已归档</span>" if archived else "")
            + "</div>"
            "</article>"
        )

    @staticmethod
    def _task_run_metric(label: str, value: object) -> str:
        return (
            "<span class='task-run-metric'>"
            f"<small>{escape(label)}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
        )

    def _task_run_modal_body(
        self,
        task: Mapping[str, Any],
        *,
        payload: Mapping[str, Any],
        current_actor: Mapping[str, Any],
    ) -> str:
        runs = list(task.get("runs", []) or [])
        return (
            "<div class='task-run-modal-stack'>"
            + self._task_run_create_inline_form(
                task, payload=payload, current_actor=current_actor
            )
            + self._task_run_entries(runs, current_actor=current_actor)
            + "</div>"
        )

    def _task_run_create_inline_form(
        self,
        task: Mapping[str, Any],
        *,
        payload: Mapping[str, Any],
        current_actor: Mapping[str, Any],
    ) -> str:
        task_id = str(task.get("task_id", "") or "")
        selected_devices = set(
            str(item) for item in list(task.get("selected_device_ids", []) or [])
        )
        device_select = self._task_run_device_select(
            list(payload.get("schedulable_devices", []) or []),
            selected_devices=selected_devices,
        )
        return (
            "<section class='task-run-modal-section'>"
            "<div class='task-run-modal-section-head'><strong>创建 Run</strong><span>默认优先选中任务已绑定设备，可临时改成设备池里的其他设备。</span></div>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='task-run-create-form'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            f"{device_select}"
            "<label>metadata(JSON)<textarea name='metadata' rows='2' placeholder='例如 {\"source\":\"tasks-page\"}'></textarea></label>"
            "<div class='form-actions'><button type='submit'>创建 Run</button></div>"
            "</form>"
            "</section>"
        )

    @staticmethod
    def _task_run_device_select(
        devices: Sequence[Mapping[str, Any]],
        *,
        selected_devices: set[str],
    ) -> str:
        options = []
        for item in devices:
            device_id = str(item.get("device_id", "") or "")
            if not device_id:
                continue
            label_parts = [
                device_id,
                str(item.get("model", "") or item.get("product", "") or "").strip(),
                str(item.get("connection_state", "") or "").strip(),
            ]
            label = " / ".join(part for part in label_parts if part)
            selected = " selected" if device_id in selected_devices else ""
            options.append(
                f"<option value='{escape(device_id, quote=True)}'{selected}>{escape(label)}</option>"
            )
        if not options:
            return "<div class='notice warning'>当前没有可调度设备，先到设备池刷新或连接设备。</div>"
        return (
            "<label>设备<select name='device' multiple required>"
            + "".join(options)
            + "</select></label>"
        )

    def _task_run_entries(
        self, runs: Sequence[Mapping[str, Any]], *, current_actor: Mapping[str, Any]
    ) -> str:
        if not runs:
            return (
                "<section class='task-run-modal-section'>"
                + self._notice("这个任务还没有 Run，先在上方创建一条。")
                + "</section>"
            )
        entries = "".join(
            self._task_run_entry(dict(run), current_actor=current_actor) for run in runs
        )
        return (
            "<section class='task-run-modal-section'>"
            "<div class='task-run-modal-section-head'><strong>Run 列表</strong><span>只展示最近关联记录；完整细节从 Run 详情继续下钻。</span></div>"
            "<div class='task-run-entry-list'>" + entries + "</div></section>"
        )

    def _task_run_entry(
        self, run: Mapping[str, Any], *, current_actor: Mapping[str, Any]
    ) -> str:
        run_id = str(run.get("run_id", "") or "")
        run_status = str(run.get("run_status", "") or "unknown")
        short_run_id = run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
        devices = ", ".join(run.get("target_device_ids", []) or []) or "n/a"
        monitoring_summary = dict(run.get("monitoring_summary", {}) or {})
        monitor_line = str(
            monitoring_summary.get("summary_line", "未发现监控快照") or "未发现监控快照"
        )
        return (
            "<article class='task-run-entry'>"
            "<div class='task-run-entry-head'>"
            f"<strong class='mono' title='{escape(run_id, quote=True)}'>{escape(short_run_id or 'n/a')}</strong>"
            f"<span class='pill'>{escape(run_status)}</span>"
            "</div>"
            "<div class='task-run-entry-meta'>"
            f"<span><b>设备</b>{escape(devices)}</span>"
            f"<span><b>创建</b>{escape(self._display_datetime(run.get('created_at', '')) or 'n/a')}</span>"
            f"<span class='task-run-entry-wide'><b>监控</b>{escape(monitor_line)}</span>"
            "</div>"
            "<div class='task-run-entry-actions'>"
            + self._route_link_new_tab("Run 详情", run.get("detail_path", ""))
            + self._route_link_new_tab(
                "产物", f"/artifacts/run/{quote(run_id, safe='')}" if run_id else ""
            )
            + self._route_link_new_tab("Run JSON", run.get("api_path", ""))
            + self._task_run_execute_inline_form(run, current_actor=current_actor)
            + self._task_run_stop_inline_form(run, current_actor=current_actor)
            + "</div>"
            "</article>"
        )

    def _task_run_execute_inline_form(
        self, run: Mapping[str, Any], *, current_actor: Mapping[str, Any]
    ) -> str:
        if not self._run_can_execute(run):
            return ""
        run_id = str(run.get("run_id", "") or "")
        return (
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/execute-run', current_actor=current_actor), quote=True)}' class='task-run-action-form task-run-execute-form'>"
            f"<input type='hidden' name='run_id' value='{escape(run_id, quote=True)}' />"
            "<label>Backend<select name='monitoring_backend'><option value='default'>default</option><option value='solox'>solox</option><option value='perfetto'>perfetto</option><option value='solox_perfetto'>solox_perfetto</option></select></label>"
            "<label>并发<input type='number' name='max_concurrency' value='1' min='1' /></label>"
            "<label>重试<input type='number' name='retry_count' value='0' min='0' /></label>"
            "<button type='submit'>执行</button>"
            "</form>"
        )

    def _task_run_stop_inline_form(
        self, run: Mapping[str, Any], *, current_actor: Mapping[str, Any]
    ) -> str:
        if not self._run_can_stop(run):
            return ""
        run_id = str(run.get("run_id", "") or "")
        return (
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/stop-run', current_actor=current_actor), quote=True)}' class='task-run-action-form task-run-stop-form'>"
            f"<input type='hidden' name='run_id' value='{escape(run_id, quote=True)}' />"
            "<input type='hidden' name='reason' value='user_stopped' />"
            "<button type='submit' class='danger-inline-button'>停止</button>"
            "</form>"
        )

    @staticmethod
    def _run_can_execute(run: Mapping[str, Any]) -> bool:
        status = str(run.get("run_status", "") or "").lower()
        if status in {"success", "failed", "cancelled", "partial_failed", "running"}:
            return False
        counts = dict(run.get("instance_status_counts", {}) or {})
        return not any(
            str(key) in {"running", "preparing", "stopping", "collecting"}
            and int(value or 0) > 0
            for key, value in counts.items()
        )

    @staticmethod
    def _run_can_stop(run: Mapping[str, Any]) -> bool:
        status = str(run.get("run_status", "") or "").lower()
        if status in {"success", "failed", "cancelled", "partial_failed"}:
            return False
        counts = dict(run.get("instance_status_counts", {}) or {})
        active_states = {"pending", "preparing", "running", "stopping", "collecting"}
        return status in {"queued", "pending", "running"} or any(
            str(key) in active_states and int(value or 0) > 0
            for key, value in counts.items()
        )

    @staticmethod
    def _dom_id_fragment(value: str) -> str:
        safe = "".join(
            ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "")
        )
        return safe or "unknown"
