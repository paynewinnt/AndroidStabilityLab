from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import (
    AnalysisRuleConfig,
    AttributionRule,
    AttributionRuleConfig,
    FingerprintRuleConfig,
    IssueType,
    RegressionRuleSet,
)


def default_analysis_rule_config() -> AnalysisRuleConfig:
    return AnalysisRuleConfig(
        fingerprint=FingerprintRuleConfig(
            version="v1",
            ignore_raw_key_issue_types=(
                IssueType.DEVICE_OFFLINE,
                IssueType.STARTUP_TIMEOUT,
                IssueType.STARTUP_FAILURE,
                IssueType.REBOOT,
                IssueType.EXECUTION_TIMEOUT,
            ),
        ),
        regression=RegressionRuleSet(
            version="v1",
            min_side_issue_groups=1,
            significant_occurrence_delta=1,
            significant_affected_run_delta=1,
            significant_affected_device_delta=1,
            significant_affected_scenario_delta=1,
            min_side_metric_sessions=1,
            min_side_metric_samples=1,
            significant_metric_delta_ratio=0.1,
        ),
        attribution=AttributionRuleConfig(
            version="v1",
            fallback_direction="unknown",
            medium_confidence_score=3,
            high_confidence_score=5,
            rules=(
                AttributionRule(
                    rule_id="app_target_process_crash",
                    name="Target app process failure",
                    direction="app_logic",
                    issue_types=(
                        IssueType.CRASH,
                        IssueType.ANR,
                        IssueType.JAVA_EXCEPTION,
                        IssueType.JAVA_CRASH,
                        IssueType.STARTUP_FAILURE,
                        IssueType.PROCESS_EXIT,
                    ),
                    summary_keywords=("fatal exception", "process crashed", "not responding", "startup failed"),
                    package_process_match=True,
                ),
                AttributionRule(
                    rule_id="framework_system_service",
                    name="Framework or system service signal",
                    direction="framework_system_service",
                    issue_types=(
                        IssueType.CRASH,
                        IssueType.ANR,
                        IssueType.JAVA_EXCEPTION,
                        IssueType.JAVA_CRASH,
                        IssueType.SYSTEM_SERVER_CRASH,
                        IssueType.WATCHDOG,
                        IssueType.REBOOT,
                        IssueType.PROCESS_EXIT,
                    ),
                    scored_issue_types=(IssueType.SYSTEM_SERVER_CRASH, IssueType.WATCHDOG),
                    issue_type_score=3,
                    process_keywords=("system_server", "zygote", "systemui"),
                    summary_keywords=("watchdog", "system_server", "system ui", "framework"),
                    metadata_keywords=("system_server", "watchdog", "framework"),
                    evidence_signal_keywords=("system_server", "watchdog", "system process"),
                    evidence_source_keywords=("dropbox", "system_server", "text"),
                    matched_fragment_keywords=("system_server", "watchdog"),
                    confirmation_level_scores={"weak": 1, "medium": 2, "strong": 3, "confirmed": 3, "high": 3},
                    recommended_next_steps=(
                        "优先查看 dropbox/system_server/tombstone 与 reboot 前后的 logcat。",
                        "确认 Watchdog 阻塞线程、system_server 崩溃栈和 Framework 服务调用链。",
                    ),
                    review_notes=(
                        "该结论仅表示 Framework/SystemService 方向的初步归因，不等同于最终根因。",
                    ),
                ),
                AttributionRule(
                    rule_id="driver_hardware_native",
                    name="Driver or hardware signal",
                    direction="driver_hardware",
                    issue_types=(
                        IssueType.NATIVE_CRASH,
                        IssueType.REBOOT,
                        IssueType.PROCESS_EXIT,
                        IssueType.CRASH,
                    ),
                    process_keywords=("vendor.", "android.hardware", "composer", "gralloc"),
                    summary_keywords=("kernel panic", "segmentation fault", "signal 11", "vendor"),
                ),
                AttributionRule(
                    rule_id="resource_pressure",
                    name="Resource pressure signal",
                    direction="resource_pressure",
                    issue_types=(
                        IssueType.ANR,
                        IssueType.STARTUP_TIMEOUT,
                        IssueType.EXECUTION_TIMEOUT,
                        IssueType.PROCESS_EXIT,
                        IssueType.CRASH,
                    ),
                    summary_keywords=("oom", "outofmemory", "low memory", "memory pressure", "timeout"),
                    artifact_keywords=("meminfo", "bugreport"),
                ),
                AttributionRule(
                    rule_id="graphics_display",
                    name="Graphics or display pipeline signal",
                    direction="graphics_display",
                    issue_types=(
                        IssueType.ANR,
                        IssueType.NATIVE_CRASH,
                        IssueType.EXECUTION_TIMEOUT,
                        IssueType.CRASH,
                        IssueType.FREEZE,
                        IssueType.BLACK_SCREEN,
                    ),
                    scored_issue_types=(IssueType.FREEZE, IssueType.BLACK_SCREEN),
                    issue_type_score=3,
                    process_keywords=("surfaceflinger", "renderthread", "hwui"),
                    summary_keywords=("jank", "black screen", "freeze", "render", "surface"),
                    artifact_keywords=("surfaceflinger", "perfetto"),
                    metadata_keywords=("black screen", "freeze", "surfaceflinger", "frame_refresh", "screenshot"),
                    evidence_signal_keywords=("black screen", "freeze", "frozen", "frame", "render", "surface", "display"),
                    evidence_source_keywords=("screenshot", "surfaceflinger", "frame_refresh", "input"),
                    matched_fragment_keywords=("black screen", "freeze", "surface", "display", "frame"),
                    confirmation_level_scores={"weak": 1, "medium": 2, "strong": 3, "confirmed": 3, "high": 3},
                    recommended_next_steps=(
                        "优先检查截图/录屏、SurfaceFlinger、Perfetto 与输入事件时间线。",
                        "确认是否存在无帧刷新、黑屏持续、渲染线程阻塞或显示合成异常。",
                    ),
                    review_notes=(
                        "Freeze/Black Screen 归因依赖多源 evidence 更可靠，单一日志命中应人工复核。",
                    ),
                ),
            ),
        ),
    )


