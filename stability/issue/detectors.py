from __future__ import annotations

import re
from typing import Iterable

from stability.domain import IssueRecord, IssueType, SeverityLevel


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

        issues.extend(self._detect_from_output(task, run, instance, combined_output, metadata, detection_sources))
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
        task,
        run,
        instance,
        combined_output: str,
        metadata: dict,
        detection_sources: list[dict[str, str]] | None = None,
    ) -> list[IssueRecord]:
        """Match known crash/anr patterns from Monkey stdout and stderr."""
        if not combined_output:
            return []

        detections: list[IssueRecord] = []
        detection_sources = detection_sources or self._collect_detection_sources("", "", metadata)
        context = self._extract_issue_context(combined_output, metadata)
        reboot_detected = bool(metadata.get("reboot_detected")) or self._matches_any(self.REBOOT_PATTERNS, combined_output)
        if reboot_detected:
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.REBOOT,
                    severity=SeverityLevel.CRITICAL,
                    title="检测到设备重启",
                    summary=self._summarize_output(combined_output, "Reboot"),
                    raw_key=f"reboot:{getattr(instance, 'device_id', '')}",
                    metadata=metadata,
                )
            )
        if self._matches_any(self.WATCHDOG_PATTERNS, combined_output):
            evidence = self._structured_evidence(self.WATCHDOG_PATTERNS, detection_sources, fallback_text=combined_output)
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.WATCHDOG,
                    severity=SeverityLevel.CRITICAL,
                    title="检测到 Watchdog",
                    summary=self._summarize_output(combined_output, "Watchdog"),
                    raw_key=f"watchdog:{getattr(instance, 'device_id', '')}",
                    metadata=self._metadata_with_evidence(metadata, evidence),
                    process_name="system_server" if "system_server" in combined_output else context["process_name"],
                    pid=context["pid"],
                )
            )
        system_server_crash_detected = self._matches_any(self.SYSTEM_SERVER_CRASH_PATTERNS, combined_output)
        if system_server_crash_detected:
            evidence = self._structured_evidence(
                self.SYSTEM_SERVER_CRASH_PATTERNS,
                detection_sources,
                fallback_text=combined_output,
            )
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.SYSTEM_SERVER_CRASH,
                    severity=SeverityLevel.CRITICAL,
                    title="检测到 system_server Crash",
                    summary=self._summarize_output(combined_output, "System Server Crash"),
                    raw_key=f"system_server_crash:{getattr(instance, 'device_id', '')}",
                    metadata=self._metadata_with_evidence(metadata, evidence),
                    process_name="system_server",
                    pid=context["pid"],
                )
            )
        if self._matches_any(self.ANR_PATTERNS, combined_output):
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.ANR,
                    severity=SeverityLevel.HIGH,
                    title="检测到 ANR",
                    summary=self._summarize_output(combined_output, "ANR"),
                    raw_key=f"anr:{getattr(task.target_app, 'package_name', '')}",
                    metadata=metadata,
                    process_name=context["process_name"],
                    pid=context["pid"],
                )
            )
        if self._matches_any(self.NATIVE_CRASH_PATTERNS, combined_output):
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.NATIVE_CRASH,
                    severity=SeverityLevel.CRITICAL,
                    title="检测到 Native Crash",
                    summary=self._summarize_output(combined_output, "Native Crash"),
                    raw_key=f"native_crash:{getattr(task.target_app, 'package_name', '')}",
                    metadata=metadata,
                    process_name=context["process_name"],
                    pid=context["pid"],
                )
            )
        if self._matches_any(self.JAVA_EXCEPTION_PATTERNS, combined_output):
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.JAVA_EXCEPTION,
                    severity=SeverityLevel.MEDIUM,
                    title="检测到 Java Exception",
                    summary=self._summarize_output(combined_output, "Java Exception"),
                    raw_key=f"java_exception:{getattr(task.target_app, 'package_name', '')}",
                    metadata=metadata,
                    process_name=context["process_name"],
                    pid=context["pid"],
                )
            )
        if self._matches_any(self.CRASH_PATTERNS, combined_output) and not system_server_crash_detected:
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.CRASH,
                    severity=SeverityLevel.CRITICAL,
                    title="检测到 Crash",
                    summary=self._summarize_output(combined_output, "Crash"),
                    raw_key=f"crash:{getattr(task.target_app, 'package_name', '')}",
                    metadata=metadata,
                    process_name=context["process_name"],
                    pid=context["pid"],
                )
            )
        if self._matches_any(self.BLACK_SCREEN_PATTERNS, combined_output):
            evidence = self._structured_evidence(
                self.BLACK_SCREEN_PATTERNS,
                detection_sources,
                fallback_text=combined_output,
            )
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.BLACK_SCREEN,
                    severity=SeverityLevel.HIGH,
                    title="检测到黑屏",
                    summary=self._summarize_output(combined_output, "Black Screen"),
                    raw_key=f"black_screen:{getattr(task.target_app, 'package_name', '')}:{getattr(instance, 'device_id', '')}",
                    metadata=self._metadata_with_evidence(metadata, evidence),
                    process_name=context["process_name"],
                    pid=context["pid"],
                )
            )
        if self._matches_any(self.FREEZE_PATTERNS, combined_output):
            evidence = self._structured_evidence(
                self.FREEZE_PATTERNS,
                detection_sources,
                fallback_text=combined_output,
            )
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.FREEZE,
                    severity=SeverityLevel.HIGH,
                    title="检测到画面冻结或无响应",
                    summary=self._summarize_output(combined_output, "Freeze"),
                    raw_key=f"freeze:{getattr(task.target_app, 'package_name', '')}:{getattr(instance, 'device_id', '')}",
                    metadata=self._metadata_with_evidence(metadata, evidence),
                    process_name=context["process_name"],
                    pid=context["pid"],
                )
            )
        crash_like_issue_types = {
            IssueType.REBOOT,
            IssueType.WATCHDOG,
            IssueType.SYSTEM_SERVER_CRASH,
            IssueType.ANR,
            IssueType.NATIVE_CRASH,
            IssueType.JAVA_EXCEPTION,
            IssueType.CRASH,
        }
        process_exit_detected = bool(metadata.get("process_exit_detected")) or self._matches_any(
            self.PROCESS_EXIT_PATTERNS,
            combined_output,
        )
        if process_exit_detected and not any(issue.issue_type in crash_like_issue_types for issue in detections):
            process_context = self._extract_process_exit_context(combined_output, metadata, fallback=context)
            process_name = str(process_context["process_name"] or "")
            raw_key_target = process_name or getattr(task.target_app, "package_name", "")
            detections.append(
                self._build_issue(
                    task,
                    run,
                    instance,
                    issue_type=IssueType.PROCESS_EXIT,
                    severity=SeverityLevel.MEDIUM,
                    title="检测到进程退出",
                    summary=self._summarize_output(combined_output, "Process Exit"),
                    raw_key=f"process_exit:{raw_key_target}",
                    metadata=metadata,
                    process_name=process_name,
                    pid=process_context["pid"],
                )
            )
        return detections

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
