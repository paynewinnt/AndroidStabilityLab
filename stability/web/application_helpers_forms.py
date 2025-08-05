from __future__ import annotations

from .application_common import *
from stability.time_utils import format_beijing_datetime_or_original


class ApplicationFormHelpersMixin:
    @staticmethod
    def _query_overrides(query: Mapping[str, list[str]]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        raw_json = WebPortalApplication._form_value(dict(query), "overrides")
        if raw_json:
            try:
                decoded = json.loads(raw_json)
            except json.JSONDecodeError:
                decoded = {}
            if isinstance(decoded, Mapping):
                overrides.update({str(key): value for key, value in decoded.items()})
        for raw_item in query.get("override", []) or []:
            if "=" not in raw_item:
                continue
            key, raw_value = str(raw_item).split("=", 1)
            key = key.strip()
            if key:
                overrides[key] = WebPortalApplication._parse_scalar_override(raw_value.strip())
        for key, values in query.items():
            raw_key = str(key)
            if not raw_key.startswith("set."):
                continue
            field = raw_key.removeprefix("set.").strip()
            if field and values:
                overrides[field] = WebPortalApplication._parse_scalar_override(str(values[-1]).strip())
        return overrides

    @staticmethod
    def _parse_scalar_override(value: str) -> Any:
        if value == "":
            return ""
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @staticmethod
    def _expand_form_values(payload: Mapping[str, list[str]], key: str) -> list[str]:
        values = list(payload.get(key, []) or [])
        expanded: list[str] = []
        for raw in values:
            for item in str(raw).split(","):
                normalized = item.strip()
                if normalized:
                    expanded.append(normalized)
        return expanded

    @staticmethod
    def _json_form_object(payload: Mapping[str, list[str]], key: str) -> dict[str, Any]:
        raw = WebPortalApplication._form_value(dict(payload), key)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{key} must be valid JSON: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ValueError(f"{key} must be a JSON object.")
        return {str(k): v for k, v in data.items()}

    @staticmethod
    def _form_int(payload: Mapping[str, list[str]], key: str, *, default: int) -> int:
        raw = WebPortalApplication._form_value(dict(payload), key)
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    @staticmethod
    def _form_optional_int(payload: Mapping[str, list[str]], key: str) -> int | None:
        raw = WebPortalApplication._form_value(dict(payload), key)
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    @staticmethod
    def _form_bool(payload: Mapping[str, list[str]], key: str, *, default: bool) -> bool:
        raw = WebPortalApplication._form_value(dict(payload), key).lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _history_filter_link(
        *,
        baseline_key: str,
        label: str,
        action: str,
        comparison_only: bool,
        active: bool,
    ) -> str:
        query_parts: list[str] = []
        if action:
            query_parts.append(f"action={quote(action, safe='')}")
        if comparison_only:
            query_parts.append("comparison_only=1")
        suffix = f"?{'&'.join(query_parts)}" if query_parts else ""
        class_name = "pill" if active else "pill"
        return (
            f"<a class='{class_name}' href='/admission/baseline/{quote(baseline_key, safe='')}{suffix}'>"
            f"{escape(label)}</a>"
        )

    @staticmethod
    def _golden_diff_filter_link(
        *,
        payload: Mapping[str, Any],
        label: str,
        change_type: str = "",
        changed_field: str = "",
        active: bool,
    ) -> str:
        filters = dict(payload.get("filters", {}) or {})
        query_parts = [
            f"left_path={quote(str(payload.get('left_path', '') or ''), safe='')}",
            f"right_path={quote(str(payload.get('right_path', '') or ''), safe='')}",
        ]
        effective_change_type = change_type if (change_type or not changed_field) else str(filters.get("change_type", "") or "")
        effective_changed_field = changed_field if (changed_field or not change_type) else str(filters.get("changed_field", "") or "")
        if effective_change_type:
            query_parts.append(f"change_type={quote(effective_change_type, safe='')}")
        if effective_changed_field:
            query_parts.append(f"changed_field={quote(effective_changed_field, safe='')}")
        case_query = str(filters.get("case_query", "") or "")
        if case_query:
            query_parts.append(f"case_query={quote(case_query, safe='')}")
        if bool(filters.get("include_unchanged", False)):
            query_parts.append("include_unchanged=1")
        for item in list(filters.get("case_ids", []) or []):
            if str(item).strip():
                query_parts.append(f"case_id={quote(str(item), safe='')}")
        class_name = "pill" if active else "pill"
        return f"<a class='{class_name}' href='/goldens/diff?{'&'.join(query_parts)}'>{escape(label)}</a>"

    def _artifact_links(self, title: str, items: list[tuple[str, Any]]) -> str:
        return portal_renderers.artifact_links(title, items)

    @staticmethod
    def _route_link(label: str, path: Any) -> str:
        return portal_renderers.route_link(label, path)

    @staticmethod
    def _inline_link(label: str, path: Any) -> str:
        return portal_renderers.inline_link(label, path)

    @staticmethod
    def _sync_hint(sync_payload: dict[str, Any] | None) -> str:
        return portal_renderers.sync_hint(sync_payload)

    @staticmethod
    def _isoformat_or_none(value: Any) -> str | None:
        return format_beijing_datetime_or_original(value)

    @staticmethod
    def _filter_baseline_history(
        history: list[Any],
        *,
        action: str,
        comparison_only: bool,
    ) -> list[Any]:
        items = list(history)
        if action:
            items = [item for item in items if str(getattr(item, "action", "") or "") == action]
        if comparison_only:
            items = [item for item in items if str(getattr(item, "comparison_id", "") or "").strip()]
        return items

    @staticmethod
    def _filter_golden_diff_entries(
        entries: list[dict[str, Any]],
        *,
        change_type: str,
        changed_field: str,
        case_query: str,
    ) -> list[dict[str, Any]]:
        items = list(entries)
        if change_type:
            items = [item for item in items if str(item.get("change_type", "") or "") == change_type]
        if changed_field:
            items = [
                item
                for item in items
                if changed_field in {str(field) for field in list(item.get("changed_fields", []) or [])}
            ]
        if case_query:
            needle = case_query.lower()
            items = [item for item in items if needle in str(item.get("case_id", "") or "").lower()]
        return items

    @classmethod
    def _golden_diff_field_summary(
        cls,
        *,
        left_case: Mapping[str, Any],
        right_case: Mapping[str, Any],
        change_type: str,
        changed_fields: list[str],
    ) -> list[dict[str, str]]:
        if change_type == "added":
            return cls._presence_field_summary(side="right", case=right_case)
        if change_type == "removed":
            return cls._presence_field_summary(side="left", case=left_case)
        summaries: list[dict[str, str]] = []
        for field in changed_fields[:5]:
            summaries.append(
                {
                    "field": str(field),
                    "left": cls._format_diff_value(cls._resolve_case_path(left_case, str(field))),
                    "right": cls._format_diff_value(cls._resolve_case_path(right_case, str(field))),
                }
            )
        return summaries

    @classmethod
    def _golden_diff_block_summary(
        cls,
        *,
        left_case: Mapping[str, Any],
        right_case: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        block_specs = (
            ("baseline_rules", "Baseline Rules"),
            ("candidate_rules", "Candidate Rules"),
            ("filters", "Filters"),
            ("expected", "Expected"),
        )
        summaries: list[dict[str, Any]] = []
        for key, label in block_specs:
            left_value = left_case.get(key)
            right_value = right_case.get(key)
            if not cls._has_block_content(left_value) and not cls._has_block_content(right_value):
                continue
            summaries.append(
                {
                    "key": key,
                    "label": label,
                    "left_status": "present" if cls._has_block_content(left_value) else "missing",
                    "right_status": "present" if cls._has_block_content(right_value) else "missing",
                    "changed": left_value != right_value,
                    "left_preview": cls._block_preview(left_value),
                    "right_preview": cls._block_preview(right_value),
                }
            )
        return summaries

    @classmethod
    def _presence_field_summary(cls, *, side: str, case: Mapping[str, Any]) -> list[dict[str, str]]:
        present_value = {
            "description": cls._format_diff_value(case.get("description")),
            "issue_type": cls._format_diff_value(case.get("issue_type")),
            "layer": cls._format_diff_value(case.get("layer")),
            "expectation": cls._format_diff_value(case.get("expectation")),
        }
        left_missing = side == "right"
        return [
            {
                "field": key,
                "left": "missing" if left_missing else value,
                "right": value if left_missing else "missing",
            }
            for key, value in present_value.items()
            if value != "n/a"
        ]

    @staticmethod
    def _resolve_case_path(payload: Mapping[str, Any], path: str) -> Any:
        current: Any = payload
        for part in [item for item in str(path).split(".") if item]:
            if isinstance(current, Mapping) and part in current:
                current = current[part]
                continue
            return None
        return current

    @staticmethod
    def _has_block_content(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

    @classmethod
    def _block_preview(cls, value: Any) -> str:
        if not cls._has_block_content(value):
            return "missing"
        if isinstance(value, (dict, list, tuple)):
            try:
                return cls._format_diff_value(
                    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                )
            except TypeError:
                return cls._format_diff_value(str(value))
        return cls._format_diff_value(value)

    @staticmethod
    def _format_diff_value(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, (str, int, float, bool)):
            text = str(value)
        else:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if len(text) <= 96:
            return text
        return text[:56] + " ... " + text[-24:]

    @staticmethod
    def _bool_query(query: dict[str, list[str]], key: str, *, default: bool) -> bool:
        values = query.get(key, [])
        if not values:
            return default
        raw = str(values[0]).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _int_query(query: dict[str, list[str]], key: str, *, default: int) -> int:
        values = query.get(key, [])
        if not values:
            return default
        try:
            return max(0, int(values[0]))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _str_query(query: dict[str, list[str]], key: str) -> str:
        values = query.get(key, [])
        if not values:
            return ""
        return str(values[0]).strip()

    @staticmethod
    def _query_values(query: dict[str, list[str]], key: str) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in query.get(key, []) or []:
            for item in str(raw or "").split(","):
                value = item.strip()
                if value and value not in seen:
                    result.append(value)
                    seen.add(value)
        return result

    @staticmethod
    def _call_device_pool_service_method(method: object, *, group: str, team: str, tags: Sequence[str]) -> object:
        try:
            return method(group=group, team=team, tags=tuple(tags))  # type: ignore[misc]
        except TypeError:
            return method()  # type: ignore[misc]

    @staticmethod
    def _normalize_device_pools_payload(payload: object) -> dict[str, Any]:
        if isinstance(payload, Mapping):
            result = dict(payload)
        else:
            result = {"pools": list(payload or [])}
        result.setdefault("filters", {})
        result.setdefault("summary", {})
        result.setdefault("pools", [])
        return result

    @staticmethod
    def _object_payload(value: object) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "to_dict"):
            return dict(value.to_dict())  # type: ignore[no-any-return, attr-defined]
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return {}

    @classmethod
    def _candidate_device_payload(cls, value: object, *, schedulable: bool) -> dict[str, Any]:
        payload = cls._object_payload(value)
        profile = cls._object_payload(payload.get("profile", {}) or {})
        tags = profile.get("tags", ()) or ()
        reasons = list(payload.get("reasons", []) or [])
        return {
            "device_id": str(payload.get("device_id", "") or ""),
            "serial": str(payload.get("serial", "") or ""),
            "display_name": str(payload.get("display_name", "") or ""),
            "group_name": str(profile.get("group_name", "") or "ungrouped"),
            "team": str(profile.get("team_name", "") or "unassigned"),
            "tags": sorted({str(item).strip() for item in tags if str(item).strip()}),
            "is_online": "offline" not in reasons,
            "is_schedulable": bool(payload.get("schedulable", schedulable)),
            "score": int(payload.get("score", 0) or 0),
            "unschedulable_reasons": reasons,
            "profile": profile,
        }

    @staticmethod
    def _summary_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            key = str(item.get("key", "") or "").strip()
            if key:
                counts[key] = int(item.get("total_count", item.get("device_count", 0)) or 0)
        return dict(sorted(counts.items()))

    @staticmethod
    def _device_team(device: Mapping[str, Any]) -> str:
        metadata = dict(device.get("metadata", {}) or {})
        return str(
            device.get("team")
            or device.get("team_id")
            or device.get("team_name")
            or device.get("owner_team")
            or metadata.get("team")
            or metadata.get("team_id")
            or metadata.get("team_name")
            or metadata.get("owner_team")
            or "unassigned"
        )

    @staticmethod
    def _device_tags(device: Mapping[str, Any]) -> list[str]:
        return sorted({str(item).strip() for item in (device.get("tags", ()) or ()) if str(item).strip()})

    @classmethod
    def _unschedulable_reasons(cls, device: Mapping[str, Any]) -> list[str]:
        if bool(device.get("is_schedulable", False)):
            return []
        reasons: list[str] = []
        if not bool(device.get("is_online", False)):
            reasons.append("offline")
        availability = str(device.get("availability_state", "") or "").strip()
        if availability and availability not in {"idle", "available"}:
            reasons.append(f"availability:{availability}")
        connection = str(device.get("connection_state", "") or "").strip()
        if connection and connection not in {"connected", "online"}:
            reasons.append(f"connection:{connection}")
        if str(device.get("current_instance_id", "") or "").strip():
            reasons.append("busy")
        if not reasons:
            reasons.append("not_schedulable")
        return sorted(set(reasons))

    @staticmethod
    def _form_value(payload: dict[str, list[str]], key: str) -> str:
        values = payload.get(key, [])
        if not values:
            return ""
        return str(values[0]).strip()

    @classmethod
    def _required_form_value(cls, payload: dict[str, list[str]], key: str) -> str:
        value = cls._form_value(payload, key)
        if not value:
            raise ValueError(f"Missing form parameter: {key}")
        return value
