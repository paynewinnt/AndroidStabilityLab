from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from stability.time_utils import now_beijing_string, utcnow


RUNTIME_CATEGORIES: Mapping[str, tuple[str, ...]] = {
    "tasks": ("tasks",),
    "analysis": (
        "analysis_snapshots",
        "analysis_review_reports",
        "analysis_review_report_comparisons",
        "analysis_review_report_baseline_audits",
        "analysis_review_report_baselines",
    ),
    "admission": ("admission_cases",),
    "collaboration": ("collaboration",),
    "integration": ("integration_outbox",),
    "runner": ("unattended_runner",),
    "apks": ("apks",),
}

PROTECTED_FILES = {"webhooks.json", "sessions.json", "actors.json"}


@dataclass(frozen=True)
class RuntimePathSummary:
    category: str
    path: str
    exists: bool
    file_count: int = 0
    dir_count: int = 0
    size_bytes: int = 0
    newest_mtime: str = ""
    issue: str = ""


@dataclass(frozen=True)
class RuntimeDoctorResult:
    root_dir: str
    generated_at: str
    ok: bool
    total_size_bytes: int
    total_file_count: int
    summaries: tuple[RuntimePathSummary, ...]
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeCleanupCandidate:
    category: str
    path: str
    reason: str
    size_bytes: int
    file_count: int


@dataclass(frozen=True)
class RuntimeCleanupResult:
    root_dir: str
    generated_at: str
    dry_run: bool
    max_age_days: int
    categories: tuple[str, ...]
    candidates: tuple[RuntimeCleanupCandidate, ...]
    deleted_paths: tuple[str, ...] = ()
    skipped_paths: tuple[str, ...] = ()
    reclaimed_bytes: int = 0


@dataclass(frozen=True)
class RuntimeExportResult:
    root_dir: str
    output_path: str
    generated_at: str
    categories: tuple[str, ...]
    included_files: int
    included_bytes: int
    manifest: dict[str, Any] = field(default_factory=dict)


