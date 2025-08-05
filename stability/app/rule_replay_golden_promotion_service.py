from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Sequence

from stability.domain import RuleReplayGoldenPromotionResult
from stability.time_utils import now_beijing_string

from .rule_replay_acceptance_service import RuleReplayAcceptanceService


class RuleReplayGoldenPromotionService:
    """Validate and promote draft golden-sample cases into one target suite."""

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

    def __init__(self, *, acceptance_service: RuleReplayAcceptanceService) -> None:
        self._acceptance_service = acceptance_service

    def promote(
        self,
        *,
        source_path: str,
        target_path: str = "config/rule_replay_golden_samples.json",
        case_ids: Sequence[str] | None = None,
        replace_existing: bool = False,
    ) -> RuleReplayGoldenPromotionResult:
        source = Path(source_path).expanduser()
        target = Path(target_path).expanduser()
        source_payload = self._load_suite(source, allow_missing=False)
        target_payload = self._load_suite(target, allow_missing=True)

        selected_ids = tuple(item.strip() for item in (case_ids or ()) if str(item).strip())
        source_cases = self._normalize_cases(source_payload, path=source)
        if selected_ids:
            source_cases = [item for item in source_cases if str(item.get("case_id", "")) in set(selected_ids)]
            if not source_cases:
                raise ValueError("No source golden cases matched the requested --case-id values.")

        source_case_ids = [str(item.get("case_id", "") or "") for item in source_cases]
        duplicates = self._duplicate_ids(source_case_ids)
        if duplicates:
            raise ValueError(f"Source suite contains duplicate case ids: {', '.join(sorted(duplicates))}")

        target_cases = self._normalize_cases(target_payload, path=target, allow_empty=True)
        target_by_id = {str(item.get("case_id", "") or ""): item for item in target_cases}
        replaced_case_ids: list[str] = []
        conflict_case_ids = [
            case_id for case_id in source_case_ids if case_id in target_by_id and not replace_existing
        ]
        if conflict_case_ids:
            raise ValueError(
                "Target suite already contains case ids: "
                f"{', '.join(sorted(conflict_case_ids))}. Use --replace-existing to overwrite them."
            )

        merged_cases = [item for item in target_cases if str(item.get("case_id", "") or "") not in set(source_case_ids)]
        for item in source_cases:
            case_id = str(item.get("case_id", "") or "")
            if case_id in target_by_id:
                replaced_case_ids.append(case_id)
            merged_cases.append(item)

        target_payload["suite_version"] = str(target_payload.get("suite_version") or source_payload.get("suite_version") or "v2")
        target_payload["cases"] = merged_cases
        target_payload["promoted_at"] = now_beijing_string()
        target_payload["promotion_source_path"] = str(source)

        acceptance = self._verify_promoted_cases(target_payload=target_payload, case_ids=source_case_ids)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(target_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return RuleReplayGoldenPromotionResult(
            source_path=str(source),
            target_path=str(target),
            selected_case_ids=selected_ids or tuple(source_case_ids),
            promoted_case_ids=tuple(source_case_ids),
            replaced_case_ids=tuple(replaced_case_ids),
            skipped_case_ids=tuple(),
            target_suite_version=str(target_payload.get("suite_version", "") or ""),
            source_suite_version=str(source_payload.get("suite_version", "") or ""),
            promoted_case_count=len(source_case_ids),
            replace_existing=replace_existing,
            acceptance=acceptance,
        )

    def _verify_promoted_cases(self, *, target_payload: dict[str, Any], case_ids: Sequence[str]):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "promoted_suite.json"
            temp_path.write_text(json.dumps(target_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            result = self._acceptance_service.verify_golden_suite(
                suite_path=str(temp_path),
                case_ids=tuple(case_ids),
                fail_fast=False,
            )
        if result.failed_case_count > 0:
            failed = ", ".join(item.case_id for item in result.cases if not item.passed)
            raise ValueError(f"Promotion acceptance failed for cases: {failed}")
        return result

    def _load_suite(self, path: Path, *, allow_missing: bool) -> dict[str, Any]:
        if not path.exists():
            if allow_missing:
                return {"suite_version": "v2", "cases": []}
            raise FileNotFoundError(f"Golden suite file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Golden suite file must be a JSON object: {path}")
        payload.setdefault("cases", [])
        if not isinstance(payload["cases"], list):
            raise ValueError(f"Golden suite 'cases' must be a JSON array: {path}")
        return payload

    def _normalize_cases(
        self,
        payload: dict[str, Any],
        *,
        path: Path,
        allow_empty: bool = False,
    ) -> list[dict[str, Any]]:
        cases = payload.get("cases", [])
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(cases):
            if not isinstance(item, dict):
                raise ValueError(f"Golden suite case at index {index} must be a JSON object: {path}")
            missing = sorted(self._REQUIRED_CASE_KEYS - set(item.keys()))
            if missing:
                raise ValueError(
                    f"Golden suite case '{item.get('case_id', f'index-{index}')}' is missing keys: {', '.join(missing)}"
                )
            normalized.append(dict(item))
        if not normalized and not allow_empty:
            raise ValueError(f"Golden suite contains no cases: {path}")
        return normalized

    @staticmethod
    def _duplicate_ids(case_ids: Sequence[str]) -> set[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for item in case_ids:
            if item in seen:
                duplicates.add(item)
            seen.add(item)
        return duplicates
