from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain.value_objects import new_id

from .rule_governance_models import (
    RuleApprovalRecord,
    RuleChangeCandidate,
    RuleDiffEntry,
    RulePermissionBinding,
    RuleRollbackResult,
    RuleValidationResult,
    RuleVersionRecord,
)


class RuleGovernanceLifecycleMixin:
    """Persisted candidate, approval, publication, rollback, and permission helpers."""

    _ROLE_PERMISSIONS: Mapping[str, tuple[str, ...]] = {
        "admin": ("propose", "approve", "publish", "rollback", "bind_permission"),
        "rule_admin": ("propose", "approve", "publish", "rollback", "bind_permission"),
        "publisher": ("propose", "approve", "publish", "rollback"),
        "reviewer": ("approve",),
        "author": ("propose",),
        "viewer": (),
    }

    def bind_rule_permission(
        self,
        *,
        actor_id: str,
        role: str,
        permissions: Sequence[str] = (),
        bound_by: str = "cli",
        path: str | Path | None = None,
    ) -> RulePermissionBinding:
        self._assert_rule_permission(bound_by, "bind_permission", path=path)
        normalized_actor = self._require_text(actor_id, "actor_id")
        normalized_role = self._require_text(role, "role")
        resolved_permissions = tuple(permissions) or self._ROLE_PERMISSIONS.get(normalized_role, ())
        if not resolved_permissions and normalized_role not in self._ROLE_PERMISSIONS:
            raise ValueError(f"Unknown rule governance role '{normalized_role}'.")

        bindings = {
            item.actor_id: item
            for item in self.list_rule_permission_bindings(path=path)
        }
        binding = RulePermissionBinding(
            actor_id=normalized_actor,
            role=normalized_role,
            permissions=tuple(str(item).strip() for item in resolved_permissions if str(item).strip()),
            bound_by=bound_by.strip() or "cli",
            bound_at=self._governance_now(),
        )
        bindings[normalized_actor] = binding
        self._write_json(self._permissions_path(self._resolve_path(path)), [asdict(item) for item in bindings.values()])
        return binding

    def list_rule_permission_bindings(self, *, path: str | Path | None = None) -> tuple[RulePermissionBinding, ...]:
        payload = self._read_json(self._permissions_path(self._resolve_path(path)), default=[])
        if not isinstance(payload, list):
            return ()
        return tuple(self._permission_binding_from_payload(item) for item in payload if isinstance(item, Mapping))

    def save_rule_change_candidate(
        self,
        patch: Mapping[str, Any],
        *,
        created_by: str = "cli",
        title: str = "",
        reason: str = "",
        required_approvals: int = 1,
        path: str | Path | None = None,
    ) -> RuleChangeCandidate:
        self._assert_rule_permission(created_by, "propose", path=path)
        plan = self.build_rule_edit_plan(patch=patch, path=path)
        if not plan.valid:
            raise ValueError("Candidate rule change is invalid: " + "; ".join(plan.errors))
        candidate = RuleChangeCandidate(
            candidate_id=new_id("rule_candidate"),
            rule_path=plan.rule_path,
            status="draft",
            created_by=created_by.strip() or "cli",
            created_at=self._governance_now(),
            title=title.strip(),
            reason=reason.strip(),
            patch=dict(plan.patch),
            preview_rules=dict(plan.preview_rules),
            validation=plan.validation,
            diff_count=plan.diff_count,
            diffs=tuple(plan.diffs),
            approvals=(),
            required_approvals=max(1, int(required_approvals)),
        )
        self._write_candidate(candidate)
        return candidate

    def list_rule_change_candidates(
        self,
        *,
        status: str = "",
        path: str | Path | None = None,
        limit: int = 20,
    ) -> tuple[RuleChangeCandidate, ...]:
        candidates_dir = self._candidates_dir(self._resolve_path(path))
        items = [self._candidate_from_payload(payload) for payload in self._read_json_files(candidates_dir)]
        if status.strip():
            items = [item for item in items if item.status == status.strip()]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return tuple(items[: max(0, int(limit)) or len(items)])

    def get_rule_change_candidate(
        self,
        candidate_id: str,
        *,
        path: str | Path | None = None,
    ) -> RuleChangeCandidate:
        candidate = self._read_candidate(self._require_text(candidate_id, "candidate_id"), self._resolve_path(path))
        if candidate is None:
            raise ValueError(f"Rule change candidate '{candidate_id}' was not found.")
        return candidate

    def approve_rule_change_candidate(
        self,
        *,
        candidate_id: str,
        actor_id: str,
        decision: str = "approve",
        comment: str = "",
        path: str | Path | None = None,
    ) -> RuleChangeCandidate:
        self._assert_rule_permission(actor_id, "approve", path=path)
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject.")
        candidate = self.get_rule_change_candidate(candidate_id, path=path)
        if candidate.status not in {"draft", "approved", "rejected"}:
            raise ValueError(f"Candidate '{candidate.candidate_id}' cannot be reviewed from status '{candidate.status}'.")
        approval = RuleApprovalRecord(
            approval_id=new_id("rule_approval"),
            candidate_id=candidate.candidate_id,
            actor_id=actor_id.strip() or "cli",
            decision=normalized_decision,
            comment=comment.strip(),
            created_at=self._governance_now(),
        )
        approvals = tuple(item for item in candidate.approvals if item.actor_id != approval.actor_id) + (approval,)
        approved_count = sum(1 for item in approvals if item.decision == "approve")
        status = "rejected" if normalized_decision == "reject" else (
            "approved" if approved_count >= candidate.required_approvals else "draft"
        )
        updated = self._replace_candidate(candidate, status=status, approvals=approvals)
        self._write_candidate(updated)
        return updated

    def publish_rule_change_candidate(
        self,
        *,
        candidate_id: str,
        published_by: str = "cli",
        path: str | Path | None = None,
    ) -> RuleVersionRecord:
        self._assert_rule_permission(published_by, "publish", path=path)
        candidate = self.get_rule_change_candidate(candidate_id, path=path)
        if candidate.status != "approved":
            raise ValueError(f"Candidate '{candidate.candidate_id}' must be approved before publication.")
        resolved_path = Path(candidate.rule_path)
        previous_rules = dict(self._read_source_rules(resolved_path))
        if not previous_rules:
            previous_rules = self._effective_rules_payload(resolved_path)
        content = dict(candidate.preview_rules)
        validation = self._validate_rules_payload(content, resolved_path, source_exists=True)
        if not validation.valid:
            raise ValueError("Candidate became invalid before publication: " + "; ".join(validation.errors))

        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        version = RuleVersionRecord(
            version_id=new_id("rule_version"),
            candidate_id=candidate.candidate_id,
            rule_path=str(resolved_path),
            published_by=published_by.strip() or "cli",
            published_at=self._governance_now(),
            checksum=self._checksum_rules(content),
            rule_versions=self._config_versions(content, resolved_path),
            previous_version_id=self._latest_version_id(resolved_path),
            rule_content=content,
            previous_rule_content=previous_rules,
            diff_count=candidate.diff_count,
        )
        self._write_version(version)
        self._write_active_version(resolved_path, version.version_id)
        self._write_candidate(self._replace_candidate(candidate, status="published"))
        return version

    def list_rule_versions(
        self,
        *,
        path: str | Path | None = None,
        limit: int = 20,
    ) -> tuple[RuleVersionRecord, ...]:
        versions = [self._version_from_payload(payload) for payload in self._read_json_files(self._versions_dir(self._resolve_path(path)))]
        versions.sort(key=lambda item: item.published_at, reverse=True)
        return tuple(versions[: max(0, int(limit)) or len(versions)])

    def rollback_rule_version(
        self,
        *,
        version_id: str,
        rolled_back_by: str = "cli",
        path: str | Path | None = None,
    ) -> RuleRollbackResult:
        self._assert_rule_permission(rolled_back_by, "rollback", path=path)
        resolved_path = self._resolve_path(path)
        version = self._read_version(self._require_text(version_id, "version_id"), resolved_path)
        if version is None:
            raise ValueError(f"Rule version '{version_id}' was not found.")
        if not version.previous_rule_content:
            raise ValueError(f"Rule version '{version_id}' does not contain rollback content.")
        content = dict(version.previous_rule_content)
        validation = self._validate_rules_payload(content, Path(version.rule_path), source_exists=True)
        if not validation.valid:
            raise ValueError("Rollback content is invalid: " + "; ".join(validation.errors))

        rule_path = Path(version.rule_path)
        rule_path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rollback_version = RuleVersionRecord(
            version_id=new_id("rule_version"),
            candidate_id="",
            rule_path=str(rule_path),
            published_by=rolled_back_by.strip() or "cli",
            published_at=self._governance_now(),
            checksum=self._checksum_rules(content),
            rule_versions=self._config_versions(content, rule_path),
            previous_version_id=self._latest_version_id(resolved_path),
            rollback_of_version_id=version.version_id,
            rule_content=content,
            previous_rule_content=dict(version.rule_content),
            diff_count=len(self._diff_mapping("", version.rule_content, content)),
        )
        self._write_version(rollback_version)
        self._write_active_version(resolved_path, rollback_version.version_id)
        return RuleRollbackResult(
            rollback_version=rollback_version,
            restored_from_version_id=version.version_id,
            restored_rule_path=str(rule_path),
            rolled_back_by=rolled_back_by.strip() or "cli",
        )

    def rule_governance_state(
        self,
        *,
        path: str | Path | None = None,
        limit: int = 10,
    ) -> Mapping[str, Any]:
        return {
            "contract_version": "asl.rule_governance.v1",
            "permissions": tuple(self.list_rule_permission_bindings(path=path)),
            "candidates": tuple(self.list_rule_change_candidates(path=path, limit=limit)),
            "versions": tuple(self.list_rule_versions(path=path, limit=limit)),
        }

    def _assert_rule_permission(self, actor_id: str, permission: str, *, path: str | Path | None = None) -> None:
        actor = actor_id.strip() or "cli"
        bindings = {item.actor_id: item for item in self.list_rule_permission_bindings(path=path)}
        binding = bindings.get(actor)
        if binding is None and actor == "cli" and not bindings:
            return
        if binding is None or permission not in set(binding.permissions):
            raise PermissionError(f"Actor '{actor}' is not allowed to {permission} analysis rules.")

    @staticmethod
    def _governance_now() -> str:
        from stability.time_utils import now_beijing_string

        return now_beijing_string()

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required.")
        return text

    def _governance_dir(self, rule_path: Path) -> Path:
        return rule_path.parent / "rule_governance"

    def _candidates_dir(self, rule_path: Path) -> Path:
        return self._governance_dir(rule_path) / "candidates"

    def _versions_dir(self, rule_path: Path) -> Path:
        return self._governance_dir(rule_path) / "versions"

    def _permissions_path(self, rule_path: Path) -> Path:
        return self._governance_dir(rule_path) / "permissions.json"

    def _active_version_path(self, rule_path: Path) -> Path:
        return self._governance_dir(rule_path) / "active_version.json"

    def _candidate_path(self, rule_path: Path, candidate_id: str) -> Path:
        return self._candidates_dir(rule_path) / f"{candidate_id}.json"

    def _version_path(self, rule_path: Path, version_id: str) -> Path:
        return self._versions_dir(rule_path) / f"{version_id}.json"

    def _write_candidate(self, item: RuleChangeCandidate) -> None:
        self._write_json(self._candidate_path(Path(item.rule_path), item.candidate_id), asdict(item))

    def _read_candidate(self, candidate_id: str, rule_path: Path) -> RuleChangeCandidate | None:
        payload = self._read_json(self._candidate_path(rule_path, candidate_id), default=None)
        return self._candidate_from_payload(payload) if isinstance(payload, Mapping) else None

    def _write_version(self, item: RuleVersionRecord) -> None:
        self._write_json(self._version_path(Path(item.rule_path), item.version_id), asdict(item))

    def _read_version(self, version_id: str, rule_path: Path) -> RuleVersionRecord | None:
        payload = self._read_json(self._version_path(rule_path, version_id), default=None)
        return self._version_from_payload(payload) if isinstance(payload, Mapping) else None

    def _write_active_version(self, rule_path: Path, version_id: str) -> None:
        self._write_json(self._active_version_path(rule_path), {"version_id": version_id, "updated_at": self._governance_now()})

    def _latest_version_id(self, rule_path: Path) -> str:
        payload = self._read_json(self._active_version_path(rule_path), default={})
        return str(payload.get("version_id", "") if isinstance(payload, Mapping) else "")

    @classmethod
    def _replace_candidate(cls, item: RuleChangeCandidate, **updates: Any) -> RuleChangeCandidate:
        payload = asdict(item)
        payload.update(updates)
        return cls._candidate_from_payload(payload)

    @classmethod
    def _candidate_from_payload(cls, payload: Mapping[str, Any]) -> RuleChangeCandidate:
        validation_payload = payload.get("validation")
        approvals_payload = payload.get("approvals", ())
        return RuleChangeCandidate(
            candidate_id=str(payload.get("candidate_id", "")),
            rule_path=str(payload.get("rule_path", "")),
            status=str(payload.get("status", "")),
            created_by=str(payload.get("created_by", "")),
            created_at=str(payload.get("created_at", "")),
            title=str(payload.get("title", "")),
            reason=str(payload.get("reason", "")),
            patch=dict(payload.get("patch", {}) or {}),
            preview_rules=dict(payload.get("preview_rules", {}) or {}),
            validation=cls._validation_from_payload(validation_payload) if isinstance(validation_payload, Mapping) else None,
            diff_count=int(payload.get("diff_count", 0) or 0),
            diffs=tuple(cls._diff_from_payload(item) for item in payload.get("diffs", ()) if isinstance(item, Mapping)),
            approvals=tuple(
                cls._approval_from_payload(item) for item in approvals_payload if isinstance(item, Mapping)
            ),
            required_approvals=max(1, int(payload.get("required_approvals", 1) or 1)),
        )

    @staticmethod
    def _permission_binding_from_payload(payload: Mapping[str, Any]) -> RulePermissionBinding:
        return RulePermissionBinding(
            actor_id=str(payload.get("actor_id", "")),
            role=str(payload.get("role", "")),
            permissions=tuple(str(item) for item in payload.get("permissions", ()) or ()),
            scope=str(payload.get("scope", "analysis_rules")),
            bound_by=str(payload.get("bound_by", "")),
            bound_at=str(payload.get("bound_at", "")),
        )

    @staticmethod
    def _approval_from_payload(payload: Mapping[str, Any]) -> RuleApprovalRecord:
        return RuleApprovalRecord(
            approval_id=str(payload.get("approval_id", "")),
            candidate_id=str(payload.get("candidate_id", "")),
            actor_id=str(payload.get("actor_id", "")),
            decision=str(payload.get("decision", "")),
            comment=str(payload.get("comment", "")),
            created_at=str(payload.get("created_at", "")),
        )

    @staticmethod
    def _validation_from_payload(payload: Mapping[str, Any]) -> RuleValidationResult:
        return RuleValidationResult(
            path=str(payload.get("path", "")),
            source_exists=bool(payload.get("source_exists", False)),
            valid=bool(payload.get("valid", False)),
            errors=tuple(str(item) for item in payload.get("errors", ()) or ()),
            warnings=tuple(str(item) for item in payload.get("warnings", ()) or ()),
        )

    @staticmethod
    def _diff_from_payload(payload: Mapping[str, Any]) -> RuleDiffEntry:
        return RuleDiffEntry(
            path=str(payload.get("path", "")),
            change_type=str(payload.get("change_type", "")),
            left_value=payload.get("left_value"),
            right_value=payload.get("right_value"),
        )

    @classmethod
    def _version_from_payload(cls, payload: Mapping[str, Any]) -> RuleVersionRecord:
        return RuleVersionRecord(
            version_id=str(payload.get("version_id", "")),
            candidate_id=str(payload.get("candidate_id", "")),
            rule_path=str(payload.get("rule_path", "")),
            published_by=str(payload.get("published_by", "")),
            published_at=str(payload.get("published_at", "")),
            checksum=str(payload.get("checksum", "")),
            rule_versions=dict(payload.get("rule_versions", {}) or {}),
            previous_version_id=str(payload.get("previous_version_id", "")),
            rollback_of_version_id=str(payload.get("rollback_of_version_id", "")),
            rule_content=dict(payload.get("rule_content", {}) or {}),
            previous_rule_content=dict(payload.get("previous_rule_content", {}) or {}),
            diff_count=int(payload.get("diff_count", 0) or 0),
        )

    @staticmethod
    def _checksum_rules(payload: Mapping[str, Any]) -> str:
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _read_json(path: Path, *, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    @classmethod
    def _read_json_files(cls, directory: Path) -> list[Mapping[str, Any]]:
        if not directory.exists():
            return []
        items: list[Mapping[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            payload = cls._read_json(path, default={})
            if isinstance(payload, Mapping):
                items.append(payload)
        return items

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
