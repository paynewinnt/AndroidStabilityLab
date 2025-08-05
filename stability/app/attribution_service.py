from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from stability.domain import (
    AggregatedIssue,
    AnalysisRuleConfig,
    AttributionHit,
    AttributionRule,
    IssueAttribution,
)

from .analysis_service import AnalysisService


@dataclass(frozen=True)
class _RuleMatch:
    rule: AttributionRule
    score: int
    hits: Sequence[AttributionHit]


class AttributionService:
    """Minimal rule-based preliminary attribution on top of aggregated issue groups."""

    _DIRECTION_LABELS = {
        "app_logic": "应用侧逻辑异常",
        "framework_system_service": "Framework / 系统服务异常",
        "driver_hardware": "驱动 / 硬件相关异常",
        "resource_pressure": "资源压力相关",
        "graphics_display": "图形渲染或显示链路相关",
        "unknown": "暂无法判断",
    }

    def __init__(
        self,
        *,
        analysis_service: AnalysisService,
        rule_config: AnalysisRuleConfig | None = None,
    ) -> None:
        self._analysis_service = analysis_service
        inherited_rule_config = getattr(analysis_service, "_rule_config", None)
        self._rule_config = rule_config or inherited_rule_config or AnalysisRuleConfig()

    @property
    def rule_version(self) -> str:
        return self._rule_config.attribution.version

    def infer_issue_group(self, fingerprint: str, **filters: Any) -> IssueAttribution:
        issue_group = self._analysis_service.get_issue_group(fingerprint, **filters)
        return self.attribute_issue_group(issue_group)

    def attribute_issue_group(self, issue_group: AggregatedIssue) -> IssueAttribution:
        matches = []
        for rule in self._rule_config.attribution.rules:
            match = self._evaluate_rule(rule, issue_group)
            if match is not None:
                matches.append(match)
        if not matches:
            return IssueAttribution(
                fingerprint=issue_group.fingerprint.value,
                issue_type=issue_group.issue_type,
                title=issue_group.title,
                direction=self._rule_config.attribution.fallback_direction,
                direction_label=self._direction_label(self._rule_config.attribution.fallback_direction),
                confidence="low",
                confidence_score=0.0,
                summary="当前样本未命中任何归因规则，暂无法给出稳定的初步归因方向。",
                rule_version=self.rule_version,
                sample_event_ids=tuple(issue_group.sample_event_ids),
                notes=("No attribution rule matched current issue samples.",),
            )

        best = max(matches, key=lambda item: (item.score, len(item.hits)))
        direction = best.rule.direction or self._rule_config.attribution.fallback_direction
        confidence = self._confidence_for_score(best.score)
        confidence_score = self._confidence_score(best.score)
        matched_rule_ids = tuple(item.rule.rule_id for item in sorted(matches, key=lambda item: item.score, reverse=True))
        matched_fields = ", ".join(sorted({hit.field for hit in best.hits}))
        evidence_summary = self._evidence_summary(best.hits)
        summary = (
            f"疑似归因为{self._direction_label(direction)}，"
            f"命中规则 {best.rule.rule_id}"
            + (f"（{best.rule.name}）" if best.rule.name else "")
            + (f"，主要依据：{matched_fields}。" if matched_fields else "。")
        )
        return IssueAttribution(
            fingerprint=issue_group.fingerprint.value,
            issue_type=issue_group.issue_type,
            title=issue_group.title,
            direction=direction,
            direction_label=self._direction_label(direction),
            confidence=confidence,
            confidence_score=confidence_score,
            summary=summary,
            rule_version=self.rule_version,
            matched_rule_id=best.rule.rule_id,
            matched_rule_name=best.rule.name,
            matched_rule_ids=matched_rule_ids,
            score=best.score,
            evidence_summary=evidence_summary,
            recommended_next_steps=tuple(best.rule.recommended_next_steps),
            review_notes=tuple(best.rule.review_notes),
            sample_event_ids=tuple(issue_group.sample_event_ids),
            hits=tuple(best.hits),
            notes=(),
        )

    def _evaluate_rule(self, rule: AttributionRule, issue_group: AggregatedIssue) -> _RuleMatch | None:
        if rule.issue_types and issue_group.issue_type not in set(rule.issue_types):
            return None
        hits: list[AttributionHit] = []
        score = 0
        if rule.issue_type_score > 0 and issue_group.issue_type in set(rule.scored_issue_types):
            score += rule.issue_type_score
            hits.append(
                AttributionHit(
                    field="issue_type",
                    keyword=issue_group.issue_type.value,
                    evidence=issue_group.issue_type.value,
                    score=rule.issue_type_score,
                )
            )

        title_text = self._normalize(issue_group.title)
        summaries = [self._normalize(event.summary) for event in issue_group.sample_events if event.summary]
        processes = [
            self._normalize(str((event.metadata or {}).get("process_name", "") or ""))
            for event in issue_group.sample_events
            if str((event.metadata or {}).get("process_name", "") or "")
        ]
        package_process_pairs = [
            (
                self._normalize(event.package_name),
                self._normalize(str((event.metadata or {}).get("process_name", "") or "")),
            )
            for event in issue_group.sample_events
        ]
        artifact_paths = [self._normalize(path) for event in issue_group.sample_events for path in event.artifact_paths if path]
        metadata_texts = [self._normalize(self._metadata_text(event.metadata)) for event in issue_group.sample_events]
        evidence_signal_texts = [
            self._normalize(self._metadata_text(signal))
            for event in issue_group.sample_events
            for signal in self._metadata_sequence((event.metadata or {}).get("evidence_signals"))
        ]
        evidence_source_texts = [
            self._normalize(source)
            for event in issue_group.sample_events
            for source in self._metadata_sequence((event.metadata or {}).get("matched_sources"))
        ]
        matched_fragment_texts = [
            self._normalize(fragment)
            for event in issue_group.sample_events
            for fragment in self._metadata_sequence((event.metadata or {}).get("matched_fragments"))
        ]
        confirmation_levels = [
            self._normalize(str((event.metadata or {}).get("confirmation_level", "") or ""))
            for event in issue_group.sample_events
            if str((event.metadata or {}).get("confirmation_level", "") or "")
        ]

        if rule.package_process_match:
            for package_name, process_name in package_process_pairs:
                if package_name and process_name and process_name.startswith(package_name):
                    score += 4
                    hits.append(
                        AttributionHit(
                            field="process_name",
                            keyword="package_process_match",
                            evidence=process_name,
                            score=4,
                        )
                    )
                    break

        score += self._match_keywords(
            rule.title_keywords,
            title_text,
            field="issue_title",
            per_hit_score=2,
            hits=hits,
        )
        score += self._match_keywords(
            rule.summary_keywords,
            summaries,
            field="summary",
            per_hit_score=2,
            hits=hits,
        )
        score += self._match_keywords(
            rule.process_keywords,
            processes,
            field="process_name",
            per_hit_score=3,
            hits=hits,
        )
        score += self._match_keywords(
            rule.artifact_keywords,
            artifact_paths,
            field="artifact_path",
            per_hit_score=1,
            hits=hits,
        )
        score += self._match_keywords(
            rule.metadata_keywords,
            metadata_texts,
            field="metadata",
            per_hit_score=1,
            hits=hits,
        )
        score += self._match_keywords(
            rule.evidence_signal_keywords,
            evidence_signal_texts,
            field="evidence_signal",
            per_hit_score=2,
            hits=hits,
        )
        score += self._match_keywords(
            rule.evidence_source_keywords,
            evidence_source_texts,
            field="matched_source",
            per_hit_score=2,
            hits=hits,
        )
        score += self._match_keywords(
            rule.matched_fragment_keywords,
            matched_fragment_texts,
            field="matched_fragment",
            per_hit_score=2,
            hits=hits,
        )
        score += self._match_confirmation_levels(rule.confirmation_level_scores, confirmation_levels, hits)

        if score <= 0:
            return None
        return _RuleMatch(rule=rule, score=score, hits=tuple(hits))

    def _match_keywords(
        self,
        keywords: Sequence[str],
        haystacks: str | Iterable[str],
        *,
        field: str,
        per_hit_score: int,
        hits: list[AttributionHit],
    ) -> int:
        if isinstance(haystacks, str):
            values = [haystacks]
        else:
            values = [item for item in haystacks if item]
        total = 0
        for raw_keyword in keywords:
            keyword = self._normalize(raw_keyword)
            if not keyword:
                continue
            for value in values:
                if keyword in value:
                    total += per_hit_score
                    hits.append(
                        AttributionHit(
                            field=field,
                            keyword=raw_keyword,
                            evidence=value[:200],
                            score=per_hit_score,
                        )
                    )
                    break
        return total

    def _match_confirmation_levels(
        self,
        level_scores: Mapping[str, int],
        levels: Sequence[str],
        hits: list[AttributionHit],
    ) -> int:
        if not level_scores or not levels:
            return 0
        normalized_scores = {self._normalize(level): score for level, score in level_scores.items()}
        best_level = ""
        best_score = 0
        for level in levels:
            score = int(normalized_scores.get(level, 0) or 0)
            if score > best_score:
                best_level = level
                best_score = score
        if best_score <= 0:
            return 0
        hits.append(
            AttributionHit(
                field="confirmation_level",
                keyword=best_level,
                evidence=best_level,
                score=best_score,
            )
        )
        return best_score

    def _confidence_for_score(self, score: int) -> str:
        config = self._rule_config.attribution
        if score >= config.high_confidence_score:
            return "high"
        if score >= config.medium_confidence_score:
            return "medium"
        return "low"

    def _confidence_score(self, score: int) -> float:
        high_score = max(int(self._rule_config.attribution.high_confidence_score), 1)
        return round(min(max(score / high_score, 0.0), 1.0), 2)

    @staticmethod
    def _evidence_summary(hits: Sequence[AttributionHit]) -> Sequence[str]:
        summaries: list[str] = []
        seen: set[str] = set()
        for hit in sorted(hits, key=lambda item: item.score, reverse=True):
            if hit.field not in {"issue_type", "evidence_signal", "matched_source", "matched_fragment", "confirmation_level"}:
                continue
            evidence = " ".join(str(hit.evidence or "").split())
            if not evidence:
                continue
            text = f"{hit.field}: {evidence[:160]}"
            if text in seen:
                continue
            seen.add(text)
            summaries.append(text)
            if len(summaries) >= 5:
                break
        return tuple(summaries)

    @classmethod
    def _direction_label(cls, direction: str) -> str:
        return cls._DIRECTION_LABELS.get(direction, cls._DIRECTION_LABELS["unknown"])

    @staticmethod
    def _normalize(value: str | None) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @classmethod
    def _metadata_text(cls, metadata: Any) -> str:
        if not metadata:
            return ""
        try:
            return json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(metadata)

    @staticmethod
    def _metadata_sequence(value: Any) -> Sequence[Any]:
        if value is None:
            return ()
        if isinstance(value, (list, tuple)):
            return tuple(item for item in value if item)
        return (value,)
