from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.application import (
    CiAdmissionSyncCommand,
    ChannelWorkerCommand,
    DeliverOutboxCommand,
    ReplayDeadLettersCommand,
    RunOutboxWorkerCommand,
    build_im_acceptance_summary,
    deliver_integration_outbox,
    replay_integration_dead_letters,
    run_defect_sync_worker,
    run_feishu_notify_worker,
    run_im_notification_worker,
    run_integration_outbox_worker,
    run_release_sync_worker,
    sync_ci_admission_decisions,
)
from stability.app import (
    AggregatedIssueNotFound,
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
from stability.cli.utils import _expand_multi_value
from stability.web import serve_web_portal

# Split from stability.cli.task_create; integration_commands.py owns this command/payload group.

# Split from stability/cli/handlers/integration_commands.py.

def _handle_deliver_integration_outbox(args: argparse.Namespace) -> int:
    """Deliver one batch of pending outbox events to one registered webhook."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    try:
        payload = deliver_integration_outbox(
            service,
            DeliverOutboxCommand(
                webhook_name=args.webhook_name.strip(),
                event_types=tuple(_expand_multi_value(args.event_types)),
                limit=args.limit,
            ),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_integration_outbox_worker(args: argparse.Namespace) -> int:
    """Run a local delivery worker loop across one or more registered webhooks."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    try:
        payload = run_integration_outbox_worker(
            service,
            RunOutboxWorkerCommand(
                webhook_names=tuple(_expand_multi_value(args.webhook_names)),
                event_types=tuple(_expand_multi_value(args.event_types)),
                limit_per_webhook=int(args.limit_per_webhook),
                rounds=max(int(args.rounds), 1),
                interval_seconds=max(int(args.interval_seconds), 0),
                stop_when_idle=bool(args.stop_when_idle),
                daemon=bool(args.daemon),
                max_runtime_seconds=max(int(args.max_runtime_seconds), 0),
                chain_name="integration_outbox",
                worker_mode="delivery_worker_loop",
            ),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_ci_admission_sync_worker(args: argparse.Namespace) -> int:
    """Run the stable CI admission callback worker on the case-based contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    try:
        payload = run_integration_outbox_worker(
            service,
            RunOutboxWorkerCommand(
                webhook_names=tuple(_expand_multi_value(args.webhook_names)),
                event_types=("admission_case.updated",),
                limit_per_webhook=max(int(args.limit_per_webhook), 0),
                rounds=max(int(args.max_rounds), 1) if int(args.max_rounds) > 0 else 1,
                interval_seconds=max(int(args.interval_seconds), 0),
                stop_when_idle=bool(args.stop_when_idle),
                daemon=True,
                max_runtime_seconds=max(int(args.max_runtime_seconds), 0),
                chain_name="ci_admission_callback",
                worker_mode="ci_admission_callback_daemon",
            ),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload["mode"] = "ci_admission_sync_worker"
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_im_notify_worker(args: argparse.Namespace) -> int:
    """Run the IM notification worker on the stable IM event set."""
    bundle = create_v1_persistent_bootstrap()
    payload = run_im_notification_worker(
        getattr(bundle, "integration_outbox_service", None),
        ChannelWorkerCommand(
            webhook_names=tuple(_expand_multi_value(args.webhook_names)),
            limit_per_webhook=max(int(args.limit_per_webhook), 0),
            interval_seconds=max(int(args.interval_seconds), 0),
            max_rounds=max(int(args.max_rounds), 0),
            max_runtime_seconds=max(int(args.max_runtime_seconds), 0),
            stop_when_idle=bool(args.stop_when_idle),
            daemon=bool(args.daemon),
        ),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_feishu_notify_worker(args: argparse.Namespace) -> int:
    """Run the Feishu custom bot notification worker on the stable IM event set."""
    bundle = create_v1_persistent_bootstrap()
    payload = run_feishu_notify_worker(
        getattr(bundle, "integration_outbox_service", None),
        ChannelWorkerCommand(
            webhook_names=tuple(_expand_multi_value(args.webhook_names)),
            limit_per_webhook=max(int(args.limit_per_webhook), 0),
            interval_seconds=max(int(args.interval_seconds), 0),
            max_rounds=max(int(args.max_rounds), 0),
            max_runtime_seconds=max(int(args.max_runtime_seconds), 0),
            stop_when_idle=bool(args.stop_when_idle),
            daemon=bool(args.daemon),
        ),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_im_acceptance_summary(args: argparse.Namespace) -> int:
    """Show an operator-oriented IM/Feishu acceptance summary for real 2h/24h runs."""
    bundle = create_v1_persistent_bootstrap()
    selected_webhooks = tuple(_expand_multi_value(getattr(args, "webhook_names", ()) or ()))
    payload = {
        "storage_mode": "persistent",
        "mode": "im_acceptance_summary",
        "acceptance_summary": build_im_acceptance_summary(
            getattr(bundle, "integration_outbox_service", None),
            channel=str(getattr(args, "channel", "all") or "all"),
            selected_webhooks=selected_webhooks,
            limit=max(int(getattr(args, "limit", 0) or 0), 0),
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_defect_sync_worker(args: argparse.Namespace) -> int:
    """Run the defect sync worker on the stable defect event set."""
    bundle = create_v1_persistent_bootstrap()
    payload = run_defect_sync_worker(
        getattr(bundle, "integration_outbox_service", None),
        ChannelWorkerCommand(
            webhook_names=tuple(_expand_multi_value(args.webhook_names)),
            limit_per_webhook=max(int(args.limit_per_webhook), 0),
            interval_seconds=max(int(args.interval_seconds), 0),
            max_rounds=max(int(args.max_rounds), 0),
            max_runtime_seconds=max(int(args.max_runtime_seconds), 0),
            stop_when_idle=bool(args.stop_when_idle),
            daemon=bool(args.daemon),
        ),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_release_sync_worker(args: argparse.Namespace) -> int:
    """Run the release submission worker on the stable release event set."""
    bundle = create_v1_persistent_bootstrap()
    payload = run_release_sync_worker(
        getattr(bundle, "integration_outbox_service", None),
        ChannelWorkerCommand(
            webhook_names=tuple(_expand_multi_value(args.webhook_names)),
            limit_per_webhook=max(int(args.limit_per_webhook), 0),
            interval_seconds=max(int(args.interval_seconds), 0),
            max_rounds=max(int(args.max_rounds), 0),
            max_runtime_seconds=max(int(args.max_runtime_seconds), 0),
            stop_when_idle=bool(args.stop_when_idle),
            daemon=bool(args.daemon),
        ),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_replay_integration_dead_letters(args: argparse.Namespace) -> int:
    """Preview or replay dead-letter events back into pending delivery."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    try:
        payload = replay_integration_dead_letters(
            service,
            ReplayDeadLettersCommand(
                event_ids=tuple(_expand_multi_value(args.event_ids)),
                event_types=tuple(_expand_multi_value(args.event_types)),
                limit=max(int(args.limit), 0),
                execute=bool(args.execute),
                replayed_by=args.replayed_by.strip() or "cli",
            ),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_sync_ci_admission_decisions(args: argparse.Namespace) -> int:
    """Query pending admission decision events and optionally push a single CI sync batch."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    try:
        payload = sync_ci_admission_decisions(
            service,
            CiAdmissionSyncCommand(
                webhook_name=args.webhook_name.strip(),
                event_types=tuple(_expand_multi_value(args.event_types)),
                query_limit=max(int(args.query_limit), 0),
                limit=int(args.limit),
                dry_run=bool(args.dry_run),
                ci_endpoint=str(args.ci_endpoint or "").strip(),
                created_by=args.created_by.strip(),
            ),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
