from __future__ import annotations

import argparse

from stability.domain import TaskRunStatus, TaskTemplateType
from stability.cli.parser_utils import _add_monitoring_backend_override_argument


def register_integration_commands(subparsers: argparse._SubParsersAction, handler_module: object) -> None:
    list_admission_cases_parser = subparsers.add_parser(
        "list-admission-cases",
        help="List persisted admission cases with the stable case contract.",
    )
    list_admission_cases_parser.add_argument("--limit", type=int, default=20, help="Maximum cases to return.")
    list_admission_cases_parser.set_defaults(handler=handler_module._handle_list_admission_cases)

    show_admission_case_parser = subparsers.add_parser(
        "show-admission-case",
        help="Show one admission case by baseline key.",
    )
    show_admission_case_parser.add_argument("--baseline-key", required=True, help="Stable admission baseline key.")
    show_admission_case_parser.set_defaults(handler=handler_module._handle_show_admission_case)

    show_admission_report_parser = subparsers.add_parser(
        "show-admission-report",
        help="Show the formal report JSON exported from the AdmissionCase contract.",
    )
    show_admission_report_parser.add_argument("--baseline-key", required=True, help="Stable admission baseline key.")
    show_admission_report_parser.set_defaults(handler=handler_module._handle_show_admission_report)

    serve_web_parser = subparsers.add_parser(
        "serve-web",
        help="Start the minimal V3 Web main entry backed by the persistent service bundle.",
    )
    serve_web_parser.add_argument("--host", default=None, help="Host interface to bind. Default: ConfigProvider web.host or 127.0.0.1")
    serve_web_parser.add_argument("--port", type=int, default=None, help="TCP port to bind. Default: ConfigProvider web.port or 8030")
    serve_web_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR.")
    serve_web_parser.add_argument(
        "--allow-remote-access",
        action="store_true",
        help="Explicitly allow binding to a non-local host such as 0.0.0.0. The current portal is still a local ops console, not a production-ready team platform.",
    )
    serve_web_parser.add_argument(
        "--portal-mode",
        choices=("local_ops_console", "team_entry"),
        default=None,
        help="Portal deployment profile. Use team_entry when this portal should become the shared team entry instead of a local-only ops console.",
    )
    serve_web_parser.add_argument(
        "--public-base-url",
        default=None,
        help="Optional external base URL used in platform pages and API manifests. Required when --portal-mode team_entry is used.",
    )
    serve_web_parser.add_argument(
        "--deployment-label",
        default=None,
        help="Optional display label for this deployment, for example 'lab-room-a' or 'team-stability-entry'.",
    )
    serve_web_parser.add_argument(
        "--sync-devices-on-start",
        action="store_true",
        help="Refresh the persistent device registry once before the server starts.",
    )
    serve_web_parser.set_defaults(handler=handler_module._handle_serve_web)

    register_integration_webhook_parser = subparsers.add_parser(
        "register-integration-webhook",
        help="Register one local outbound webhook target for the integration outbox.",
    )
    register_integration_webhook_parser.add_argument("--name", required=True, help="Webhook display name.")
    register_integration_webhook_parser.add_argument("--url", required=True, help="Webhook callback URL.")
    register_integration_webhook_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Subscribed event type. Repeat this flag or pass a comma-separated list. Defaults to all events when omitted.",
    )
    register_integration_webhook_parser.add_argument("--created-by", default="cli", help="Creator identity.")
    register_integration_webhook_parser.add_argument(
        "--secret-hint",
        default="",
        help="Optional hint describing how the receiver verifies signatures or stores secrets.",
    )
    register_integration_webhook_parser.add_argument(
        "--signing-secret",
        default="",
        help="Optional local signing secret used for HMAC webhook signatures.",
    )
    register_integration_webhook_parser.add_argument(
        "--signature-key-id",
        default="v1",
        help="Current signature key id advertised to receivers.",
    )
    register_integration_webhook_parser.add_argument(
        "--accepted-signature-key-id",
        dest="accepted_signature_key_ids",
        action="append",
        default=[],
        help="Additional accepted key ids kept during secret rotation.",
    )
    register_integration_webhook_parser.add_argument(
        "--failure-policy",
        default="retryable_http",
        help="Delivery failure policy label for operator review.",
    )
    register_integration_webhook_parser.add_argument(
        "--delivery-channel",
        default="generic",
        help="Webhook chain label such as ci_callback or im_notify.",
    )
    register_integration_webhook_parser.set_defaults(handler=handler_module._handle_register_integration_webhook)

    register_im_webhook_parser = subparsers.add_parser(
        "register-im-webhook",
        help="Register one IM notification webhook on the stable asl.im_notify.v1 contract.",
    )
    register_im_webhook_parser.add_argument("--name", required=True, help="Webhook display name.")
    register_im_webhook_parser.add_argument("--url", required=True, help="IM robot or inbound callback URL.")
    register_im_webhook_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional IM event type filter. Repeat this flag or pass a comma-separated list. Defaults to the stable IM event set.",
    )
    register_im_webhook_parser.add_argument("--created-by", default="cli", help="Creator identity.")
    register_im_webhook_parser.add_argument(
        "--secret-hint",
        default="",
        help="Optional hint describing how the IM receiver verifies signatures or stores secrets.",
    )
    register_im_webhook_parser.add_argument(
        "--signing-secret",
        default="",
        help="Optional local signing secret used for HMAC webhook signatures.",
    )
    register_im_webhook_parser.add_argument(
        "--signature-key-id",
        default="v1",
        help="Current signature key id advertised to receivers.",
    )
    register_im_webhook_parser.add_argument(
        "--accepted-signature-key-id",
        dest="accepted_signature_key_ids",
        action="append",
        default=[],
        help="Additional accepted key ids kept during secret rotation.",
    )
    register_im_webhook_parser.add_argument(
        "--failure-policy",
        default="retryable_http",
        help="Delivery failure policy label for operator review.",
    )
    register_im_webhook_parser.set_defaults(handler=handler_module._handle_register_im_webhook)

    register_feishu_webhook_parser = subparsers.add_parser(
        "register-feishu-webhook",
        help="Register one Feishu custom bot webhook using the Feishu robot body signature.",
    )
    register_feishu_webhook_parser.add_argument("--name", required=True, help="Webhook display name.")
    register_feishu_webhook_parser.add_argument("--url", required=True, help="Feishu custom bot webhook URL.")
    register_feishu_webhook_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional Feishu event type filter. Repeat this flag or pass a comma-separated list. Defaults to the stable IM event set.",
    )
    register_feishu_webhook_parser.add_argument("--created-by", default="cli", help="Creator identity.")
    register_feishu_webhook_parser.add_argument(
        "--secret-hint",
        default="",
        help="Optional hint describing where the Feishu robot secret is stored.",
    )
    register_feishu_webhook_parser.add_argument(
        "--signing-secret",
        default="",
        help="Feishu custom bot signing secret used only for timestamp/sign in the JSON body.",
    )
    register_feishu_webhook_parser.add_argument(
        "--signature-key-id",
        default="feishu-bot",
        help="Local bookkeeping key id; Feishu verifies the body sign, not this ASL header key.",
    )
    register_feishu_webhook_parser.add_argument(
        "--accepted-signature-key-id",
        dest="accepted_signature_key_ids",
        action="append",
        default=[],
        help="Additional local bookkeeping key ids kept during secret rotation.",
    )
    register_feishu_webhook_parser.add_argument(
        "--failure-policy",
        default="retryable_http",
        help="Delivery failure policy label for operator review.",
    )
    register_feishu_webhook_parser.set_defaults(handler=handler_module._handle_register_feishu_webhook)

    register_defect_webhook_parser = subparsers.add_parser(
        "register-defect-webhook",
        help="Register one defect sync webhook on the stable asl.defect_sync.v1 contract.",
    )
    register_defect_webhook_parser.add_argument("--name", required=True, help="Webhook display name.")
    register_defect_webhook_parser.add_argument("--url", required=True, help="Defect system callback URL.")
    register_defect_webhook_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional defect event type filter. Repeat this flag or pass a comma-separated list. Defaults to the stable defect event set.",
    )
    register_defect_webhook_parser.add_argument("--created-by", default="cli", help="Creator identity.")
    register_defect_webhook_parser.add_argument(
        "--secret-hint",
        default="",
        help="Optional hint describing how the defect receiver verifies signatures or stores secrets.",
    )
    register_defect_webhook_parser.add_argument(
        "--signing-secret",
        default="",
        help="Optional local signing secret used for HMAC webhook signatures.",
    )
    register_defect_webhook_parser.add_argument(
        "--signature-key-id",
        default="v1",
        help="Current signature key id advertised to receivers.",
    )
    register_defect_webhook_parser.add_argument(
        "--accepted-signature-key-id",
        dest="accepted_signature_key_ids",
        action="append",
        default=[],
        help="Additional accepted key ids kept during secret rotation.",
    )
    register_defect_webhook_parser.add_argument(
        "--failure-policy",
        default="retryable_http",
        help="Delivery failure policy label for operator review.",
    )
    register_defect_webhook_parser.set_defaults(handler=handler_module._handle_register_defect_webhook)

    create_release_submission_parser = subparsers.add_parser(
        "create-release-submission",
        help="Receive one release-submission context, create its task/run, and optionally execute it immediately.",
    )
    create_release_submission_parser.add_argument("--source-platform", required=True, help="Submission platform key.")
    create_release_submission_parser.add_argument("--source-request-id", required=True, help="External submission ticket or request id.")
    create_release_submission_parser.add_argument("--package-name", required=True, help="Target application package name.")
    create_release_submission_parser.add_argument("--version-name", default="", help="Optional version name from the release platform.")
    create_release_submission_parser.add_argument("--version-code", default="", help="Optional version code from the release platform.")
    create_release_submission_parser.add_argument("--build-id", default="", help="Optional build id or artifact revision.")
    create_release_submission_parser.add_argument("--release-channel", default="", help="Optional release channel such as beta/gray/store.")
    create_release_submission_parser.add_argument("--owner-team", default="", help="Optional owner team key from the release platform.")
    create_release_submission_parser.add_argument("--submission-title", default="", help="Optional explicit submission display title.")
    create_release_submission_parser.add_argument(
        "--template-type",
        default="cold_start_loop",
        help="Task template type used for the release-triggered task.",
    )
    create_release_submission_parser.add_argument(
        "--device",
        dest="devices",
        action="append",
        default=[],
        help="Optional device id filter. Repeat this flag or pass a comma-separated list.",
    )
    create_release_submission_parser.add_argument(
        "--metric",
        dest="metrics",
        action="append",
        default=[],
        help="Optional monitoring metric. Repeat this flag or pass a comma-separated list.",
    )
    create_release_submission_parser.add_argument("--sampling-interval", type=int, default=5, help="Sampling interval seconds.")
    create_release_submission_parser.add_argument("--task-params", default="{}", help="JSON object task_params payload.")
    create_release_submission_parser.add_argument("--metadata", default="{}", help="JSON object metadata payload.")
    create_release_submission_parser.add_argument("--created-by", default="cli", help="Creator identity.")
    create_release_submission_parser.add_argument(
        "--monitoring-backend",
        default="",
        help="Optional monitoring backend override such as solox or perfetto.",
    )
    create_release_submission_parser.add_argument(
        "--skip-execute",
        action="store_true",
        help="Only create task/run without executing immediately.",
    )
    create_release_submission_parser.add_argument("--max-concurrency", type=int, default=1, help="execute-run max concurrency.")
    create_release_submission_parser.add_argument("--retry-count", type=int, default=0, help="execute-run retry count.")
    create_release_submission_parser.add_argument(
        "--skip-device-sync",
        action="store_true",
        help="Skip the pre-submission device registry sync in persistent mode.",
    )
    create_release_submission_parser.set_defaults(handler=handler_module._handle_create_release_submission)

    list_release_submissions_parser = subparsers.add_parser(
        "list-release-submissions",
        help="List persisted release-submission records with task/run/admission summaries.",
    )
    list_release_submissions_parser.add_argument("--limit", type=int, default=20, help="Maximum submissions to return.")
    list_release_submissions_parser.set_defaults(handler=handler_module._handle_list_release_submissions)

    show_release_submission_parser = subparsers.add_parser(
        "show-release-submission",
        help="Show one persisted release-submission record in detail.",
    )
    show_release_submission_parser.add_argument("--submission-id", required=True, help="Release submission id.")
    show_release_submission_parser.set_defaults(handler=handler_module._handle_show_release_submission)

    sync_release_submission_admission_parser = subparsers.add_parser(
        "sync-release-submission-admission",
        help="Sync one release submission with the current AdmissionCase decision.",
    )
    sync_release_submission_admission_parser.add_argument("--submission-id", required=True, help="Release submission id.")
    sync_release_submission_admission_parser.add_argument("--baseline-key", required=True, help="Admission baseline key.")
    sync_release_submission_admission_parser.add_argument("--synced-by", default="cli", help="Operator identity.")
    sync_release_submission_admission_parser.set_defaults(handler=handler_module._handle_sync_release_submission_admission)

    register_release_webhook_parser = subparsers.add_parser(
        "register-release-webhook",
        help="Register one release platform webhook on the stable asl.release_submission.v1 contract.",
    )
    register_release_webhook_parser.add_argument("--name", required=True, help="Webhook display name.")
    register_release_webhook_parser.add_argument("--url", required=True, help="Release platform callback URL.")
    register_release_webhook_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional release event type filter. Repeat this flag or pass a comma-separated list.",
    )
    register_release_webhook_parser.add_argument("--created-by", default="cli", help="Creator identity.")
    register_release_webhook_parser.add_argument("--secret-hint", default="", help="Optional receiver secret hint.")
    register_release_webhook_parser.add_argument("--signing-secret", default="", help="Optional HMAC signing secret.")
    register_release_webhook_parser.add_argument("--signature-key-id", default="v1", help="Current signature key id.")
    register_release_webhook_parser.add_argument(
        "--accepted-signature-key-id",
        dest="accepted_signature_key_ids",
        action="append",
        default=[],
        help="Additional accepted key ids kept during secret rotation.",
    )
    register_release_webhook_parser.add_argument(
        "--failure-policy",
        default="retryable_http",
        help="Delivery failure policy label for operator review.",
    )
    register_release_webhook_parser.set_defaults(handler=handler_module._handle_register_release_webhook)

    run_release_sync_worker_parser = subparsers.add_parser(
        "run-release-sync-worker",
        help="Run the stable release-submission worker on release submission create/execution/admission events.",
    )
    run_release_sync_worker_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional release webhook name filter. Defaults to all registered release webhooks.",
    )
    run_release_sync_worker_parser.add_argument(
        "--limit-per-webhook",
        type=int,
        default=20,
        help="Maximum events to attempt for one webhook in one round.",
    )
    run_release_sync_worker_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Sleep interval between release worker rounds.",
    )
    run_release_sync_worker_parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Optional max rounds for the worker loop. 0 means use runtime/idle limits only.",
    )
    run_release_sync_worker_parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=0,
        help="Optional max runtime before returning. 0 means no explicit runtime cap.",
    )
    run_release_sync_worker_parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Stop early once release delivery becomes idle with no remaining backlog.",
    )
    run_release_sync_worker_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a scheduled local daemon loop instead of a bounded one-shot worker loop.",
    )
    run_release_sync_worker_parser.set_defaults(handler=handler_module._handle_run_release_sync_worker)

    deliver_integration_outbox_parser = subparsers.add_parser(
        "deliver-integration-outbox",
        help="Deliver pending outbox events to one registered webhook target.",
    )
    deliver_integration_outbox_parser.add_argument(
        "--webhook-name",
        required=True,
        help="Registered webhook name. Keep one command focused on one real outbound chain.",
    )
    deliver_integration_outbox_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional event type filter for this delivery round.",
    )
    deliver_integration_outbox_parser.add_argument("--limit", type=int, default=20, help="Maximum events to attempt.")
    deliver_integration_outbox_parser.set_defaults(handler=handler_module._handle_deliver_integration_outbox)

    run_integration_outbox_worker_parser = subparsers.add_parser(
        "run-integration-outbox-worker",
        help="Run one local outbox delivery worker loop across one or more registered webhooks.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional webhook name filter. Repeat or pass a comma-separated list; defaults to all registered webhooks.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional event type filter for each worker round.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--limit-per-webhook",
        type=int,
        default=20,
        help="Maximum events to attempt for one webhook in one round.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of worker rounds to execute before returning. Default: 1.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=0,
        help="Optional sleep interval between worker rounds. Default: 0.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Stop early once one round attempts no deliveries and leaves no retry/pending backlog.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a scheduled local daemon loop instead of a bounded one-shot worker loop.",
    )
    run_integration_outbox_worker_parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=0,
        help="Optional daemon max runtime before returning. 0 means no explicit runtime cap.",
    )
    run_integration_outbox_worker_parser.set_defaults(handler=handler_module._handle_run_integration_outbox_worker)

    run_ci_admission_sync_worker_parser = subparsers.add_parser(
        "run-ci-admission-sync-worker",
        help="Run the long-lived CI admission callback worker on admission_case.updated events.",
    )
    run_ci_admission_sync_worker_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional CI webhook name filter. Defaults to all registered CI callback webhooks.",
    )
    run_ci_admission_sync_worker_parser.add_argument(
        "--limit-per-webhook",
        type=int,
        default=20,
        help="Maximum events to attempt for one webhook in one round.",
    )
    run_ci_admission_sync_worker_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Sleep interval between CI worker rounds.",
    )
    run_ci_admission_sync_worker_parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Optional max rounds for the daemon loop. 0 means use runtime/idle limits only.",
    )
    run_ci_admission_sync_worker_parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=0,
        help="Optional max runtime before returning. 0 means no explicit runtime cap.",
    )
    run_ci_admission_sync_worker_parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Stop early once CI delivery becomes idle with no remaining backlog.",
    )
    run_ci_admission_sync_worker_parser.set_defaults(handler=handler_module._handle_run_ci_admission_sync_worker)

    run_im_notify_worker_parser = subparsers.add_parser(
        "run-im-notify-worker",
        help="Run the stable IM notification worker on the supported collaboration and admission events.",
    )
    run_im_notify_worker_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional IM webhook name filter. Defaults to all registered IM notification webhooks.",
    )
    run_im_notify_worker_parser.add_argument(
        "--limit-per-webhook",
        type=int,
        default=20,
        help="Maximum events to attempt for one webhook in one round.",
    )
    run_im_notify_worker_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Sleep interval between IM worker rounds.",
    )
    run_im_notify_worker_parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Optional max rounds for the worker loop. 0 means use runtime/idle limits only.",
    )
    run_im_notify_worker_parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=0,
        help="Optional max runtime before returning. 0 means no explicit runtime cap.",
    )
    run_im_notify_worker_parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Stop early once IM delivery becomes idle with no remaining backlog.",
    )
    run_im_notify_worker_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a scheduled local daemon loop instead of a bounded one-shot worker loop.",
    )
    run_im_notify_worker_parser.set_defaults(handler=handler_module._handle_run_im_notify_worker)

    run_feishu_notify_worker_parser = subparsers.add_parser(
        "run-feishu-notify-worker",
        help="Run the Feishu custom bot notification worker on the supported IM events.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional Feishu webhook name filter. Defaults to all registered Feishu bot webhooks.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--limit-per-webhook",
        type=int,
        default=20,
        help="Maximum events to attempt for one webhook in one round.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Sleep interval between Feishu worker rounds.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Optional max rounds for the worker loop. 0 means use runtime/idle limits only.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=0,
        help="Optional max runtime before returning. 0 means no explicit runtime cap.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Stop early once Feishu delivery becomes idle with no remaining backlog.",
    )
    run_feishu_notify_worker_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a scheduled local daemon loop instead of a bounded one-shot worker loop.",
    )
    run_feishu_notify_worker_parser.set_defaults(handler=handler_module._handle_run_feishu_notify_worker)

    show_im_acceptance_summary_parser = subparsers.add_parser(
        "show-im-acceptance-summary",
        help="Show operator-facing IM/Feishu 2h/24h acceptance delivery counters and checklist.",
    )
    show_im_acceptance_summary_parser.add_argument(
        "--channel",
        choices=("all", "im_notify", "feishu_bot"),
        default="all",
        help="Acceptance channel scope. Use feishu_bot for real Feishu custom bot validation.",
    )
    show_im_acceptance_summary_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional IM/Feishu webhook name filter. Repeat or pass a comma-separated list.",
    )
    show_im_acceptance_summary_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum outbox events to scan. 0 means all events supported by the service.",
    )
    show_im_acceptance_summary_parser.set_defaults(handler=handler_module._handle_show_im_acceptance_summary)

    run_defect_sync_worker_parser = subparsers.add_parser(
        "run-defect-sync-worker",
        help="Run the stable defect sync worker on issue defect create/link/status events.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--webhook-name",
        dest="webhook_names",
        action="append",
        default=[],
        help="Optional defect webhook name filter. Defaults to all registered defect webhooks.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--limit-per-webhook",
        type=int,
        default=20,
        help="Maximum events to attempt for one webhook in one round.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Sleep interval between defect worker rounds.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="Optional max rounds for the worker loop. 0 means use runtime/idle limits only.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=0,
        help="Optional max runtime before returning. 0 means no explicit runtime cap.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Stop early once defect delivery becomes idle with no remaining backlog.",
    )
    run_defect_sync_worker_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a scheduled local daemon loop instead of a bounded one-shot worker loop.",
    )
    run_defect_sync_worker_parser.set_defaults(handler=handler_module._handle_run_defect_sync_worker)

    replay_integration_dead_letters_parser = subparsers.add_parser(
        "replay-integration-dead-letters",
        help="Preview or replay dead-letter outbox events back into pending delivery state.",
    )
    replay_integration_dead_letters_parser.add_argument(
        "--event-id",
        dest="event_ids",
        action="append",
        default=[],
        help="Optional dead-letter event id filter. Repeat or pass a comma-separated list.",
    )
    replay_integration_dead_letters_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Optional dead-letter event type filter.",
    )
    replay_integration_dead_letters_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum dead-letter events to preview or replay.",
    )
    replay_integration_dead_letters_parser.add_argument(
        "--replayed-by",
        default="cli",
        help="Operator identity recorded in the replay receipt output.",
    )
    replay_integration_dead_letters_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually replay matching dead-letter events. Omit to preview only.",
    )
    replay_integration_dead_letters_parser.set_defaults(handler=handler_module._handle_replay_integration_dead_letters)

    sync_ci_admission_decisions_parser = subparsers.add_parser(
        "sync-ci-admission-decisions",
        help="Query pending CI-relevant admission events and send one-shot decision sync to a webhook target.",
    )
    sync_ci_admission_decisions_parser.add_argument(
        "--webhook-name",
        required=True,
        help="Registered webhook name used for external CI callback delivery.",
    )
    sync_ci_admission_decisions_parser.add_argument(
        "--event-type",
        dest="event_types",
        action="append",
        default=[],
        help="Admission event type filter (repeat or comma-separated). Defaults to admission_case.updated.",
    )
    sync_ci_admission_decisions_parser.add_argument(
        "--ci-endpoint",
        default="",
        help=(
            "Optional CI callback URL. If the webhook name does not exist, it will be created "
            "from this URL for this invocation."
        ),
    )
    sync_ci_admission_decisions_parser.add_argument("--created-by", default="cli", help="Creator identity for auto-register.")
    sync_ci_admission_decisions_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum events to attempt in this sync round.",
    )
    sync_ci_admission_decisions_parser.add_argument(
        "--query-limit",
        type=int,
        default=0,
        help="Max outbox events to scan for pending decisions; 0 means scan all.",
    )
    sync_ci_admission_decisions_parser.add_argument("--dry-run", action="store_true", help="Only query and print the payload, no delivery.")
    sync_ci_admission_decisions_parser.set_defaults(handler=handler_module._handle_sync_ci_admission_decisions)

    prune_snapshots_parser = subparsers.add_parser(
        "prune-analysis-snapshots",
        help="Preview or execute one snapshot retention policy.",
    )
    prune_snapshots_parser.add_argument(
        "--snapshot-type",
        default="",
        choices=["", "top_issues", "comparison", "regression", "replay"],
        help="Optional snapshot type filter.",
    )
    prune_snapshots_parser.add_argument("--created-by", default="", help="Optional creator filter.")
    prune_snapshots_parser.add_argument(
        "--max-count",
        type=int,
        default=None,
        help="Keep at most N newest matching snapshots. Use 0 to delete all matches.",
    )
    prune_snapshots_parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Delete matching snapshots older than N days.",
    )
    prune_snapshots_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete matching snapshots. Without this flag the command only previews the plan.",
    )
    prune_snapshots_parser.set_defaults(handler=handler_module._handle_prune_analysis_snapshots)
