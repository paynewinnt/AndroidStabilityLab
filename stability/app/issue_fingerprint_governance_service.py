from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import IssueFingerprint
from stability.time_utils import now_beijing_string


@dataclass(frozen=True)
class IssueFingerprintGovernanceRule:
    """Manual governance rule for one generated issue fingerprint."""

    source_fingerprint: str
    action: str
    canonical_fingerprint: str = ""
    reason: str = ""
    created_at: str = ""
    created_by: str = ""
    updated_at: str = ""
    updated_by: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_fingerprint": self.source_fingerprint,
            "action": self.action,
            "canonical_fingerprint": self.canonical_fingerprint,
            "reason": self.reason,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "IssueFingerprintGovernanceRule":
        return cls(
            source_fingerprint=str(payload.get("source_fingerprint", "") or "").strip(),
            action=str(payload.get("action", "") or "").strip().lower(),
            canonical_fingerprint=str(payload.get("canonical_fingerprint", "") or "").strip(),
            reason=str(payload.get("reason", "") or ""),
            created_at=str(payload.get("created_at", "") or ""),
            created_by=str(payload.get("created_by", "") or ""),
            updated_at=str(payload.get("updated_at", "") or ""),
            updated_by=str(payload.get("updated_by", "") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )


class IssueFingerprintGovernanceService:
    """Persist manual alias/suppress rules applied before issue aggregation."""

    CONTRACT_VERSION = "asl.issue_fingerprint_governance.v1"
    REGISTRY_FILE = "fingerprints.json"
    _VALID_ACTIONS = {"alias", "suppress"}

    def __init__(self, *, root_dir: str | Path = "runtime/issue_fingerprint_governance") -> None:
        self._root_dir = Path(root_dir)
        self._registry_path = self._root_dir / self.REGISTRY_FILE

    @property
    def registry_path(self) -> Path:
        return self._registry_path

    def list_rules(self, *, action: str = "") -> tuple[IssueFingerprintGovernanceRule, ...]:
        rules = tuple(self._load_rules().values())
        normalized_action = action.strip().lower()
        if normalized_action:
            return tuple(item for item in rules if item.action == normalized_action)
        return rules

    def get_rule(self, source_fingerprint: str) -> IssueFingerprintGovernanceRule | None:
        return self._load_rules().get(self._normalize_fingerprint(source_fingerprint))

    def upsert_alias(
        self,
        *,
        source_fingerprint: str,
        canonical_fingerprint: str,
        reason: str = "",
        created_by: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> IssueFingerprintGovernanceRule:
        source = self._normalize_fingerprint(source_fingerprint)
        canonical = self._normalize_fingerprint(canonical_fingerprint)
        if source == canonical:
            raise ValueError("Source and canonical fingerprints must be different.")
        return self._upsert_rule(
            source_fingerprint=source,
            action="alias",
            canonical_fingerprint=canonical,
            reason=reason,
            created_by=created_by,
            metadata=dict(metadata or {}),
        )

    def suppress_fingerprint(
        self,
        *,
        fingerprint: str,
        reason: str = "",
        created_by: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> IssueFingerprintGovernanceRule:
        return self._upsert_rule(
            source_fingerprint=self._normalize_fingerprint(fingerprint),
            action="suppress",
            canonical_fingerprint="",
            reason=reason,
            created_by=created_by,
            metadata=dict(metadata or {}),
        )

    def remove_rule(self, source_fingerprint: str) -> bool:
        source = self._normalize_fingerprint(source_fingerprint)
        rules = self._load_rules()
        if source not in rules:
            return False
        del rules[source]
        self._save_rules(tuple(rules.values()))
        return True

    def resolve_fingerprint(self, fingerprint: IssueFingerprint) -> IssueFingerprint | None:
        """Return the governed fingerprint, or None when the source is suppressed."""
        rules = self._load_rules()
        current = self._normalize_fingerprint(fingerprint.value)
        visited: set[str] = set()
        applied: list[IssueFingerprintGovernanceRule] = []
        for _ in range(16):
            if current in visited:
                break
            visited.add(current)
            rule = rules.get(current)
            if rule is None:
                break
            applied.append(rule)
            if rule.action == "suppress":
                return None
            if rule.action != "alias" or not rule.canonical_fingerprint:
                break
            current = rule.canonical_fingerprint
        if not applied:
            return fingerprint
        components = dict(fingerprint.components)
        components["governance"] = {
            "original_fingerprint": fingerprint.value,
            "canonical_fingerprint": current,
            "applied_rule_count": len(applied),
            "applied_rules": [item.to_payload() for item in applied],
        }
        return IssueFingerprint(
            value=current,
            rule_version=f"{fingerprint.rule_version}+governance",
            components=components,
        )

    def _upsert_rule(
        self,
        *,
        source_fingerprint: str,
        action: str,
        canonical_fingerprint: str,
        reason: str,
        created_by: str,
        metadata: Mapping[str, Any],
    ) -> IssueFingerprintGovernanceRule:
        normalized_action = action.strip().lower()
        if normalized_action not in self._VALID_ACTIONS:
            raise ValueError(f"Unsupported fingerprint governance action: {action}")
        rules = self._load_rules()
        existing = rules.get(source_fingerprint)
        now = now_beijing_string()
        rule = IssueFingerprintGovernanceRule(
            source_fingerprint=source_fingerprint,
            action=normalized_action,
            canonical_fingerprint=canonical_fingerprint,
            reason=reason,
            created_at=existing.created_at if existing else now,
            created_by=existing.created_by if existing else created_by,
            updated_at=now,
            updated_by=created_by,
            metadata=dict(metadata),
        )
        rules[source_fingerprint] = rule
        self._save_rules(tuple(rules.values()))
        return rule

    def _load_rules(self) -> dict[str, IssueFingerprintGovernanceRule]:
        path = self._registry_path
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        raw_rules = payload.get("rules", []) if isinstance(payload, Mapping) else []
        rules: dict[str, IssueFingerprintGovernanceRule] = {}
        for item in raw_rules:
            if not isinstance(item, Mapping):
                continue
            rule = IssueFingerprintGovernanceRule.from_payload(item)
            if rule.source_fingerprint and rule.action in self._VALID_ACTIONS:
                rules[rule.source_fingerprint] = rule
        return rules

    def _save_rules(self, rules: Sequence[IssueFingerprintGovernanceRule]) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "contract_version": self.CONTRACT_VERSION,
            "updated_at": now_beijing_string(),
            "rules": [item.to_payload() for item in sorted(rules, key=lambda rule: rule.source_fingerprint)],
        }
        self._registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize_fingerprint(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Issue fingerprint is required.")
        return normalized
