from __future__ import annotations

from html import escape
from typing import Any, Mapping
from urllib.parse import quote

from .cards_page import RunnerCardsPageMixin
from .core_page import RunnerCorePageMixin


class RunnerPageMixin(RunnerCorePageMixin):
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
            empty_title="没有备份设备也可以保存",
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
            "<label>任务<select name='task_id' required>" + task_options + "</select></label>"
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

__all__ = ["RunnerPageMixin", "RunnerCardsPageMixin"]
