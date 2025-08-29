from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.app import (
    DeviceRecordNotFound,
    RunRecordNotFound,
    SnapshotRecordNotFound,
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedTaskRecordNotFound,
)
from stability.app.task_service import TaskRecordNotFound
from stability.domain import (
    AggregatedIssue,
    AnalysisSnapshotRecord,
    AnalysisSnapshotSummary,
    ComparedMetricTrend,
    ComparedIssue,
    ComparisonResult,
    IssueEventReference,
    IssueAttribution,
    MetricTrendSummary,
    PerformanceTrendComparison,
    RegressedIssue,
    RegressedMetric,
    RegressionResult,
    SamplingConfig,
    TaskDefinition,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.cli.handlers.web import handle_serve_web as _web_handle_serve_web
from stability.cli.payloads_admission import _admission_case_payload, _admission_report_payload_from_bundle
from stability.web import serve_web_portal

# Split from stability.cli.task_create; analysis.py owns this command/payload group.

# Split from stability/cli/handlers/analysis.py.

def _handle_list_admission_cases(args: argparse.Namespace) -> int:
    """List persisted admission cases with one stable contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "admission_case_service", None)
    if service is None:
        raise SystemExit("Admission case service is unavailable.")
    if hasattr(service, "list_admission_case_payloads"):
        cases_payload = service.list_admission_case_payloads(limit=args.limit)
    elif hasattr(service, "list_cases"):
        items = service.list_cases(limit=args.limit)
        cases_payload = {
            "contract_version": "admission_case_list.v1",
            "count": len(items),
            "entries": [_admission_case_payload(item) for item in items],
        }
    else:
        raise SystemExit("Admission case list contract is unavailable.")
    payload = {
        "storage_mode": "persistent",
        "admission_cases": cases_payload,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_admission_case(args: argparse.Namespace) -> int:
    """Show one admission case with the stable case contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "admission_case_service", None)
    if service is None:
        raise SystemExit("Admission case service is unavailable.")
    try:
        if hasattr(service, "export_admission_case_payload"):
            case_payload = service.export_admission_case_payload(baseline_key=args.baseline_key.strip())
        elif hasattr(service, "get_case"):
            case_payload = _admission_case_payload(service.get_case(args.baseline_key.strip()))
        else:
            raise SystemExit("Admission case contract is unavailable.")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "admission_case": case_payload,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_admission_report(args: argparse.Namespace) -> int:
    """Show the export-ready report derived from the AdmissionCase contract."""
    bundle = create_v1_persistent_bootstrap()
    report = _admission_report_payload_from_bundle(bundle, args.baseline_key.strip())
    payload = {
        "storage_mode": "persistent",
        "formal_report": report,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