class FileBackedRuleConfigProvider:
    """Load versioned analysis rules from one local JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> AnalysisRuleConfig:
        defaults = default_analysis_rule_config()
        if not self._path.exists():
            return defaults
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return defaults
        fingerprint_payload = self._mapping(payload.get("fingerprint"))
        regression_payload = self._mapping(payload.get("regression"))
        attribution_payload = self._mapping(payload.get("attribution"))
        return AnalysisRuleConfig(
            fingerprint=FingerprintRuleConfig(
                version=str(fingerprint_payload.get("version", defaults.fingerprint.version) or defaults.fingerprint.version),
                ignore_raw_key_issue_types=self._issue_types(
                    fingerprint_payload.get(
                        "ignore_raw_key_issue_types",
                        [item.value for item in defaults.fingerprint.ignore_raw_key_issue_types],
                    )
                ),
            ),
            regression=RegressionRuleSet(
                version=str(regression_payload.get("version", defaults.regression.version) or defaults.regression.version),
                min_side_issue_groups=self._int_value(
                    regression_payload.get("min_side_issue_groups"),
                    defaults.regression.min_side_issue_groups,
                ),
                significant_occurrence_delta=self._int_value(
                    regression_payload.get("significant_occurrence_delta"),
                    defaults.regression.significant_occurrence_delta,
                ),
                significant_affected_run_delta=self._int_value(
                    regression_payload.get("significant_affected_run_delta"),
                    defaults.regression.significant_affected_run_delta,
                ),
                significant_affected_device_delta=self._int_value(
                    regression_payload.get("significant_affected_device_delta"),
                    defaults.regression.significant_affected_device_delta,
                ),
                significant_affected_scenario_delta=self._int_value(
                    regression_payload.get("significant_affected_scenario_delta"),
                    defaults.regression.significant_affected_scenario_delta,
                ),
                min_side_metric_sessions=self._int_value(
                    regression_payload.get("min_side_metric_sessions"),
                    defaults.regression.min_side_metric_sessions,
                ),
                min_side_metric_samples=self._int_value(
                    regression_payload.get("min_side_metric_samples"),
                    defaults.regression.min_side_metric_samples,
                ),
                significant_metric_delta_ratio=self._float_value(
                    regression_payload.get("significant_metric_delta_ratio"),
                    defaults.regression.significant_metric_delta_ratio,
                ),
            ),
            attribution=AttributionRuleConfig(
                version=str(attribution_payload.get("version", defaults.attribution.version) or defaults.attribution.version),
                fallback_direction=str(
                    attribution_payload.get("fallback_direction", defaults.attribution.fallback_direction)
                    or defaults.attribution.fallback_direction
                ),
                medium_confidence_score=self._int_value(
                    attribution_payload.get("medium_confidence_score"),
                    defaults.attribution.medium_confidence_score,
                ),
                high_confidence_score=self._int_value(
                    attribution_payload.get("high_confidence_score"),
                    defaults.attribution.high_confidence_score,
                ),
                rules=self._attribution_rules(
                    attribution_payload.get("rules"),
                    defaults.attribution.rules,
                ),
            ),
        )

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _int_value(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float_value(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _issue_types(raw_values: Any) -> Sequence[IssueType]:
        values = raw_values if isinstance(raw_values, list) else []
        resolved: list[IssueType] = []
        for raw in values:
            try:
                resolved.append(IssueType(str(raw)))
            except ValueError:
                continue
        return tuple(resolved)

    @classmethod
    def _attribution_rules(
        cls,
        raw_values: Any,
        defaults: Sequence[AttributionRule],
    ) -> Sequence[AttributionRule]:
        values = raw_values if isinstance(raw_values, list) else []
        rules: list[AttributionRule] = []
        for item in values:
            payload = cls._mapping(item)
            rule_id = str(payload.get("rule_id", "") or "").strip()
            if not rule_id:
                continue
            rules.append(
                AttributionRule(
                    rule_id=rule_id,
                    name=str(payload.get("name", "") or "").strip(),
                    direction=str(payload.get("direction", "unknown") or "unknown").strip(),
                    issue_types=cls._issue_types(payload.get("issue_types")),
                    scored_issue_types=cls._issue_types(payload.get("scored_issue_types")),
                    issue_type_score=cls._int_value(payload.get("issue_type_score"), 0),
                    title_keywords=cls._string_sequence(payload.get("title_keywords")),
                    summary_keywords=cls._string_sequence(payload.get("summary_keywords")),
                    process_keywords=cls._string_sequence(payload.get("process_keywords")),
                    artifact_keywords=cls._string_sequence(payload.get("artifact_keywords")),
                    metadata_keywords=cls._string_sequence(payload.get("metadata_keywords")),
                    evidence_signal_keywords=cls._string_sequence(payload.get("evidence_signal_keywords")),
                    evidence_source_keywords=cls._string_sequence(payload.get("evidence_source_keywords")),
                    matched_fragment_keywords=cls._string_sequence(payload.get("matched_fragment_keywords")),
                    confirmation_level_scores=cls._score_mapping(payload.get("confirmation_level_scores")),
                    recommended_next_steps=cls._string_sequence(payload.get("recommended_next_steps")),
                    review_notes=cls._string_sequence(payload.get("review_notes")),
                    package_process_match=bool(payload.get("package_process_match", False)),
                )
            )
        return tuple(rules) or tuple(defaults)

    @staticmethod
    def _string_sequence(raw_values: Any) -> Sequence[str]:
        values = raw_values if isinstance(raw_values, list) else []
        return tuple(str(item).strip() for item in values if str(item).strip())

    @classmethod
    def _score_mapping(cls, raw_value: Any) -> Mapping[str, int]:
        values = raw_value if isinstance(raw_value, dict) else {}
        return {
            str(key).strip(): cls._int_value(value, 0)
            for key, value in values.items()
            if str(key).strip() and cls._int_value(value, 0) > 0
        }
