from __future__ import annotations

from typing import Any, Mapping, Sequence

from stability.app import AttributionService
from stability.domain import AggregatedIssue, IssueEventReference, IssueFingerprint, IssueType, SeverityLevel

from tests.test_analysis_service import build_service_fixture

import unittest


class AttributionServiceTest(unittest.TestCase):
    def test_attribute_issue_group_infers_app_logic_for_target_process_crash(self) -> None:
        analysis_service = build_service_fixture()
        attribution_service = AttributionService(analysis_service=analysis_service)
        top_issue = analysis_service.list_top_issues(issue_type="crash")[0]
        issue_group = analysis_service.get_issue_group(top_issue.fingerprint.value)

        result = attribution_service.attribute_issue_group(issue_group)

        self.assertEqual(result.direction, "app_logic")
        self.assertEqual(result.confidence, "high")
        self.assertEqual(result.matched_rule_id, "app_target_process_crash")
        self.assertIn("app_target_process_crash", result.matched_rule_ids)
        self.assertGreater(result.confidence_score, 0.0)

    def test_attribute_issue_group_falls_back_to_unknown_when_no_rule_matches(self) -> None:
        analysis_service = build_service_fixture()
        attribution_service = AttributionService(analysis_service=analysis_service)
        top_issue = analysis_service.list_top_issues(issue_type="device_offline")[0]
        issue_group = analysis_service.get_issue_group(top_issue.fingerprint.value)

        result = attribution_service.attribute_issue_group(issue_group)

        self.assertEqual(result.direction, "unknown")
        self.assertEqual(result.confidence, "low")
        self.assertFalse(result.hits)

    def test_attribute_issue_group_infers_framework_service_from_watchdog_signal(self) -> None:
        attribution_service = AttributionService(analysis_service=build_service_fixture())
        issue_group = AggregatedIssue(
            fingerprint=IssueFingerprint(
                value="ifp_framework",
                rule_version="v1",
                components={"issue_type": "reboot"},
            ),
            issue_type=IssueType.REBOOT,
            title="system_server watchdog reboot",
            severity=SeverityLevel.CRITICAL,
            first_seen_at=None,
            last_seen_at=None,
            occurrence_count=1,
            affected_run_count=1,
            affected_device_count=1,
            affected_scenario_count=1,
            affected_version_count=1,
            affected_packages=("com.example.app",),
            affected_devices=("device-1",),
            affected_scenarios=("monkey",),
            affected_versions=("1.0.0(100)",),
            sample_event_ids=("issue-1",),
            sample_events=(
                IssueEventReference(
                    event_id="issue-1",
                    run_id="run-1",
                    task_id="task-1",
                    task_name="Task 1",
                    instance_id="instance-1",
                    device_id="device-1",
                    package_name="com.example.app",
                    scenario_name="monkey",
                    issue_type=IssueType.REBOOT,
                    severity=SeverityLevel.CRITICAL,
                    summary="system_server watchdog detected before reboot",
                    artifact_paths=(),
                    metadata={"process_name": "system_server"},
                ),
            ),
            score=0.0,
            score_breakdown={},
        )

        result = attribution_service.attribute_issue_group(issue_group)

        self.assertEqual(result.direction, "framework_system_service")
        self.assertEqual(result.confidence, "high")
        self.assertEqual(result.matched_rule_id, "framework_system_service")

    def test_attribute_issue_group_infers_framework_service_from_system_server_crash_type(self) -> None:
        attribution_service = AttributionService(analysis_service=build_service_fixture())
        issue_group = _make_issue_group(
            issue_type=IssueType.SYSTEM_SERVER_CRASH,
            title="检测到 system_server Crash",
            summary="system_server died with fatal exception",
            metadata={"process_name": "system_server"},
            process_name="system_server",
        )

        result = attribution_service.attribute_issue_group(issue_group)

        self.assertEqual(result.direction, "framework_system_service")
        self.assertEqual(result.matched_rule_id, "framework_system_service")
        self.assertIn("system_server_crash", [hit.keyword for hit in result.hits])
        self.assertTrue(result.recommended_next_steps)

    def test_attribute_issue_group_infers_graphics_display_for_freeze_and_black_screen(self) -> None:
        attribution_service = AttributionService(analysis_service=build_service_fixture())

        for issue_type, title, summary in (
            (IssueType.FREEZE, "检测到画面冻结或无响应", "screen freeze and input stuck"),
            (IssueType.BLACK_SCREEN, "检测到黑屏", "black screen after surface update"),
        ):
            result = attribution_service.attribute_issue_group(
                _make_issue_group(
                    issue_type=issue_type,
                    title=title,
                    summary=summary,
                    metadata={"process_name": "surfaceflinger"},
                    process_name="surfaceflinger",
                )
            )

            self.assertEqual(result.direction, "graphics_display")
            self.assertEqual(result.matched_rule_id, "graphics_display")
            self.assertIn(issue_type.value, [hit.keyword for hit in result.hits])

    def test_structured_evidence_boosts_confidence_and_generates_summary(self) -> None:
        attribution_service = AttributionService(analysis_service=build_service_fixture())
        weak_result = attribution_service.attribute_issue_group(
            _make_issue_group(
                issue_type=IssueType.FREEZE,
                title="检测到画面冻结或无响应",
                summary="observed by detector",
                metadata={},
            )
        )
        strong_result = attribution_service.attribute_issue_group(
            _make_issue_group(
                issue_type=IssueType.FREEZE,
                title="检测到画面冻结或无响应",
                summary="freeze observed",
                metadata={
                    "evidence_signals": [
                        {
                            "source": "screenshot",
                            "raw_source": "screenshot_1",
                            "pattern": "freeze",
                            "fragment": "screenshot shows frozen frame on display",
                        },
                        {
                            "source": "surfaceflinger",
                            "raw_source": "dumpsys_surfaceflinger",
                            "pattern": "frame",
                            "fragment": "SurfaceFlinger reports no frame refresh",
                        },
                    ],
                    "confirmation_level": "strong",
                    "matched_sources": ["screenshot", "surfaceflinger"],
                    "matched_fragments": [
                        "screenshot shows frozen frame on display",
                        "SurfaceFlinger reports no frame refresh",
                    ],
                },
            )
        )

        self.assertGreater(strong_result.score, weak_result.score)
        self.assertGreater(strong_result.confidence_score, weak_result.confidence_score)
        self.assertTrue(strong_result.evidence_summary)
        self.assertIn("graphics_display", strong_result.matched_rule_ids)


