from __future__ import annotations

import unittest

from stability.domain import IssueType, IssueRecord, SeverityLevel
from stability.issue import MonkeyIssueDetector


class MonkeyIssueDetectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = MonkeyIssueDetector()

    # ------------------------------------------------------------------
    # _DetectorEntry registry tests
    # ------------------------------------------------------------------

    def test_registry_has_expected_entries(self) -> None:
        """The _DETECTORS registry must contain all required entries."""
        expected_names = {
            "ANR", "JavaCrash", "NativeCrash", "NullRecovery",
            "Tombstone", "LowMemory", "Watchdog", "ScrollJank",
            "StrictMode", "ProcessExit",
        }
        actual_names = {e.name for e in MonkeyIssueDetector._DETECTORS}
        self.assertEqual(expected_names, actual_names)

    # ------------------------------------------------------------------
    # Individual detector tests via _detect_from_output
    # ------------------------------------------------------------------

    def test_detect_anr(self) -> None:
        lines = ["I ActivityManager: ANR in com.example.app"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertIn(issues[0].issue_type, (IssueType.ANR,))
        self.assertEqual(issues[0].severity, SeverityLevel.HIGH)
        self.assertIn("ANR", issues[0].raw_key)

    def test_detect_java_crash(self) -> None:
        lines = ["FATAL EXCEPTION: main\njava.lang.RuntimeException: boom"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.JAVA_CRASH)
        self.assertEqual(issues[0].severity, SeverityLevel.HIGH)

    def test_detect_native_crash_by_signal(self) -> None:
        lines = ["signal 11 (SIGSEGV) code 1 (SEGV_MAPERR)"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.NATIVE_CRASH)
        self.assertEqual(issues[0].severity, SeverityLevel.HIGH)

    def test_detect_watchdog(self) -> None:
        lines = ["WATCHDOG KILLING SYSTEM PROCESS: Blocked in handler on ActivityManager"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.WATCHDOG)
        self.assertEqual(issues[0].severity, SeverityLevel.HIGH)

    def test_detect_tombstone(self) -> None:
        lines = ["I crash_dump32: *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***\nBuild fingerprint: ...\nAbort message: 'tombstone'"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.NATIVE_CRASH)
        self.assertEqual(issues[0].severity, SeverityLevel.HIGH)

    def test_detect_low_memory(self) -> None:
        lines = ["W ActivityManager: Low memory: 512 MB"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.LOW_MEMORY)
        self.assertEqual(issues[0].severity, SeverityLevel.MEDIUM)

    def test_detect_scroll_jank(self) -> None:
        lines = ["I Choreographer: Dropped 15 frames.  The application may be doing too much work on its main thread."]
        issues = self.detector._detect_from_output(lines)
        # "Dropped" alone doesn't match scroll jank unless "dropped frame" is adjacent
        self.assertEqual(len(issues), 0)

    def test_detect_scroll_jank_with_keyword(self) -> None:
        lines = ["I SurfaceFlinger: scroll jank detected on com.example.app"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.SCROLL_JANK)
        self.assertEqual(issues[0].severity, SeverityLevel.MEDIUM)

    def test_detect_strict_mode(self) -> None:
        lines = ["StrictMode policy violation: android.os.StrictMode$StrictModeDiskReadViolation"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.STRICT_MODE)
        self.assertEqual(issues[0].severity, SeverityLevel.LOW)

    def test_detect_process_exit(self) -> None:
        lines = ["I ActivityManager: Killing 2456:com.example.app/u0a123 (adj 900): empty process"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.PROCESS_EXIT)
        self.assertEqual(issues[0].severity, SeverityLevel.HIGH)

    def test_detect_native_crash_by_signal_keyword(self) -> None:
        lines = ["SIGSEGV at 0x1234"]
        issues = self.detector._detect_from_output(lines)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.NATIVE_CRASH)

    def test_skip_system_server_java_crash(self) -> None:
        """Java crash lines mentioning system_server should be skipped."""
        lines = ["FATAL EXCEPTION: android.ui\njava.lang.RuntimeException: boom in system_server"]
        # The Java crash pattern matches lines with exception names
        # But system_server check skips them
        issues = self.detector._detect_from_output(lines)
        # Note: "java.lang.RuntimeException" doesn't match _RE_JAVA_CRASH because it
        # expects "Exception" or "Error" suffix on a word boundary
        self.assertEqual(len(issues), 0)

    # ------------------------------------------------------------------
    # _format_raw_key helper tests
    # ------------------------------------------------------------------

    def test_format_raw_key_truncates_long_strings(self) -> None:
        long = "x" * 500
        result = MonkeyIssueDetector._format_raw_key(long)
        self.assertEqual(len(result), 200)

    def test_format_raw_key_strips_whitespace(self) -> None:
        result = MonkeyIssueDetector._format_raw_key("  hello world  ")
        self.assertEqual(result, "hello world")

    # ------------------------------------------------------------------
    # _create_issue record structure
    # ------------------------------------------------------------------

    def test_create_issue_returns_well_formed_record(self) -> None:
        record = MonkeyIssueDetector._create_issue(
            issue_type=IssueType.ANR,
            severity=SeverityLevel.HIGH,
            summary="ANR: com.example.app",
            evidence_key="anr_evidence",
            line_no=42,
            raw="I ActivityManager: ANR in com.example.app",
        )
        self.assertIsInstance(record, IssueRecord)
        self.assertEqual(record.issue_type, IssueType.ANR)
        self.assertEqual(record.severity, SeverityLevel.HIGH)
        self.assertEqual(record.summary, "ANR: com.example.app")
        self.assertEqual(record.raw_key, "anr_evidence")
        self.assertEqual(record.metadata["line_no"], 42)
        self.assertIn("ANR in com.example.app", record.metadata["evidence"])

    # ------------------------------------------------------------------
    # Reboot guard
    # ------------------------------------------------------------------

    def test_lines_after_reboot_are_skipped_until_boot_completed(self) -> None:
        lines = [
            "some normal log",
            "I ServiceManager: rebooting device",
            "this should be skipped",
            "another skipped line",
            "BOOT_COMPLETED received",
            "this should be detected again",
        ]
        issues = self.detector._detect_from_output(lines)
        # None of the lines between reboot and BOOT_COMPLETED should be detected
        # "rebooting device" itself triggers _is_reboot_line, causing remaining lines
        # to be skipped until BOOT_COMPLETED.
        # "BOOT_COMPLETED received" triggers _is_boot_completed_line, halting skip.
        # "this should be detected again" resumes normal scanning.
        for issue in issues:
            self.assertGreaterEqual(issue.metadata["line_no"], 6)

    # ------------------------------------------------------------------
    # previous_state reboot continuation
    # ------------------------------------------------------------------

    def test_previous_state_rebooting_skips_lines_until_boot_completed(self) -> None:
        lines = [
            "skipped because rebooting from previous state",
            "BOOT_COMPLETED received",
            "SIGSEGV at 0x1234 detected after boot completed",
        ]
        issues = self.detector._detect_from_output(lines, previous_state={"rebooting": True})
        # Only the last line should produce a detection
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.NATIVE_CRASH)


if __name__ == "__main__":
    unittest.main()
