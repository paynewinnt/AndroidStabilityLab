"""按证据类型声明保留策略：保留天数 + 单类型大小上限。

证据落在 ``runtime/tasks/<task>/runs/<run>/executions/<instance>/devices/<device>/`` 下，
按子目录划分为 report / logs / monitoring / artifacts / temp，重型 trace 文件按扩展名单独归类。
本模块只描述策略与归类规则，真正的扫描与删除由 ``RuntimeLifecycleService`` 执行。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024

# run 产物子目录名 -> 证据类型
_DIR_EVIDENCE_TYPES: Mapping[str, str] = {
    "report": "report",
    "logs": "logs",
    "monitoring": "monitoring",
    "artifacts": "artifacts",
    "temp": "temp",
}

# 重型 trace 文件按扩展名优先归类，不论它落在哪个子目录
_TRACE_SUFFIXES: tuple[str, ...] = (".perfetto-trace", ".perfetto", ".trace")

UNKNOWN_EVIDENCE_TYPE = "unknown"

EVIDENCE_TYPES: tuple[str, ...] = (
    "report",
    "logs",
    "monitoring",
    "artifacts",
    "trace",
    "temp",
)


@dataclass(frozen=True)
class EvidenceRetentionRule:
    """单一证据类型的保留规则。

    - ``max_age_days``：超过该天数的文件成为清理候选；``None`` 表示不按时间清理。
    - ``max_total_bytes``：该类型总占用上限，超过后按最旧优先逐个淘汰；``None`` 表示不设上限。
    - ``protected``：``True`` 表示永不自动删除（例如人类可读报告）。
    """

    evidence_type: str
    max_age_days: int | None = None
    max_total_bytes: int | None = None
    protected: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "max_age_days": self.max_age_days,
            "max_total_bytes": self.max_total_bytes,
            "protected": self.protected,
        }


def _default_rules() -> dict[str, EvidenceRetentionRule]:
    return {
        # 报告轻量且最有价值：长期保留，永不自动删除
        "report": EvidenceRetentionRule("report", max_age_days=90, protected=True),
        "logs": EvidenceRetentionRule("logs", max_age_days=14, max_total_bytes=1 * _GB),
        "monitoring": EvidenceRetentionRule("monitoring", max_age_days=30, max_total_bytes=1 * _GB),
        "artifacts": EvidenceRetentionRule("artifacts", max_age_days=30, max_total_bytes=2 * _GB),
        # trace 通常最重：保留时间最短、上限单列
        "trace": EvidenceRetentionRule("trace", max_age_days=7, max_total_bytes=2 * _GB),
        "temp": EvidenceRetentionRule("temp", max_age_days=2, max_total_bytes=512 * _MB),
    }


# 未归类文件默认受保护：扫描会递归整个 runtime/tasks，run.json 等非证据文件不应被自动清理。
# 如确需清理 unknown，可在配置中显式设置 {"default": {"protected": false, "max_age_days": N}}。
_DEFAULT_FALLBACK = EvidenceRetentionRule(UNKNOWN_EVIDENCE_TYPE, protected=True)


@dataclass(frozen=True)
class EvidenceRetentionPolicy:
    """一组按证据类型的保留规则，外加未知类型的兜底规则。"""

    rules: Mapping[str, EvidenceRetentionRule]
    default_rule: EvidenceRetentionRule = _DEFAULT_FALLBACK

    @classmethod
    def default(cls) -> "EvidenceRetentionPolicy":
        return cls(rules=_default_rules(), default_rule=_DEFAULT_FALLBACK)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "EvidenceRetentionPolicy":
        """在默认策略上叠加配置覆盖。

        配置形如::

            {
              "report": {"max_age_days": 120},
              "trace": {"max_age_days": 3, "max_total_mb": 1024},
              "default": {"max_age_days": 45}
            }

        支持 ``max_total_bytes`` 或更友好的 ``max_total_mb``（后者优先）。
        """
        rules = _default_rules()
        default_rule = _DEFAULT_FALLBACK
        if payload:
            for key, raw in payload.items():
                if not isinstance(raw, Mapping):
                    continue
                if key == "default":
                    default_rule = cls._merge_rule(default_rule, raw)
                    continue
                base = rules.get(key, EvidenceRetentionRule(str(key)))
                rules[key] = cls._merge_rule(base, raw)
        return cls(rules=rules, default_rule=default_rule)

    @staticmethod
    def _merge_rule(base: EvidenceRetentionRule, raw: Mapping[str, Any]) -> EvidenceRetentionRule:
        max_age_days = base.max_age_days
        if "max_age_days" in raw:
            max_age_days = EvidenceRetentionPolicy._coerce_optional_int(raw.get("max_age_days"))
        max_total_bytes = base.max_total_bytes
        if "max_total_mb" in raw:
            mb = EvidenceRetentionPolicy._coerce_optional_int(raw.get("max_total_mb"))
            max_total_bytes = None if mb is None else mb * _MB
        elif "max_total_bytes" in raw:
            max_total_bytes = EvidenceRetentionPolicy._coerce_optional_int(raw.get("max_total_bytes"))
        protected = base.protected
        if "protected" in raw:
            protected = bool(raw.get("protected"))
        return EvidenceRetentionRule(
            evidence_type=base.evidence_type,
            max_age_days=max_age_days,
            max_total_bytes=max_total_bytes,
            protected=protected,
        )

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def rule_for(self, evidence_type: str) -> EvidenceRetentionRule:
        return self.rules.get(evidence_type, self.default_rule)

    @staticmethod
    def classify(path: Path) -> str:
        """把一个证据文件路径归类到证据类型。"""
        name = path.name.lower()
        for suffix in _TRACE_SUFFIXES:
            if name.endswith(suffix):
                return "trace"
        for part in reversed(path.parts):
            mapped = _DIR_EVIDENCE_TYPES.get(part)
            if mapped:
                return mapped
        return UNKNOWN_EVIDENCE_TYPE

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {key: rule.to_payload() for key, rule in self.rules.items()}
        payload["default"] = self.default_rule.to_payload()
        return payload
