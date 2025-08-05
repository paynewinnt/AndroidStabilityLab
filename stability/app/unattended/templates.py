from __future__ import annotations

from typing import Any, Sequence

from stability.domain import TaskTemplateType

from .models import LongRunPlan, LongRunTemplate, LongRunTemplateNotFound


LONG_RUN_TEMPLATES: tuple[LongRunTemplate, ...] = (
    LongRunTemplate(
        template_id="smoke_long_run",
        name="Smoke Long Run",
        description="Short unattended rotation for validating that long-run wiring, device selection, and summary retention work.",
        default_template_type=TaskTemplateType.MONKEY.value,
        default_interval_minutes=15,
        default_max_rounds=4,
        recommended_device_count=1,
        recommended_rotation_strategy="round_robin",
        default_tags=("long_run", "smoke"),
        risk_notes=(
            "Coverage is intentionally shallow; use only as a confidence check before longer soak runs.",
        ),
    ),
    LongRunTemplate(
        template_id="overnight_long_run",
        name="Overnight Long Run",
        description="Balanced overnight soak profile for catching intermittent crashes, ANRs, offline devices, and recovery behavior.",
        default_template_type=TaskTemplateType.MONKEY.value,
        default_interval_minutes=60,
        default_max_rounds=12,
        recommended_device_count=2,
        recommended_rotation_strategy="round_robin",
        default_tags=("long_run", "overnight", "soak"),
        risk_notes=(
            "Keep backup devices available because a single offline device can otherwise reduce overnight signal.",
            "Review morning reports before reusing quarantined devices.",
        ),
    ),
    LongRunTemplate(
        template_id="weekly_soak",
        name="Weekly Soak",
        description="High-signal weekly stability profile with broad device rotation and conservative failure isolation.",
        default_template_type=TaskTemplateType.CUSTOM.value,
        default_interval_minutes=120,
        default_max_rounds=84,
        recommended_device_count=4,
        recommended_rotation_strategy="round_robin",
        default_tags=("long_run", "weekly", "soak"),
        risk_notes=(
            "Long retention windows can grow task metadata; keep history limits bounded.",
            "Device quarantine should be reviewed periodically to avoid exhausting the pool.",
        ),
    ),
    LongRunTemplate(
        template_id="custom_long_run",
        name="Custom Long Run",
        description="Explicitly customizable long-run profile for teams that already know their interval, round count, and device pool.",
        default_template_type=TaskTemplateType.CUSTOM.value,
        default_interval_minutes=60,
        default_max_rounds=24,
        recommended_device_count=1,
        recommended_rotation_strategy="round_robin",
        default_tags=("long_run", "custom"),
        risk_notes=(
            "Custom profiles should document why interval, round count, and device count differ from the standard templates.",
        ),
    ),
)