class RuntimeLifecycleService:
    """Inspect, export and safely clean local runtime data."""

    def __init__(self, root_dir: str | Path = "runtime") -> None:
        self._root_dir = Path(root_dir)

    def doctor(self) -> RuntimeDoctorResult:
        summaries = tuple(self._summaries())
        issues: list[str] = []
        if not self._root_dir.exists():
            issues.append(f"runtime root does not exist: {self._root_dir}")
        elif not self._root_dir.is_dir():
            issues.append(f"runtime root is not a directory: {self._root_dir}")
        total_size = sum(item.size_bytes for item in summaries)
        total_files = sum(item.file_count for item in summaries)
        issues.extend(item.issue for item in summaries if item.issue)
        return RuntimeDoctorResult(
            root_dir=str(self._root_dir),
            generated_at=now_beijing_string(),
            ok=not issues,
            total_size_bytes=total_size,
            total_file_count=total_files,
            summaries=summaries,
            issues=tuple(issues),
        )

    def cleanup(
        self,
        *,
        categories: Sequence[str] | None = None,
        max_age_days: int = 14,
        apply: bool = False,
    ) -> RuntimeCleanupResult:
        selected = self._normalize_categories(categories)
        cutoff = utcnow().timestamp() - max(max_age_days, 0) * 86400
        candidates = tuple(self._cleanup_candidates(selected, cutoff=cutoff, max_age_days=max_age_days))
        deleted: list[str] = []
        skipped: list[str] = []
        reclaimed = 0
        if apply:
            for candidate in candidates:
                path = self._safe_runtime_path(candidate.path)
                if self._is_protected(path):
                    skipped.append(str(path))
                    continue
                reclaimed += candidate.size_bytes
                self._delete_path(path)
                deleted.append(str(path))
        return RuntimeCleanupResult(
            root_dir=str(self._root_dir),
            generated_at=now_beijing_string(),
            dry_run=not apply,
            max_age_days=max_age_days,
            categories=tuple(selected),
            candidates=candidates,
            deleted_paths=tuple(deleted),
            skipped_paths=tuple(skipped),
            reclaimed_bytes=reclaimed,
        )

    def export(
        self,
        output_path: str | Path,
        *,
        categories: Sequence[str] | None = None,
    ) -> RuntimeExportResult:
        selected = self._normalize_categories(categories)
        output = Path(output_path)
        if output.exists() and output.is_dir():
            output = output / self._default_export_name()
        output.parent.mkdir(parents=True, exist_ok=True)
        files = list(self._iter_category_files(selected))
        manifest = {
            "root_dir": str(self._root_dir),
            "generated_at": now_beijing_string(),
            "categories": list(selected),
            "file_count": len(files),
        }
        total_bytes = 0
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in files:
                if not path.is_file():
                    continue
                total_bytes += path.stat().st_size
                archive.write(path, path.relative_to(self._root_dir.parent))
        return RuntimeExportResult(
            root_dir=str(self._root_dir),
            output_path=str(output),
            generated_at=manifest["generated_at"],
            categories=tuple(selected),
            included_files=len(files),
            included_bytes=total_bytes,
            manifest=manifest,
        )

    def _summaries(self) -> Iterable[RuntimePathSummary]:
        for category, names in RUNTIME_CATEGORIES.items():
            for name in names:
                path = self._root_dir / name
                yield self._summarize_path(category, path)

    def _summarize_path(self, category: str, path: Path) -> RuntimePathSummary:
        if not path.exists():
            return RuntimePathSummary(category=category, path=str(path), exists=False)
        if not path.is_dir():
            return RuntimePathSummary(category=category, path=str(path), exists=True, issue="not_directory")
        file_count = 0
        dir_count = 0
        size = 0
        newest = 0.0
        try:
            for item in path.rglob("*"):
                if item.is_dir():
                    dir_count += 1
                    continue
                if item.is_file():
                    file_count += 1
                    stat = item.stat()
                    size += stat.st_size
                    newest = max(newest, stat.st_mtime)
        except OSError as exc:
            return RuntimePathSummary(category=category, path=str(path), exists=True, issue=str(exc))
        return RuntimePathSummary(
            category=category,
            path=str(path),
            exists=True,
            file_count=file_count,
            dir_count=dir_count,
            size_bytes=size,
            newest_mtime=self._mtime_display(newest),
        )

    def _cleanup_candidates(
        self,
        categories: Sequence[str],
        *,
        cutoff: float,
        max_age_days: int,
    ) -> Iterable[RuntimeCleanupCandidate]:
        for category in categories:
            for name in RUNTIME_CATEGORIES.get(category, ()):
                base = self._root_dir / name
                if not base.exists() or not base.is_dir():
                    continue
                for child in sorted(base.iterdir()):
                    if self._is_protected(child):
                        continue
                    if not self._older_than(child, cutoff):
                        continue
                    size, files = self._path_size(child)
                    yield RuntimeCleanupCandidate(
                        category=category,
                        path=str(child),
                        reason=f"older_than_{max_age_days}_days",
                        size_bytes=size,
                        file_count=files,
                    )

    def _iter_category_files(self, categories: Sequence[str]) -> Iterable[Path]:
        for category in categories:
            for name in RUNTIME_CATEGORIES.get(category, ()):
                base = self._root_dir / name
                if not base.exists():
                    continue
                if base.is_file():
                    yield base
                    continue
                for item in base.rglob("*"):
                    if item.is_file():
                        yield item

    def _normalize_categories(self, categories: Sequence[str] | None) -> tuple[str, ...]:
        raw = [str(item or "").strip() for item in categories or () if str(item or "").strip()]
        if not raw or "all" in raw:
            return tuple(RUNTIME_CATEGORIES)
        unknown = [item for item in raw if item not in RUNTIME_CATEGORIES]
        if unknown:
            raise ValueError(f"Unknown runtime categories: {', '.join(unknown)}")
        return tuple(dict.fromkeys(raw))

    def _safe_runtime_path(self, raw: str) -> Path:
        path = Path(raw).resolve(strict=False)
        root = self._root_dir.resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Path is outside runtime root: {path}") from exc
        return path

    @staticmethod
    def _path_size(path: Path) -> tuple[int, int]:
        if path.is_file():
            return path.stat().st_size, 1
        size = 0
        files = 0
        for item in path.rglob("*"):
            if item.is_file():
                files += 1
                size += item.stat().st_size
        return size, files

    @staticmethod
    def _older_than(path: Path, cutoff: float) -> bool:
        try:
            return path.stat().st_mtime < cutoff
        except OSError:
            return False

    @staticmethod
    def _delete_path(path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    @staticmethod
    def _is_protected(path: Path) -> bool:
        if path.name in PROTECTED_FILES:
            return True
        return path.name in {"latest"}

    @staticmethod
    def _mtime_display(timestamp: float) -> str:
        if timestamp <= 0:
            return ""
        from datetime import datetime
        from stability.time_utils import format_beijing_datetime

        return format_beijing_datetime(datetime.fromtimestamp(timestamp)) or ""

    @staticmethod
    def _default_export_name() -> str:
        safe = now_beijing_string().replace(" ", "_").replace(":", "")
        return f"runtime_export_{safe}.zip"
