"""Helpers for planning runtime artifact locations for V1 executions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional, Union

PathLike = Union[str, Path]


@dataclass(frozen=True)
class ArtifactScope:
    """Identity fields used to derive a stable runtime directory tree."""

    task_id: str
    execution_id: str
    run_id: Optional[str] = None
    device_id: Optional[str] = None


@dataclass(frozen=True)
class ArtifactLayout:
    """Resolved paths for the main execution outputs."""

    root: Path
    logs_dir: Path
    artifacts_dir: Path
    reports_dir: Path
    monitoring_dir: Path
    temp_dir: Path


class ArtifactPathPlanner:
    """Plan file system locations without embedding artifact collection logic."""

    def __init__(self, runtime_root: PathLike = "runtime") -> None:
        self.runtime_root = Path(runtime_root)

    def plan(self, scope: ArtifactScope, ensure_exists: bool = False) -> ArtifactLayout:
        task_segment = self._safe_segment(scope.task_id)
        execution_segment = self._safe_segment(scope.execution_id)

        root = self.runtime_root / "tasks" / task_segment
        if scope.run_id:
            root = root / "runs" / self._safe_segment(scope.run_id)
        root = root / "executions" / execution_segment
        if scope.device_id:
            root = root / "devices" / self._safe_segment(scope.device_id)

        layout = ArtifactLayout(
            root=root,
            logs_dir=root / "logs",
            artifacts_dir=root / "artifacts",
            reports_dir=root / "report",
            monitoring_dir=root / "monitoring",
            temp_dir=root / "temp",
        )

        if ensure_exists:
            self.ensure_layout(layout)

        return layout

    def plan_issue_artifact_path(
        self,
        scope: ArtifactScope,
        issue_id: str,
        artifact_name: str,
        ensure_parent: bool = False,
    ) -> Path:
        layout = self.plan(scope, ensure_exists=ensure_parent)
        issue_dir = layout.artifacts_dir / self._safe_segment(issue_id)
        if ensure_parent:
            issue_dir.mkdir(parents=True, exist_ok=True)
        return issue_dir / self._safe_segment(artifact_name, allow_dot=True)

    def default_report_path(
        self,
        scope: ArtifactScope,
        extension: str = "md",
        ensure_parent: bool = False,
    ) -> Path:
        layout = self.plan(scope, ensure_exists=ensure_parent)
        filename = f"report.{extension.lstrip('.')}"
        return layout.reports_dir / filename

    @staticmethod
    def ensure_layout(layout: ArtifactLayout) -> None:
        for path in (
            layout.root,
            layout.logs_dir,
            layout.artifacts_dir,
            layout.reports_dir,
            layout.monitoring_dir,
            layout.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_segment(value: str, allow_dot: bool = False) -> str:
        pattern = r"[^A-Za-z0-9._-]+" if allow_dot else r"[^A-Za-z0-9_-]+"
        sanitized = re.sub(pattern, "_", str(value).strip())
        sanitized = sanitized.strip("._")
        return sanitized or "unknown"