def _make_issue_group(
    *,
    issue_type: IssueType,
    title: str,
    summary: str,
    metadata: Mapping[str, Any],
    process_name: str = "",
    artifact_paths: Sequence[str] = (),
) -> AggregatedIssue:
    return AggregatedIssue(
        fingerprint=IssueFingerprint(
            value=f"ifp_{issue_type.value}",
            rule_version="v1",
            components={"issue_type": issue_type.value},
        ),
        issue_type=issue_type,
        title=title,
        severity=SeverityLevel.HIGH,
        first_seen_at=None,
        last_seen_at=None,
        occurrence_count=1,
        affected_run_count=1,
        affected_device_count=1,
        affected_scenario_count=1,
        affected_version_count=1,
        affected_packages=("com.example.app",),
        affected_devices=("device-1",),
        affected_scenarios=("monkey",),
        affected_versions=("1.0.0(100)",),
        sample_event_ids=("issue-1",),
        sample_events=(
            IssueEventReference(
                event_id="issue-1",
                run_id="run-1",
                task_id="task-1",
                task_name="Task 1",
                instance_id="instance-1",
                device_id="device-1",
                package_name="com.example.app",
                scenario_name="monkey",
                issue_type=issue_type,
                severity=SeverityLevel.HIGH,
                summary=summary,
                artifact_paths=artifact_paths,
                metadata={"process_name": process_name, **dict(metadata)},
            ),
        ),
        score=0.0,
        score_breakdown={},
    )


if __name__ == "__main__":
    unittest.main()
