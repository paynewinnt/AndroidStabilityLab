from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Iterable

from stability.domain import IssueRecord, IssueType, SeverityLevel

# ---------------------------------------------------------------------------
# Module-level regex patterns used by the detector registry
# ---------------------------------------------------------------------------
_RE_ANR = re.compile(
    r"\bANR\b",
    re.IGNORECASE,
)
_RE_JAVA_CRASH = re.compile(
    r"(?P<exception>[A-Za-z0-9_.]+(?:Exception|Error))(?:\s*:.*?(?P<cause>[A-Za-z0-9_.]+(?:Exception|Error)))?",
)
_RE_NATIVE_CRASH = re.compile(
    r"(?:signal\s+(?P<signal>\d+)|(?:SIGSEGV|SIGABRT|SIGFPE|SIGILL|SIGBUS))",
)
_RE_NULL_RECOVERY = re.compile(
    r"(?:null|NULL|Null)(?:\s*pointer)?(?:\s*recovery)",
    re.IGNORECASE,
)
_RE_TOMBSTONE = re.compile(
    r"tombstone",
    re.IGNORECASE,
)
_RE_LOW_MEMORY = re.compile(
    r"(?:low\s+memory|lowmem|low-memory|LMK|kill\s+(?P<process>[A-Za-z0-9._:]+)|(?P<detail>mm[a-z_]*\s*:\s*\d+\s*[Mm]B))",
    re.IGNORECASE,
)
_RE_WATCHDOG = re.compile(
    r"WATCHDOG KILLING SYSTEM PROCESS",
    re.IGNORECASE,
)
_RE_SCROLL_JANK = re.compile(
    r"(?:scroll\s+jank|janky\s+scroll|dropped\s+frame)",
    re.IGNORECASE,
)
_RE_STRICT_MODE = re.compile(
    r"StrictMode\s+(?P<violation>[A-Za-z]+)",
)
_RE_PROCESS_EXIT = re.compile(
    r"(?:"
    r"am_proc_died"
    r"|WIN DEATH"
    r"|Process\s+[A-Za-z0-9._:]+\s+has died"
    r"|Killing\s+\d+:[A-Za-z0-9._:]+"
    r")(?P<reason>.*)",
    re.IGNORECASE,
)


@dataclass
class _DetectorEntry:
    name: str
    pattern: re.Pattern
    issue_type: IssueType
    severity: SeverityLevel
    # Custom evidence key builder -- receives the Match object, returns str or None
    evidence_key: Callable[[re.Match], str | None] = lambda m: m.lastgroup or (m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0))


