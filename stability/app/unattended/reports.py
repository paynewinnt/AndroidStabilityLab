from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from stability.domain.value_objects import utcnow

from .models import UnattendedDailyReport, UnattendedWeeklyReport


class UnattendedReportsMixin:
    def build_daily_report(
        self,
        *,
        report_date: str = "",
        task_id: str = "",
    ) -> UnattendedDailyReport:
        target_date = self._resolve_report_date(report_date)
        task_records = (
            [self.get_task_record(task_id.strip())]
            if task_id.strip()
            else self.list_task_records(limit=None)
        )
        round_records: list[dict[str, Any]] = []
        task_summaries: list[dict[str, Any]] = []
        issue_type_distribution: dict[str, int] = {}
        total_instance_count = 0
        failed_instance_count = 0
        offline_event_count = 0
        recovery_attempt_count = 0
        recovery_success_count = 0
        total_runtime_seconds = 0
        online_capacity = 0
        visible_capacity = 0
        interruption_rounds: list[dict[str, Any]] = []

        for record in task_records:
            matched_rounds = [
                dict(item)
                for item in record.recent_rounds
                if self._round_matches_report_date(item, target_date)
            ]
            if not matched_rounds:
                continue
            executed_round_count = sum(1 for item in matched_rounds if self._round_is_executed(item))
            failed_round_count = sum(1 for item in matched_rounds if self._round_is_failed(item))
            for round_record in matched_rounds:
                round_records.append(round_record)
                total_instance_count += int(round_record.get("instance_count", 0) or 0)
                failed_instance_count += int(round_record.get("failed_instance_count", 0) or 0)
                offline_event_count += int(round_record.get("offline_event_count", 0) or 0)
                recovery_attempt_count += int(round_record.get("recovery_attempt_count", 0) or 0)
                recovery_success_count += int(round_record.get("recovery_success_count", 0) or 0)
                total_runtime_seconds += self._round_runtime_seconds(round_record)
                assigned_count = len(list(round_record.get("assigned_device_ids", []) or []))
                unavailable_count = len(list(round_record.get("unavailable_device_ids", []) or []))
                online_capacity += assigned_count
                visible_capacity += assigned_count + unavailable_count
                for issue_type, count in dict(round_record.get("issue_type_counts", {}) or {}).items():
                    issue_key = str(issue_type or "").strip()
                    if not issue_key:
                        continue
                    issue_type_distribution[issue_key] = issue_type_distribution.get(issue_key, 0) + int(count or 0)
                if self._round_is_interruption(round_record):
                    interruption_rounds.append(
                        {
                            "task_id": record.task_id,
                            "task_name": record.task_name,
                            "round_id": str(round_record.get("round_id", "") or ""),
                            "status": str(round_record.get("status", "") or ""),
                            "run_id": str(round_record.get("run_id", "") or ""),
                            "triggered_at": str(round_record.get("triggered_at", "") or ""),
                            "assigned_device_ids": list(round_record.get("assigned_device_ids", []) or []),
                            "unavailable_device_ids": list(round_record.get("unavailable_device_ids", []) or []),
                        }
                    )
            task_summaries.append(
                {
                    "task_id": record.task_id,
                    "task_name": record.task_name,
                    "round_count": len(matched_rounds),
                    "executed_round_count": executed_round_count,
                    "failed_round_count": failed_round_count,
                    "offline_event_count": sum(int(item.get("offline_event_count", 0) or 0) for item in matched_rounds),
                    "replacement_round_count": sum(
                        1 for item in matched_rounds if list(item.get("replacement_events", []) or [])
                    ),
                    "latest_status": str(matched_rounds[0].get("status", "") or ""),
                    "rotation_strategy": record.rotation_strategy,
                    "rotation_cursor": record.rotation_cursor,
                }
            )

        round_count = len(round_records)
        executed_round_count = sum(1 for item in round_records if self._round_is_executed(item))
        failed_round_count = sum(1 for item in round_records if self._round_is_failed(item))
        skipped_round_count = round_count - executed_round_count
        failed_rate = failed_instance_count / total_instance_count if total_instance_count > 0 else 0.0
        offline_rate = offline_event_count / total_instance_count if total_instance_count > 0 else 0.0
        recovery_success_rate = recovery_success_count / recovery_attempt_count if recovery_attempt_count > 0 else 0.0
        device_online_rate = online_capacity / visible_capacity if visible_capacity > 0 else 1.0
        quarantined_devices = self._device_service.list_quarantined_devices()
        top_issue_types = [
            {"issue_type": item[0], "count": item[1]}
            for item in sorted(issue_type_distribution.items(), key=lambda entry: (-entry[1], entry[0]))[:5]
        ]
        return UnattendedDailyReport(
            report_date=target_date.isoformat(),
            generated_at=utcnow(),
            task_count=len(task_records),
            active_task_count=len(task_summaries),
            round_count=round_count,
            executed_round_count=executed_round_count,
            skipped_round_count=skipped_round_count,
            failed_round_count=failed_round_count,
            total_runtime_seconds=total_runtime_seconds,
            total_runtime_hours=round(total_runtime_seconds / 3600, 3),
            device_online_rate=device_online_rate,
            failed_rate=failed_rate,
            offline_rate=offline_rate,
            recovery_success_rate=recovery_success_rate,
            quarantined_device_count=len(quarantined_devices),
            quarantined_device_ids=tuple(device.device_id for device in quarantined_devices),
            issue_type_distribution=dict(issue_type_distribution),
            top_issue_types=tuple(top_issue_types),
            interruption_rounds=tuple(interruption_rounds),
            task_summaries=tuple(task_summaries),
            metrics={
                "instance_count": total_instance_count,
                "failed_instance_count": failed_instance_count,
                "offline_event_count": offline_event_count,
                "recovery_attempt_count": recovery_attempt_count,
                "recovery_success_count": recovery_success_count,
                "online_capacity": online_capacity,
                "visible_capacity": visible_capacity,
            },
        )

    def build_weekly_report(
        self,
        *,
        report_date: str = "",
        task_id: str = "",
    ) -> UnattendedWeeklyReport:
        anchor_date = self._resolve_report_date(report_date)
        week_start_date, week_end_date = self._resolve_report_week(anchor_date)
        task_records = (
            [self.get_task_record(task_id.strip())]
            if task_id.strip()
            else self.list_task_records(limit=None)
        )
        round_records: list[dict[str, Any]] = []
        task_summaries: list[dict[str, Any]] = []
        issue_type_distribution: dict[str, int] = {}
        total_instance_count = 0
        failed_instance_count = 0
        offline_event_count = 0
        recovery_attempt_count = 0
        recovery_success_count = 0
        total_runtime_seconds = 0
        online_capacity = 0
        visible_capacity = 0
        interruption_rounds: list[dict[str, Any]] = []
        daily_buckets: dict[str, dict[str, Any]] = {}

        for record in task_records:
            matched_rounds = [
                dict(item)
                for item in record.recent_rounds
                if self._round_matches_report_window(item, week_start_date, week_end_date)
            ]
            if not matched_rounds:
                continue
            executed_round_count = sum(1 for item in matched_rounds if self._round_is_executed(item))
            failed_round_count = sum(1 for item in matched_rounds if self._round_is_failed(item))
            offline_count_for_task = 0
            replacement_round_count = 0
            active_dates: set[str] = set()
            for round_record in matched_rounds:
                round_records.append(round_record)
                round_date = self._round_report_date(round_record)
                if round_date is not None:
                    active_dates.add(round_date.isoformat())
                    bucket = daily_buckets.setdefault(
                        round_date.isoformat(),
                        {
                            "report_date": round_date.isoformat(),
                            "round_count": 0,
                            "executed_round_count": 0,
                            "failed_round_count": 0,
                            "offline_event_count": 0,
                            "replacement_round_count": 0,
                        },
                    )
                    bucket["round_count"] += 1
                    if self._round_is_executed(round_record):
                        bucket["executed_round_count"] += 1
                    if self._round_is_failed(round_record):
                        bucket["failed_round_count"] += 1
                    bucket["offline_event_count"] += int(round_record.get("offline_event_count", 0) or 0)
                    if list(round_record.get("replacement_events", []) or []):
                        bucket["replacement_round_count"] += 1
                total_instance_count += int(round_record.get("instance_count", 0) or 0)
                failed_instance_count += int(round_record.get("failed_instance_count", 0) or 0)
                offline_events = int(round_record.get("offline_event_count", 0) or 0)
                offline_event_count += offline_events
                offline_count_for_task += offline_events
                recovery_attempt_count += int(round_record.get("recovery_attempt_count", 0) or 0)
                recovery_success_count += int(round_record.get("recovery_success_count", 0) or 0)
                total_runtime_seconds += self._round_runtime_seconds(round_record)
                assigned_count = len(list(round_record.get("assigned_device_ids", []) or []))
                unavailable_count = len(list(round_record.get("unavailable_device_ids", []) or []))
                online_capacity += assigned_count
                visible_capacity += assigned_count + unavailable_count
                if list(round_record.get("replacement_events", []) or []):
                    replacement_round_count += 1
                for issue_type, count in dict(round_record.get("issue_type_counts", {}) or {}).items():
                    issue_key = str(issue_type or "").strip()
                    if not issue_key:
                        continue
                    issue_type_distribution[issue_key] = issue_type_distribution.get(issue_key, 0) + int(count or 0)
                if self._round_is_interruption(round_record):
                    interruption_rounds.append(
                        {
                            "task_id": record.task_id,
                            "task_name": record.task_name,
                            "round_id": str(round_record.get("round_id", "") or ""),
                            "status": str(round_record.get("status", "") or ""),
                            "run_id": str(round_record.get("run_id", "") or ""),
                            "triggered_at": str(round_record.get("triggered_at", "") or ""),
                            "assigned_device_ids": list(round_record.get("assigned_device_ids", []) or []),
                            "unavailable_device_ids": list(round_record.get("unavailable_device_ids", []) or []),
                        }
                    )
            task_summaries.append(
                {
                    "task_id": record.task_id,
                    "task_name": record.task_name,
                    "round_count": len(matched_rounds),
                    "active_day_count": len(active_dates),
                    "executed_round_count": executed_round_count,
                    "failed_round_count": failed_round_count,
                    "offline_event_count": offline_count_for_task,
                    "replacement_round_count": replacement_round_count,
                    "latest_status": str(matched_rounds[0].get("status", "") or ""),
                    "rotation_strategy": record.rotation_strategy,
                    "rotation_cursor": record.rotation_cursor,
                }
            )

        round_count = len(round_records)
        executed_round_count = sum(1 for item in round_records if self._round_is_executed(item))
        failed_round_count = sum(1 for item in round_records if self._round_is_failed(item))
        skipped_round_count = round_count - executed_round_count
        failed_rate = failed_instance_count / total_instance_count if total_instance_count > 0 else 0.0
        offline_rate = offline_event_count / total_instance_count if total_instance_count > 0 else 0.0
        recovery_success_rate = recovery_success_count / recovery_attempt_count if recovery_attempt_count > 0 else 0.0
        device_online_rate = online_capacity / visible_capacity if visible_capacity > 0 else 1.0
        quarantined_devices = self._device_service.list_quarantined_devices()
        top_issue_types = [
            {"issue_type": item[0], "count": item[1]}
            for item in sorted(issue_type_distribution.items(), key=lambda entry: (-entry[1], entry[0]))[:5]
        ]
        daily_summaries = [
            dict(item)
            for item in sorted(daily_buckets.values(), key=lambda entry: str(entry.get("report_date", "")))
        ]
        iso_year, iso_week, _ = anchor_date.isocalendar()
        return UnattendedWeeklyReport(
            week_key=f"{iso_year}-W{iso_week:02d}",
            anchor_date=anchor_date.isoformat(),
            week_start_date=week_start_date.isoformat(),
            week_end_date=week_end_date.isoformat(),
            generated_at=utcnow(),
            task_count=len(task_records),
            active_task_count=len(task_summaries),
            active_day_count=len(daily_summaries),
            round_count=round_count,
            executed_round_count=executed_round_count,
            skipped_round_count=skipped_round_count,
            failed_round_count=failed_round_count,
            total_runtime_seconds=total_runtime_seconds,
            total_runtime_hours=round(total_runtime_seconds / 3600, 3),
            device_online_rate=device_online_rate,
            failed_rate=failed_rate,
            offline_rate=offline_rate,
            recovery_success_rate=recovery_success_rate,
            quarantined_device_count=len(quarantined_devices),
            quarantined_device_ids=tuple(device.device_id for device in quarantined_devices),
            issue_type_distribution=dict(issue_type_distribution),
            top_issue_types=tuple(top_issue_types),
            interruption_rounds=tuple(interruption_rounds),
            task_summaries=tuple(task_summaries),
            daily_summaries=tuple(daily_summaries),
            metrics={
                "instance_count": total_instance_count,
                "failed_instance_count": failed_instance_count,
                "offline_event_count": offline_event_count,
                "recovery_attempt_count": recovery_attempt_count,
                "recovery_success_count": recovery_success_count,
                "online_capacity": online_capacity,
                "visible_capacity": visible_capacity,
            },
        )

    @staticmethod
    def _resolve_report_date(value: str) -> date:
        raw = str(value or "").strip()
        if not raw:
            return utcnow().date()
        return date.fromisoformat(raw)

    @staticmethod
    def _resolve_report_week(anchor_date: date) -> tuple[date, date]:
        week_start_date = anchor_date - timedelta(days=anchor_date.weekday())
        return week_start_date, week_start_date + timedelta(days=6)

    def _round_matches_report_date(self, round_record: dict[str, Any], target_date: date) -> bool:
        return self._round_matches_report_window(round_record, target_date, target_date)

    def _round_matches_report_window(
        self,
        round_record: dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> bool:
        candidate_date = self._round_report_date(round_record)
        return bool(candidate_date is not None and start_date <= candidate_date <= end_date)

    def _round_report_date(self, round_record: dict[str, Any]) -> date | None:
        triggered_at = self._parse_datetime(round_record.get("triggered_at"))
        finished_at = self._parse_datetime(round_record.get("finished_at"))
        candidate = triggered_at or finished_at
        return candidate.date() if candidate is not None else None

    @staticmethod
    def _round_is_executed(round_record: dict[str, Any]) -> bool:
        if str(round_record.get("run_id", "") or "").strip():
            return True
        status = str(round_record.get("status", "") or "")
        return status in {"success", "failed", "precheck_failed"}

    @classmethod
    def _round_is_failed(cls, round_record: dict[str, Any]) -> bool:
        status = str(round_record.get("status", "") or "")
        if status in {"failed", "precheck_failed", "no_schedulable_devices"}:
            return True
        if int(round_record.get("failed_instance_count", 0) or 0) > 0:
            return True
        if int(round_record.get("offline_event_count", 0) or 0) > 0 and not cls._round_is_executed(round_record):
            return True
        return False

    @classmethod
    def _round_is_interruption(cls, round_record: dict[str, Any]) -> bool:
        status = str(round_record.get("status", "") or "")
        if status == "success":
            return False
        if status in {"not_due", "task_disabled"}:
            return False
        return cls._round_is_failed(round_record) or not cls._round_is_executed(round_record)

    def _round_runtime_seconds(self, round_record: dict[str, Any]) -> int:
        triggered_at = self._parse_datetime(round_record.get("triggered_at"))
        finished_at = self._parse_datetime(round_record.get("finished_at"))
        if triggered_at is None or finished_at is None:
            return 0
        return max(0, int((finished_at - triggered_at).total_seconds()))

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()
