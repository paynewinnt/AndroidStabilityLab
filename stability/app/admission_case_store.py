from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import (
    AdmissionCase,
    AdmissionCaseExecutionSummary,
    AdmissionCaseLifecycleEvent,
    AdmissionCaseRegressionSummary,
    AdmissionCaseRoleAuditEntry,
    AdmissionCaseScenarioCoverage,
    AdmissionCaseTopIssue,
    QualityGateRiskItem,
)
from stability.time_utils import format_beijing_datetime


class AdmissionCaseStore:
    """File-backed storage and JSON conversion for AdmissionCase."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.index_path = self.root_dir / "index.json"

    def load_case_for_baseline(self, baseline_key: str) -> AdmissionCase | None:
        key = baseline_key.strip()
        if not key:
            return None
        by_baseline = self.load_index().get(key, {})
        case_id = str(by_baseline.get("case_id", "") or "")
        return self.load_case(case_id) if case_id else None

    def load_case(self, case_id: str) -> AdmissionCase | None:
        payload = self.load_raw_case_payload(case_id)
        if not isinstance(payload, Mapping):
            return None
        try:
            return self.case_from_payload(payload)
        except (TypeError, ValueError):
            return None

    def load_raw_case_payload(self, case_id: str) -> dict[str, Any] | None:
        path = self.case_path(case_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return dict(payload) if isinstance(payload, Mapping) else None

    def write_case(self, case: AdmissionCase) -> None:
        path = self.case_path(case.case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.case_payload(case), ensure_ascii=False, indent=2), encoding="utf-8")
        index = self.load_index()
        index[str(case.baseline_key)] = {
            "case_id": str(case.case_id),
            "baseline_key": str(case.baseline_key),
            "report_id": str(case.report_id),
            "final_decision": str(case.final_decision),
            "error_code": str(case.error_code),
            "revision": int(case.revision),
            "status": str(case.status),
            "updated_at": isoformat_or_none(case.updated_at),
        }
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {}
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def case_path(self, case_id: str) -> Path:
        safe_case_id = case_id.replace("/", "_")
        return self.root_dir / safe_case_id / "case.json"

    @classmethod
    def case_payload(cls, item: AdmissionCase | None) -> dict[str, Any] | None:
        if item is None:
            return None
        payload = asdict(item)
        payload["quality_gate"] = None
        return json_ready(payload)

    @classmethod
    def case_from_payload(cls, payload: Mapping[str, Any]) -> AdmissionCase:
        prepared = dict(payload)
        prepared["created_at"] = datetime_or_none(prepared.get("created_at"))
        prepared["updated_at"] = datetime_or_none(prepared.get("updated_at"))
        prepared["execution_summary"] = AdmissionCaseExecutionSummary(
            **nested_payload(dict(prepared.get("execution_summary", {}) or {}), datetime_fields=("latest_run_created_at",))
        )
        prepared["top_issues"] = tuple(
            AdmissionCaseTopIssue(**nested_payload(dict(item), datetime_fields=("last_seen_at",)))
            for item in list(prepared.get("top_issues", ()) or ())
            if isinstance(item, Mapping)
        )
        prepared["regression_summary"] = AdmissionCaseRegressionSummary(
            **dict(prepared.get("regression_summary", {}) or {})
        )
        prepared["scenario_coverage"] = AdmissionCaseScenarioCoverage(
            **dict(prepared.get("scenario_coverage", {}) or {})
        )
        prepared["performance_risk_items"] = tuple(
            QualityGateRiskItem(**dict(item))
            for item in list(prepared.get("performance_risk_items", ()) or ())
        )
        prepared["lifecycle_events"] = tuple(
            AdmissionCaseLifecycleEvent(**nested_payload(dict(item), datetime_fields=("changed_at",)))
            for item in list(prepared.get("lifecycle_events", ()) or ())
            if isinstance(item, Mapping)
        )
        prepared["role_audit_entries"] = tuple(
            AdmissionCaseRoleAuditEntry(**nested_payload(dict(item), datetime_fields=("changed_at",)))
            for item in list(prepared.get("role_audit_entries", ()) or ())
            if isinstance(item, Mapping)
        )
        prepared["quality_gate"] = None
        prepared["override"] = None
        prepared["revision"] = max(int(prepared.get("revision", 1) or 1), 1)
        return AdmissionCase(**prepared)


def payload_revision_fingerprint(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    normalized = json_ready(dict(payload))
    normalized.pop("revision", None)
    normalized.pop("ci_contract", None)
    return normalized


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in dict(value).items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if hasattr(value, "__dict__"):
        return json_ready(vars(value))
    return value


def nested_payload(payload: Mapping[str, Any], *, datetime_fields: Sequence[str] = ()) -> dict[str, Any]:
    normalized = dict(payload)
    for field_name in datetime_fields:
        normalized[field_name] = datetime_or_none(normalized.get(field_name))
    return normalized


def datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def isoformat_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return format_beijing_datetime(value)
