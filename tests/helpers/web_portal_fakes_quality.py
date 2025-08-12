from __future__ import annotations

from types import SimpleNamespace


class _FakeQualityGateService:
    def __init__(self, quality_gate, *, outbox_service) -> None:
        self._quality_gate = quality_gate
        self._outbox = outbox_service

    def list_quality_gates(self, limit: int = 20):
        return [self._quality_gate][:limit]

    def get_quality_gate(self, baseline_key: str):
        return self._quality_gate

    def record_override(
        self,
        *,
        baseline_key: str,
        final_decision: str,
        reason: str,
        created_by: str,
        session_source: str = "",
        audit_source=None,
        comment: str = "",
        evidence_paths=(),
    ):
        override = SimpleNamespace(
            override_id="gate_override_1",
            baseline_key=baseline_key,
            automatic_decision=self._quality_gate.automatic_decision,
            final_decision=final_decision,
            reason=reason,
            created_at=None,
            created_by=created_by,
            session_source=session_source,
            audit_source=dict(audit_source or {}),
            comment=comment,
            evidence_paths=tuple(evidence_paths),
        )
        self._quality_gate = SimpleNamespace(
            **{
                **self._quality_gate.__dict__,
                "final_decision": final_decision,
                "final_review_opinion": f"人工覆盖已将自动结论 {self._quality_gate.automatic_decision} 调整为 {final_decision}",
                "override": override,
            }
        )
        self._outbox.publish_event(
            event_type="admission.override_recorded",
            target_type="admission",
            target_id=baseline_key,
            created_by=created_by,
            session_source=session_source,
            audit_source=dict(audit_source or {}),
            payload={"final_decision": final_decision, "reason": reason},
        )
        return override
