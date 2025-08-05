from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import (
    RuleReplayGoldenCaseDetail,
    RuleReplayGoldenCaseSummary,
    RuleReplayGoldenDiffEntry,
    RuleReplayGoldenDiffResult,
    RuleReplayGoldenSuiteListing,
)


class RuleReplayGoldenSuiteService:
    """Inspect, query, and diff replay golden suites stored on disk."""

    _DEFAULT_SUITE_PATH = "config/rule_replay_golden_samples.json"
    _REQUIRED_CASE_KEYS = frozenset(
        {
            "case_id",
            "description",
            "baseline_rules",
            "candidate_rules",
            "filters",
            "dataset",
            "expected",
        }
    )

    def __init__(self, *, default_suite_path: str = _DEFAULT_SUITE_PATH) -> None:
        self._default_suite_path = default_suite_path

    def list_cases(
        self,
        *,
        suite_path: str = "",
        case_ids: Sequence[str] | None = None,
        issue_type: str = "",
        layer: str = "",
        expectation: str = "",
        limit: int = 100,
    ) -> RuleReplayGoldenSuiteListing:
        path, payload = self._read_suite(suite_path)
        requested_ids = {item.strip() for item in (case_ids or ()) if str(item).strip()}
        summaries = [
            self._summary_from_case(item)
            for item in self._normalized_cases(payload, path=path)
        ]
        if requested_ids:
            summaries = [item for item in summaries if item.case_id in requested_ids]
        if issue_type:
            summaries = [item for item in summaries if item.issue_type == issue_type]
        if layer:
            summaries = [item for item in summaries if item.layer == layer]
        if expectation:
            summaries = [item for item in summaries if item.expectation == expectation]
        normalized_limit = max(0, int(limit))
        summaries = summaries[:normalized_limit]
        return RuleReplayGoldenSuiteListing(
            suite_path=str(path),
            suite_version=str(payload.get("suite_version", "") or ""),
            case_count=len(summaries),
            filters={
                "case_ids": list(requested_ids),
                "issue_type": issue_type,
                "layer": layer,
                "expectation": expectation,
                "limit": normalized_limit,
            },
            layer_counts=dict(Counter(item.layer for item in summaries if item.layer)),
            issue_type_counts=dict(Counter(item.issue_type for item in summaries if item.issue_type)),
            expectation_counts=dict(Counter(item.expectation for item in summaries if item.expectation)),
            cases=tuple(summaries),
        )

    def get_case(self, *, case_id: str, suite_path: str = "") -> RuleReplayGoldenCaseDetail:
        path, payload = self._read_suite(suite_path)
        for item in self._normalized_cases(payload, path=path):
            if str(item.get("case_id", "") or "") == case_id:
                return RuleReplayGoldenCaseDetail(
                    suite_path=str(path),
                    suite_version=str(payload.get("suite_version", "") or ""),
                    summary=self._summary_from_case(item),
                    payload=dict(item),
                )
        raise ValueError(f"Golden sample case not found: {case_id}")

    def diff_suites(
        self,
        *,
        left_path: str,
        right_path: str,
        case_ids: Sequence[str] | None = None,
        include_unchanged: bool = False,
    ) -> RuleReplayGoldenDiffResult:
        left_resolved, left_payload = self._read_suite(left_path)
        right_resolved, right_payload = self._read_suite(right_path)
        selected_ids = {item.strip() for item in (case_ids or ()) if str(item).strip()}
        left_cases = {
            str(item.get("case_id", "") or ""): item
            for item in self._normalized_cases(left_payload, path=left_resolved)
        }
        right_cases = {
            str(item.get("case_id", "") or ""): item
            for item in self._normalized_cases(right_payload, path=right_resolved)
        }
        case_id_pool = sorted(set(left_cases) | set(right_cases))
        if selected_ids:
            case_id_pool = [item for item in case_id_pool if item in selected_ids]

        entries: list[RuleReplayGoldenDiffEntry] = []
        for case_id in case_id_pool:
            left_case = left_cases.get(case_id)
            right_case = right_cases.get(case_id)
            if left_case is None:
                entries.append(
                    RuleReplayGoldenDiffEntry(
                        case_id=case_id,
                        change_type="added",
                        left_case={},
                        right_case=dict(right_case or {}),
                    )
                )
                continue
            if right_case is None:
                entries.append(
                    RuleReplayGoldenDiffEntry(
                        case_id=case_id,
                        change_type="removed",
                        changed_fields=tuple(),
                        left_case=dict(left_case),
                        right_case={},
                    )
                )
                continue
            changed_fields = tuple(self._diff_mapping("", left_case, right_case))
            if changed_fields:
                entries.append(
                    RuleReplayGoldenDiffEntry(
                        case_id=case_id,
                        change_type="modified",
                        changed_fields=changed_fields,
                        left_case=dict(left_case),
                        right_case=dict(right_case),
                    )
                )
            elif include_unchanged:
                entries.append(
                    RuleReplayGoldenDiffEntry(
                        case_id=case_id,
                        change_type="unchanged",
                        changed_fields=tuple(),
                        left_case=dict(left_case),
                        right_case=dict(right_case),
                    )
                )

        return RuleReplayGoldenDiffResult(
            left_path=str(left_resolved),
            right_path=str(right_resolved),
            left_suite_version=str(left_payload.get("suite_version", "") or ""),
            right_suite_version=str(right_payload.get("suite_version", "") or ""),
            diff_count=len(entries),
            change_counts=dict(Counter(item.change_type for item in entries)),
            entries=tuple(entries),
        )

    def _read_suite(self, suite_path: str | Path) -> tuple[Path, dict[str, Any]]:
        path = Path(str(suite_path or self._default_suite_path)).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Golden suite file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Golden suite file must be a JSON object: {path}")
        payload.setdefault("cases", [])
        if not isinstance(payload["cases"], list):
            raise ValueError(f"Golden suite 'cases' must be a JSON array: {path}")
        return path, payload

    def _normalized_cases(self, payload: Mapping[str, Any], *, path: Path) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(payload.get("cases", []) if isinstance(payload.get("cases", []), list) else []):
            if not isinstance(item, dict):
                raise ValueError(f"Golden suite case at index {index} must be a JSON object: {path}")
            missing = sorted(self._REQUIRED_CASE_KEYS - set(item.keys()))
            if missing:
                raise ValueError(
                    f"Golden suite case '{item.get('case_id', f'index-{index}')}' is missing keys: {', '.join(missing)}"
                )
            normalized.append(dict(item))
        return normalized

    @staticmethod
    def _summary_from_case(item: Mapping[str, Any]) -> RuleReplayGoldenCaseSummary:
        dataset = dict(item.get("dataset", {}) or {})
        task = dict(dataset.get("task", {}) or {})
        run = dict(dataset.get("run", {}) or {})
        filters = dict(item.get("filters", {}) or {})
        issues = 0
        for instance in dataset.get("instances", []) if isinstance(dataset.get("instances", []), list) else []:
            if isinstance(instance, dict):
                issues += len(instance.get("issues", []) if isinstance(instance.get("issues", []), list) else [])
        return RuleReplayGoldenCaseSummary(
            case_id=str(item.get("case_id", "") or ""),
            description=str(item.get("description", "") or ""),
            issue_type=str(item.get("issue_type", "") or ""),
            layer=str(item.get("layer", "") or ""),
            expectation=str(item.get("expectation", "") or ""),
            include_unchanged=bool(item.get("include_unchanged", False)),
            issue_count=issues,
            package_name=str(
                filters.get("package_name", "")
                or dict(task.get("target_app", {}) or {}).get("package_name", "")
                or ""
            ),
            template_type=str(task.get("template_type", "") or ""),
            source_run_id=str(dict(item.get("draft_metadata", {}) or {}).get("source_run_id", "") or run.get("run_id", "") or ""),
        )

    @classmethod
    def _diff_mapping(cls, prefix: str, left: Any, right: Any) -> list[str]:
        if left == right:
            return []
        if isinstance(left, dict) and isinstance(right, dict):
            diffs: list[str] = []
            keys = sorted(set(left.keys()) | set(right.keys()))
            for key in keys:
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                if key not in left or key not in right:
                    diffs.append(child_prefix)
                    continue
                diffs.extend(cls._diff_mapping(child_prefix, left[key], right[key]))
            return diffs
        if isinstance(left, list) and isinstance(right, list):
            if left == right:
                return []
            return [prefix or "value"]
        return [prefix or "value"]