class UnattendedTemplatesMixin:
    def list_long_run_templates(self) -> list[LongRunTemplate]:
        return list(self._LONG_RUN_TEMPLATES)

    def get_long_run_template(self, template_id: str) -> LongRunTemplate:
        normalized_template_id = self._normalize_template_id(template_id)
        for template in self._LONG_RUN_TEMPLATES:
            if template.template_id == normalized_template_id:
                return template
        raise LongRunTemplateNotFound(f"Long-run template '{template_id}' was not found.")

    def build_long_run_plan(
        self,
        template_id: str,
        *,
        interval_minutes: int | None = None,
        max_rounds: int | None = None,
        desired_device_count: int | None = None,
        primary_device_ids: Sequence[str] = (),
        backup_device_ids: Sequence[str] = (),
        failure_threshold: int | None = None,
        max_round_history: int | None = None,
        max_device_window_history: int | None = None,
        rotation_strategy: str | None = None,
        rotation_advance_policy: str | None = None,
        enabled: bool = True,
        start_now: bool = False,
        tags: Sequence[str] = (),
    ) -> LongRunPlan:
        template = self.get_long_run_template(template_id)
        resolved_interval = max(1, int(interval_minutes or template.default_interval_minutes))
        resolved_max_rounds = max(1, int(max_rounds or template.default_max_rounds))
        resolved_device_count = max(1, int(desired_device_count or template.recommended_device_count))
        resolved_rotation_strategy = self._normalize_rotation_strategy(
            rotation_strategy or template.recommended_rotation_strategy
        )
        resolved_rotation_advance_policy = self._normalize_rotation_advance_policy(
            rotation_advance_policy or "every_round"
        )
        resolved_failure_threshold = max(1, int(failure_threshold or 3))
        resolved_round_history = max(1, int(max_round_history or min(max(resolved_max_rounds, 10), 100)))
        resolved_window_history = max(
            1,
            int(max_device_window_history or min(max(resolved_max_rounds, 10), 100)),
        )
        configure_kwargs = {
            "interval_minutes": resolved_interval,
            "desired_device_count": resolved_device_count,
            "primary_device_ids": [str(item) for item in primary_device_ids],
            "backup_device_ids": [str(item) for item in backup_device_ids],
            "failure_threshold": resolved_failure_threshold,
            "max_round_history": resolved_round_history,
            "rotation_strategy": resolved_rotation_strategy,
            "rotation_advance_policy": resolved_rotation_advance_policy,
            "max_device_window_history": resolved_window_history,
            "enabled": bool(enabled),
            "start_now": bool(start_now),
        }
        default_tags = self._dedupe_strings([*template.default_tags, *tags])
        overrides = self._build_long_run_plan_overrides(
            template,
            configure_kwargs,
            resolved_max_rounds,
            provided={
                "interval_minutes": interval_minutes,
                "max_rounds": max_rounds,
                "desired_device_count": desired_device_count,
                "primary_device_ids": primary_device_ids,
                "backup_device_ids": backup_device_ids,
                "failure_threshold": failure_threshold,
                "max_round_history": max_round_history,
                "max_device_window_history": max_device_window_history,
                "rotation_strategy": rotation_strategy,
                "rotation_advance_policy": rotation_advance_policy,
                "enabled": enabled if enabled is not True else None,
                "start_now": start_now if start_now else None,
                "tags": tags,
            },
        )
        return LongRunPlan(
            template=template,
            configure_kwargs=configure_kwargs,
            runner_kwargs={"max_iterations": resolved_max_rounds},
            task_metadata_suggestions={
                "long_run_template_id": template.template_id,
                "long_run_template_name": template.name,
                "default_template_type": template.default_template_type,
                "tags": default_tags,
                "risk_notes": list(template.risk_notes),
            },
            overrides=overrides,
            notes=(
                "Plan generation does not start execution; pass configure_kwargs to configure_task when ready.",
                "runner_kwargs.max_iterations maps the template round-count recommendation to the unattended patrol runner.",
            ),
        )

    @classmethod
    def _normalize_template_id(cls, template_id: str) -> str:
        return str(template_id or "").strip().lower()

    @staticmethod
    def _dedupe_strings(items: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _build_long_run_plan_overrides(
        template: LongRunTemplate,
        configure_kwargs: dict[str, Any],
        max_rounds: int,
        *,
        provided: dict[str, Any],
    ) -> dict[str, Any]:
        defaults = {
            "interval_minutes": template.default_interval_minutes,
            "max_rounds": template.default_max_rounds,
            "desired_device_count": template.recommended_device_count,
            "rotation_strategy": template.recommended_rotation_strategy,
            "rotation_advance_policy": "every_round",
            "failure_threshold": 3,
            "max_round_history": min(max(template.default_max_rounds, 10), 100),
            "max_device_window_history": min(max(template.default_max_rounds, 10), 100),
            "primary_device_ids": [],
            "backup_device_ids": [],
            "enabled": True,
            "start_now": False,
            "tags": [],
        }
        resolved = {
            "interval_minutes": configure_kwargs["interval_minutes"],
            "max_rounds": max_rounds,
            "desired_device_count": configure_kwargs["desired_device_count"],
            "rotation_strategy": configure_kwargs["rotation_strategy"],
            "rotation_advance_policy": configure_kwargs["rotation_advance_policy"],
            "failure_threshold": configure_kwargs["failure_threshold"],
            "max_round_history": configure_kwargs["max_round_history"],
            "max_device_window_history": configure_kwargs["max_device_window_history"],
            "primary_device_ids": list(configure_kwargs["primary_device_ids"]),
            "backup_device_ids": list(configure_kwargs["backup_device_ids"]),
            "enabled": configure_kwargs["enabled"],
            "start_now": configure_kwargs["start_now"],
            "tags": [str(item) for item in provided.get("tags", ()) or ()],
        }
        overrides: dict[str, Any] = {}
        for key, raw_value in provided.items():
            if raw_value is None:
                continue
            value = list(raw_value) if isinstance(raw_value, tuple) else raw_value
            default_value = defaults.get(key)
            resolved_value = resolved.get(key, value)
            if resolved_value != default_value or value:
                overrides[key] = {"default": default_value, "value": resolved_value}
        return overrides
