from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping

from stability.scenario.registry import get_scenario_definition


class PerformanceFormattingHelpersMixin:
    @classmethod
    def _task_template_cell(cls, template_type: str) -> str:
        template = str(template_type or "").strip()
        if not template:
            return "n/a"
        try:
            definition = get_scenario_definition(template)
        except KeyError:
            return f"<span class='mono'>{escape(template)}</span>"
        return (
            f"<div><span class='mono'>{escape(template)}</span> - {escape(definition.chinese_name)}</div>"
            f"<div class='meta'>{escape(definition.description)}</div>"
        )

    @staticmethod
    def _display_datetime(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.replace("T", " ", 1)
    @staticmethod
    def _compact_value_text(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, Mapping):
            return json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value if str(item))
        return str(value)


__all__ = ["PerformanceFormattingHelpersMixin"]