class MonkeyIssueDetector:
    """Detect V1 issue records from scenario execution results."""

    CRASH_PATTERNS = (
        re.compile(r"FATAL EXCEPTION", re.IGNORECASE),
        re.compile(r"\bCRASH\b", re.IGNORECASE),
    )
    REBOOT_PATTERNS = (
        re.compile(r"\breboot(?:ing|ed)?\b", re.IGNORECASE),
        re.compile(r"BOOT_COMPLETED", re.IGNORECASE),
        re.compile(r"sys\.boot_completed", re.IGNORECASE),
        re.compile(r"dev\.bootcomplete", re.IGNORECASE),
    )
    ANR_PATTERNS = (
        re.compile(r"\bANR\b", re.IGNORECASE),
        re.compile(r"Application Not Responding", re.IGNORECASE),
    )
    NATIVE_CRASH_PATTERNS = (
        re.compile(r"native crash", re.IGNORECASE),
        re.compile(r"tombstone", re.IGNORECASE),
    )
    SYSTEM_SERVER_CRASH_PATTERNS = (
        re.compile(r"FATAL EXCEPTION:[^\n]*(?:\n.*?){0,4}\bProcess:\s*system_server\b", re.IGNORECASE),
        re.compile(r"\bsystem_server\b[^\n]*(?:crash|crashed|fatal exception|died|has died)\b", re.IGNORECASE),
        re.compile(r"\b(?:crash|crashed|fatal exception|died|has died)\b[^\n]*\bsystem_server\b", re.IGNORECASE),
    )
    WATCHDOG_PATTERNS = (
        re.compile(r"\bwatchdog\b", re.IGNORECASE),
        re.compile(r"WATCHDOG KILLING SYSTEM PROCESS", re.IGNORECASE),
        re.compile(r"Blocked in handler on .*?android\.server", re.IGNORECASE),
    )
    FREEZE_PATTERNS = (
        re.compile(r"\bfreeze(?:d|s|ing)?\b", re.IGNORECASE),
        re.compile(r"\bscreen\s+(?:no|not)\s+refresh(?:ing|ed)?\b", re.IGNORECASE),
        re.compile(r"\bno\s+screen\s+refresh\b", re.IGNORECASE),
        re.compile(r"\binput\s+(?:no|not)\s+response\b", re.IGNORECASE),
        re.compile(r"\binput\s+unresponsive\b", re.IGNORECASE),
        re.compile(r"\btouch\s+(?:no|not)\s+response\b", re.IGNORECASE),
        re.compile(r"\bui\s+(?:hang|hung|stuck|freeze(?:d|s|ing)?)\b", re.IGNORECASE),
    )
    BLACK_SCREEN_PATTERNS = (
        re.compile(r"\bblack\s+screen\b", re.IGNORECASE),
        re.compile(r"\bscreen\s+(?:is\s+)?black\b", re.IGNORECASE),
        re.compile(r"\bsurface\s+black\b", re.IGNORECASE),
        re.compile(r"\bblack\s+surface\b", re.IGNORECASE),
        re.compile(r"\bdisplay\s+(?:is\s+)?black\b", re.IGNORECASE),
        re.compile(r"\bblank\s+screen\b", re.IGNORECASE),
        re.compile(r"\bno\s+visible\s+(?:frame|content)\b", re.IGNORECASE),
    )
    JAVA_EXCEPTION_PATTERNS = (
        re.compile(r"SecurityException", re.IGNORECASE),
        re.compile(r"IllegalStateException", re.IGNORECASE),
        re.compile(r"RuntimeException", re.IGNORECASE),
    )
    PROCESS_PATTERN = re.compile(r"Process:\s*([A-Za-z0-9._:]+)", re.IGNORECASE)
    PROCESS_EXIT_PATTERNS = (
        re.compile(r"am_proc_died", re.IGNORECASE),
        re.compile(r"WIN DEATH", re.IGNORECASE),
        re.compile(r"Process\s+[A-Za-z0-9._:]+(?:\s+\(pid\s+\d+\))?.*?\bhas died\b", re.IGNORECASE),
        re.compile(r"Killing\s+\d+:[A-Za-z0-9._:]+", re.IGNORECASE),
    )
    PROCESS_EXIT_PROCESS_PATTERNS = (
        re.compile(
            r"Process\s+([A-Za-z0-9._:]+)(?:\s+\(pid\s+(\d+)\))?.*?\bhas died\b",
            re.IGNORECASE,
        ),
        re.compile(r"Killing\s+(\d+):([A-Za-z0-9._:]+)", re.IGNORECASE),
        re.compile(r"am_proc_died.*?\b(\d+)\b\s+([A-Za-z0-9._:]+)\b", re.IGNORECASE),
    )
    PID_PATTERN = re.compile(r"(?:PID|pid):\s*(\d+)", re.IGNORECASE)

    _DETECTORS: ClassVar[list[_DetectorEntry]] = [
        # ANR
        _DetectorEntry("ANR", _RE_ANR, IssueType.ANR, SeverityLevel.HIGH,
                       evidence_key=lambda m: m.group(0) if m else "unknown"),
        # Java Crash
        _DetectorEntry("JavaCrash", _RE_JAVA_CRASH, IssueType.JAVA_CRASH, SeverityLevel.HIGH,
                       evidence_key=lambda m: (m.group("exception") or m.group("cause") or "unknown").strip()),
        # Native Crash
        _DetectorEntry("NativeCrash", _RE_NATIVE_CRASH, IssueType.NATIVE_CRASH, SeverityLevel.HIGH,
                       evidence_key=lambda m: (m.group("signal") or "unknown").strip()),
        # Null Recovery
        _DetectorEntry("NullRecovery", _RE_NULL_RECOVERY, IssueType.NATIVE_CRASH, SeverityLevel.LOW,
                       evidence_key=lambda m: (m.group("signal") or "unknown").strip()),
        # Tombstone
        _DetectorEntry("Tombstone", _RE_TOMBSTONE, IssueType.NATIVE_CRASH, SeverityLevel.HIGH),
        # Low Memory
        _DetectorEntry("LowMemory", _RE_LOW_MEMORY, IssueType.LOW_MEMORY, SeverityLevel.MEDIUM,
                       evidence_key=lambda m: (m.group("process") or m.group("detail") or "unknown").strip()),
        # Watchdog
        _DetectorEntry("Watchdog", _RE_WATCHDOG, IssueType.WATCHDOG, SeverityLevel.HIGH),
        # Scroll Jank
        _DetectorEntry("ScrollJank", _RE_SCROLL_JANK, IssueType.SCROLL_JANK, SeverityLevel.MEDIUM),
        # Strict Mode
        _DetectorEntry("StrictMode", _RE_STRICT_MODE, IssueType.STRICT_MODE, SeverityLevel.LOW,
                       evidence_key=lambda m: (m.group("violation") or "unknown").strip()),
        # Custom Crash (ProcessExit)
        _DetectorEntry("ProcessExit", _RE_PROCESS_EXIT, IssueType.PROCESS_EXIT, SeverityLevel.HIGH,
                       evidence_key=lambda m: (m.group("reason") or "unknown").strip()),
    ]

    def detect(self, task, run, instance, scenario_result) -> list[IssueRecord]:
        """Translate scenario outcomes into normalized V1 issue records."""
        if scenario_result is None:
            return []

        issues: list[IssueRecord] = []
        metadata = getattr(scenario_result, "metadata", {}) or {}
        note_text = str(getattr(scenario_result, "note", "") or "")
        highlights_text = "\n".join(str(item) for item in (getattr(scenario_result, "highlights", ()) or ()) if item)
        detection_sources = self._collect_detection_sources(note_text, highlights_text, metadata)
        combined_output = self._join_detection_sources(detection_sources)

        exit_reason = str(getattr(scenario_result, "exit_reason", "") or "")
        if exit_reason == "device_offline":
            issues.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.DEVICE_OFFLINE,
                    severity=SeverityLevel.HIGH,
                    title="执行期间设备离线",
                    summary=str(getattr(scenario_result, "note", "") or "Monkey 执行设备离线。"),
                    raw_key=f"device_offline:{getattr(instance, 'device_id', '')}",
                    metadata=metadata,
                )
            )
        if exit_reason == "timeout":
            issues.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=(
                        IssueType.STARTUP_TIMEOUT
                        if metadata.get("template_type") == "cold_start_loop"
                        else IssueType.EXECUTION_TIMEOUT
                    ),
                    severity=SeverityLevel.HIGH,
                    title=(
                        "冷启动超时"
                        if metadata.get("template_type") == "cold_start_loop"
                        else "Monkey 执行超时"
                    ),
                    summary=str(
                        getattr(scenario_result, "note", "") or (
                            "冷启动循环执行超时。"
                            if metadata.get("template_type") == "cold_start_loop"
                            else "Monkey 执行超时。"
                        )
                    ),
                    raw_key=(
                        f"startup_timeout:{getattr(task.target_app, 'package_name', '')}:{metadata.get('startup_failure_loop', '')}"
                        if metadata.get("template_type") == "cold_start_loop"
                        else f"execution_timeout:{getattr(instance, 'instance_id', '')}"
                    ),
                    metadata=metadata,
                )
            )
        issues.extend(self._detect_startup_issues(task, run, instance, metadata))

        issues.extend(self._detect_from_output(combined_output.splitlines()))
        return self._deduplicate(issues)

    def _detect_startup_issues(self, task, run, instance, metadata: dict) -> list[IssueRecord]:
        """Map cold-start loop failures into explicit startup issues."""
        if metadata.get("template_type") != "cold_start_loop" or not metadata.get("startup_failure"):
            return []
        failure_kind = str(metadata.get("startup_failure_kind", "") or "")
        if failure_kind == "startup_timeout":
            return []

        loop_index = metadata.get("startup_failure_loop")
        loop_text = f"第 {loop_index} 轮" if loop_index is not None else "某一轮"
        reason = str(metadata.get("startup_failure_reason", "") or "冷启动命令返回失败。")
        return [
            self._build_issue(
                task,
                run,
                instance,
                issue_type=IssueType.STARTUP_FAILURE,
                severity=SeverityLevel.HIGH,
                title="冷启动失败",
                summary=f"{loop_text} 启动失败：{reason}",
                raw_key=f"startup_failure:{getattr(task.target_app, 'package_name', '')}:{loop_index}",
                metadata=metadata,
                process_name=str(metadata.get("process_name", "") or ""),
            )
        ]

    def _detect_from_output(
        self,
        lines: list[str],
        *,
        previous_state: dict[str, Any] | None = None,
    ) -> list[IssueRecord]:
        issues: list[IssueRecord] = []
        rebooting = bool(previous_state and previous_state.get("rebooting"))
        for line_no, line in enumerate(lines, start=1):
            # Reboot guard
            if not rebooting and self._is_reboot_line(line):
                rebooting = True
                continue
            if rebooting:
                if self._is_boot_completed_line(line):
                    rebooting = False
                continue

            for entry in self._DETECTORS:
                m = entry.pattern.search(line)
                if not m:
                    continue

                # Crash guard: skip system_server crashes
                if entry.name in ("JavaCrash", "NativeCrash"):
                    if self._is_system_server_crash(m, line):
                        continue

                # Build evidence
                evidence_raw = entry.evidence_key(m)
                evidence = self._format_raw_key(evidence_raw) if evidence_raw else "unknown"

                issue = self._create_issue(
                    issue_type=entry.issue_type,
                    severity=entry.severity,
                    summary=self._format_issue_summary(entry.name, evidence),
                    evidence_key=evidence,
                    line_no=line_no,
                    raw=line.rstrip("\n"),
                )
                issues.append(issue)

        return issues

    @staticmethod
    def _format_raw_key(raw_match: str) -> str:
        """Normalize a raw log line into a stable evidence key."""
        raw_match = raw_match.strip()
        # Truncate at 200 chars
        if len(raw_match) > 200:
            raw_match = raw_match[:200]
        return raw_match

    @staticmethod
    def _is_reboot_line(line: str) -> bool:
        """Check if a log line indicates a device reboot."""
        return any(p.search(line) for p in [
            re.compile(r"\breboot(?:ing|ed)?\b", re.IGNORECASE),
        ])

    @staticmethod
    def _is_boot_completed_line(line: str) -> bool:
        """Check if a log line indicates boot completed."""
        return any(p.search(line) for p in [
            re.compile(r"BOOT_COMPLETED", re.IGNORECASE),
            re.compile(r"sys\.boot_completed", re.IGNORECASE),
            re.compile(r"dev\.bootcomplete", re.IGNORECASE),
        ])

    @staticmethod
    def _is_system_server_crash(match: re.Match, line: str) -> bool:
        """Check if a crash match targets system_server."""
        return "system_server" in line

    @staticmethod
    def _create_issue(
        *,
        issue_type: IssueType,
        severity: SeverityLevel,
        summary: str,
        evidence_key: str,
        line_no: int,
        raw: str,
    ) -> IssueRecord:
        """Create a line-level issue record from a detector match."""
        return IssueRecord(
            instance_id="",
            task_run_id="",
            device_id="",
            issue_type=issue_type,
            issue_title=f"Detected {issue_type.value}",
            severity=severity,
            source="monkey",
            raw_key=evidence_key,
            summary=summary,
            metadata={"evidence": raw, "line_no": line_no},
        )

    @staticmethod
    def _format_issue_summary(name: str, evidence: str) -> str:
        """Format a short summary string for a detected issue."""
        return f"{name}: {evidence}"

    @staticmethod
    def _collect_detection_sources(note_text: str, highlights_text: str, metadata: dict) -> list[dict[str, str]]:
        """Collect available textual signals while retaining their original source."""
        metadata_text_keys = (
            "stdout",
            "stdout_tail",
            "stderr",
            "stderr_tail",
            "logcat",
            "logcat_tail",
            "summary",
            "screen_summary",
            "failure_summary",
            "monitor_summary",
            "artifact_summary",
            "artifacts_summary",
            "screenshot_summary",
            "surfaceflinger",
            "surfaceflinger_summary",
            "dumpsys_surfaceflinger",
            "input_summary",
            "frame_refresh_summary",
        )
        sources: list[dict[str, str]] = []
        if note_text:
            sources.append({"source": "note", "text": note_text})
        if highlights_text:
            sources.append({"source": "highlights", "text": highlights_text})
        for key in metadata_text_keys:
            value = metadata.get(key)
            if value:
                sources.append({"source": key, "text": MonkeyIssueDetector._stringify_detection_value(value)})
        for key, value in metadata.items():
            if key in metadata_text_keys or not value:
                continue
            text = MonkeyIssueDetector._stringify_detection_value(value)
            if text:
                sources.append({"source": str(key), "text": text})
        return sources

    @staticmethod
    def _join_detection_sources(sources: Iterable[dict[str, str]]) -> str:
        """Join source text for existing whole-output detectors."""
        return "\n".join(str(item.get("text", "") or "") for item in sources if item.get("text")).strip()

    @staticmethod
    def _collect_detection_text(note_text: str, highlights_text: str, metadata: dict) -> str:
        """Collect currently available textual signals for issue detection."""
        return MonkeyIssueDetector._join_detection_sources(
            MonkeyIssueDetector._collect_detection_sources(note_text, highlights_text, metadata)
        )

    @staticmethod
    def _stringify_detection_value(value) -> str:
        """Convert metadata values into readable detector text."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return " ".join(
                MonkeyIssueDetector._stringify_detection_value(item)
                for item in value.values()
                if item
            )
        if isinstance(value, (list, tuple, set)):
            return " ".join(MonkeyIssueDetector._stringify_detection_value(item) for item in value if item)
        return str(value)

    @staticmethod
    def _build_issue(
        task,
        run,
        instance,
        *,
        issue_type: IssueType,
        severity: SeverityLevel,
        title: str,
        summary: str,
        raw_key: str,
        metadata: dict,
        process_name: str = "",
        pid: int | None = None,
    ) -> IssueRecord:
        """Create one normalized issue record bound to the current task run and instance."""
        package_name = getattr(task.target_app, "package_name", "") if getattr(task, "target_app", None) else ""
        return IssueRecord(
            instance_id=getattr(instance, "instance_id", "") or "",
            task_run_id=getattr(run, "run_id", "") or "",
            device_id=getattr(instance, "device_id", "") or "",
            issue_type=issue_type,
            issue_title=title,
            severity=severity,
            source="monkey",
            raw_key=raw_key,
            process_name=process_name,
            package_name=package_name,
            pid=pid,
            summary=summary,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _matches_any(patterns: Iterable[re.Pattern[str]], text: str) -> bool:
        """Return whether any detection pattern matches the provided text."""
        return any(pattern.search(text) for pattern in patterns)

    @staticmethod
    def _first_matching_evidence(patterns: Iterable[re.Pattern[str]], text: str, *, limit: int = 200) -> str:
        """Return a stable evidence snippet around the first matched keyword."""
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            start = max(match.start() - 80, 0)
            end = min(match.end() + 120, len(text))
            return " ".join(text[start:end].split())[:limit].strip()
        return ""

    @staticmethod
    def _metadata_with_evidence(metadata: dict, evidence) -> dict:
        """Attach detector evidence without mutating scenario metadata."""
        enriched = dict(metadata or {})
        if not evidence:
            return enriched
        if isinstance(evidence, dict):
            enriched.update(evidence)
            fragments = evidence.get("matched_fragments")
            if fragments and "evidence" not in enriched:
                enriched["evidence"] = str(fragments[0])
            return enriched
        enriched["evidence"] = str(evidence)
        return enriched

    @classmethod
    def _structured_evidence(
        cls,
        patterns: Iterable[re.Pattern[str]],
        sources: Iterable[dict[str, str]],
        *,
        fallback_text: str,
    ) -> dict:
        """Build structured evidence from the text channels currently available to the detector."""
        pattern_tuple = tuple(patterns)
        signals: list[dict[str, str]] = []
        matched_sources: list[str] = []
        matched_fragments: list[str] = []
        seen_fragments: set[str] = set()

        for item in sources:
            source = str(item.get("source", "") or "text")
            text = str(item.get("text", "") or "")
            if not text:
                continue
            for pattern in pattern_tuple:
                match = pattern.search(text)
                if not match:
                    continue
                fragment = cls._snippet_around_match(text, match)
                signal_source = cls._classify_evidence_source(source, match.group(0), fallback_fragment=fragment)
                signal = {
                    "source": signal_source,
                    "raw_source": source,
                    "pattern": pattern.pattern,
                    "fragment": fragment,
                }
                signals.append(signal)
                if signal_source not in matched_sources:
                    matched_sources.append(signal_source)
                if fragment and fragment not in seen_fragments:
                    seen_fragments.add(fragment)
                    matched_fragments.append(fragment)

        if not signals:
            fallback = cls._first_matching_evidence(pattern_tuple, fallback_text)
            if fallback:
                signal_source = cls._classify_evidence_source("text", fallback)
                signals.append(
                    {
                        "source": signal_source,
                        "raw_source": "combined_output",
                        "pattern": "",
                        "fragment": fallback,
                    }
                )
                matched_sources.append(signal_source)
                matched_fragments.append(fallback)

        evidence_level = cls._evidence_level(matched_sources, len(matched_fragments))
        return {
            "evidence": matched_fragments[0] if matched_fragments else "",
            "evidence_signals": signals,
            "evidence_level": evidence_level,
            "confirmation_level": evidence_level,
            "matched_sources": matched_sources,
            "matched_fragments": matched_fragments,
        }

    @staticmethod
    def _snippet_around_match(text: str, match: re.Match[str], *, limit: int = 200) -> str:
        """Return a compact snippet around a regex match."""
        start = max(match.start() - 80, 0)
        end = min(match.end() + 120, len(text))
        return " ".join(text[start:end].split())[:limit].strip()

    @staticmethod
    def _classify_evidence_source(raw_source: str, fragment: str, *, fallback_fragment: str = "") -> str:
        """Map raw text channels and keywords into stable evidence source classes."""
        raw_source_text = raw_source.lower()
        fragment_text = fragment.lower()
        fallback_text = fallback_fragment.lower()
        if "screenshot" in raw_source_text or "screenshot" in fragment_text or "screen capture" in fragment_text:
            return "screenshot"
        if "surfaceflinger" in raw_source_text or "surfaceflinger" in fragment_text:
            return "surfaceflinger"
        if "input" in raw_source_text or "input" in fragment_text or "touch" in fragment_text:
            return "input"
        if "refresh" in raw_source_text or "refresh" in fragment_text or "frame" in fragment_text or "render" in fragment_text:
            return "frame_refresh"
        if "surface" in fragment_text or "display" in fragment_text:
            return "surfaceflinger"
        if "screenshot" in fallback_text or "screen capture" in fallback_text:
            return "screenshot"
        if "surfaceflinger" in fallback_text or "surface" in fallback_text or "display" in fallback_text:
            return "surfaceflinger"
        if "input" in fallback_text or "touch" in fallback_text:
            return "input"
        if "refresh" in fallback_text or "frame" in fallback_text or "render" in fallback_text:
            return "frame_refresh"
        return "text"

    @staticmethod
    def _evidence_level(matched_sources: list[str], fragment_count: int) -> str:
        """Classify confidence from source diversity without requiring real device captures."""
        distinct_sources = {source for source in matched_sources if source}
        if len(distinct_sources) >= 2:
            return "strong"
        if fragment_count >= 2:
            return "medium"
        if distinct_sources:
            return "weak"
        return "none"

    @staticmethod
    def _summarize_output(text: str, label: str, limit: int = 500) -> str:
        """Extract a short output snippet suitable for storing as issue summary."""
        normalized = " ".join(text.split())
        snippet = normalized[:limit].strip()
        return f"{label}: {snippet}" if snippet else label

    @classmethod
    def _extract_issue_context(cls, text: str, metadata: dict) -> dict[str, str | int | None]:
        """Extract process and pid hints to support more targeted evidence capture."""
        process_name = ""
        pid: int | None = None

        process_match = cls.PROCESS_PATTERN.search(text)
        if process_match:
            process_name = process_match.group(1).strip()

        pid_match = cls.PID_PATTERN.search(text)
        if pid_match:
            try:
                pid = int(pid_match.group(1))
            except ValueError:
                pid = None

        if not process_name:
            raw_process = metadata.get("process_name")
            if isinstance(raw_process, str):
                process_name = raw_process.strip()

        if pid is None:
            raw_pid = metadata.get("pid")
            if isinstance(raw_pid, int):
                pid = raw_pid
            elif isinstance(raw_pid, str) and raw_pid.isdigit():
                pid = int(raw_pid)

        return {
            "process_name": process_name,
            "pid": pid,
        }

    @classmethod
    def _extract_process_exit_context(
        cls,
        text: str,
        metadata: dict,
        *,
        fallback: dict[str, str | int | None] | None = None,
    ) -> dict[str, str | int | None]:
        """Extract process exit specific hints when the generic crash context is absent."""
        process_name = ""
        pid: int | None = None

        for pattern in cls.PROCESS_EXIT_PROCESS_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            groups = tuple(group.strip() for group in match.groups() if isinstance(group, str) and group.strip())
            if len(groups) >= 2 and groups[0].isdigit():
                try:
                    pid = int(groups[0])
                except ValueError:
                    pid = None
                process_name = groups[1]
            else:
                if groups:
                    process_name = groups[0]
                if len(groups) >= 2:
                    try:
                        pid = int(groups[1])
                    except ValueError:
                        pid = None
            if process_name or pid is not None:
                break

        if not process_name and fallback is not None:
            process_name = str(fallback.get("process_name") or "")
        if pid is None and fallback is not None:
            fallback_pid = fallback.get("pid")
            if isinstance(fallback_pid, int):
                pid = fallback_pid

        if not process_name:
            raw_process = metadata.get("process_name") or metadata.get("package_name")
            if isinstance(raw_process, str):
                process_name = raw_process.strip()

        if pid is None:
            raw_pid = metadata.get("pid")
            if isinstance(raw_pid, int):
                pid = raw_pid
            elif isinstance(raw_pid, str) and raw_pid.isdigit():
                pid = int(raw_pid)

        return {
            "process_name": process_name,
            "pid": pid,
        }

    @staticmethod
    def _deduplicate(issues: list[IssueRecord]) -> list[IssueRecord]:
        """Deduplicate issues by raw key before persisting them."""
        seen: set[str] = set()
        unique: list[IssueRecord] = []
        for issue in issues:
            dedupe_key = issue.deduplication_key()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique.append(issue)
        return unique
