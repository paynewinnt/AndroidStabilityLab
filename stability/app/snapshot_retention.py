from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import shutil
from typing import Any, Mapping

from stability.domain import AnalysisSnapshotRecord
from stability.domain.value_objects import utcnow


class SnapshotRetentionMixin:
    """Snapshot deletion, retention planning, and integrity helpers."""

    def delete_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        snapshot_key = snapshot_id.strip()
        snapshot_dir = self._root_dir / snapshot_key
        detail_path = snapshot_dir / "snapshot.json"
        if not detail_path.exists():
            raise self._snapshot_not_found(snapshot_key)
        record = self._load_record(detail_path)
        integrity = self.inspect_snapshot_integrity(record)
        shutil.rmtree(snapshot_dir)
        return {
            "snapshot_id": record.snapshot_id,
            "snapshot_type": record.snapshot_type,
            "name": record.name,
            "deleted": True,
            "deleted_dir": str(snapshot_dir),
            "integrity_before_delete": integrity,
        }

    def plan_retention(
        self,
        *,
        snapshot_type: str = "",
        created_by: str = "",
        max_count: int | None = None,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        if max_count is None and max_age_days is None:
            raise ValueError("At least one retention policy must be provided: max_count or max_age_days.")
        if max_count is not None and max_count < 0:
            raise ValueError("max_count must be >= 0.")
        if max_age_days is not None and max_age_days < 0:
            raise ValueError("max_age_days must be >= 0.")

        items = self.list_snapshots(snapshot_type=snapshot_type, created_by=created_by, limit=1000000)
        cutoff = utcnow() - timedelta(days=max_age_days) if max_age_days is not None else None
        candidates: list[dict[str, Any]] = []
        kept: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            reasons: list[str] = []
            if max_count is not None and index >= max_count:
                reasons.append("exceeds_max_count")
            if cutoff is not None and item.created_at < cutoff:
                reasons.append("older_than_max_age_days")
            payload = {
                "snapshot_id": item.snapshot_id,
                "snapshot_type": item.snapshot_type,
                "name": item.name,
                "created_at": item.created_at.isoformat(),
                "created_by": item.created_by,
                "detail_path": item.detail_path,
                "markdown_path": item.markdown_path,
                "rule_versions": dict(item.rule_versions),
                "source_summary": dict(item.source_summary),
                "reasons": reasons,
            }
            if reasons:
                candidates.append(payload)
            else:
                kept.append(payload)

        return {
            "policy": {
                "snapshot_type": snapshot_type or None,
                "created_by": created_by or None,
                "max_count": max_count,
                "max_age_days": max_age_days,
                "cutoff_created_at": cutoff.isoformat() if cutoff is not None else None,
            },
            "matched_snapshot_count": len(items),
            "delete_count": len(candidates),
            "keep_count": len(kept),
            "candidates": candidates,
            "kept": kept,
        }

    def apply_retention(
        self,
        *,
        snapshot_type: str = "",
        created_by: str = "",
        max_count: int | None = None,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        plan = self.plan_retention(
            snapshot_type=snapshot_type,
            created_by=created_by,
            max_count=max_count,
            max_age_days=max_age_days,
        )
        deleted: list[dict[str, Any]] = []
        for item in plan["candidates"]:
            deleted.append(self.delete_snapshot(str(item["snapshot_id"])))
        return {
            "policy": dict(plan["policy"]),
            "matched_snapshot_count": plan["matched_snapshot_count"],
            "delete_count": len(deleted),
            "keep_count": plan["keep_count"],
            "deleted": deleted,
        }

    def inspect_snapshot_integrity(self, record: AnalysisSnapshotRecord) -> dict[str, Any]:
        tracked_paths = [
            ("detail_path", record.detail_path),
            ("markdown_path", record.markdown_path),
        ]
        source_refs = record.source_refs if isinstance(record.source_refs, Mapping) else {}
        for key in ("report_paths", "execution_log_paths", "artifact_paths"):
            for item in source_refs.get(key, ()) or ():
                if isinstance(item, str) and item:
                    tracked_paths.append((key, item))

        existing_paths: list[str] = []
        missing_paths: list[str] = []
        for _, raw_path in tracked_paths:
            candidate = Path(raw_path)
            if candidate.exists():
                existing_paths.append(str(candidate))
            else:
                missing_paths.append(str(candidate))

        return {
            "tracked_path_count": len(tracked_paths),
            "existing_path_count": len(existing_paths),
            "missing_path_count": len(missing_paths),
            "detail_path_exists": Path(record.detail_path).exists(),
            "markdown_path_exists": Path(record.markdown_path).exists(),
            "missing_paths": missing_paths,
        }
