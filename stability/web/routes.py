from __future__ import annotations

from urllib.parse import unquote


API_PREFIX = "/api/"

HTML_CREATE_TASK_ROUTES = frozenset({"/tasks/actions/create-task", "/tasks/actions/create"})
HTML_ARCHIVE_TASK_ROUTES = frozenset({"/tasks/actions/archive-task", "/tasks/actions/delete"})
HTML_CREATE_RUN_ROUTES = frozenset({"/tasks/actions/create-run", "/runs/actions/create"})
HTML_EXECUTE_RUN_ROUTES = frozenset({"/tasks/actions/execute-run", "/runs/actions/execute"})
HTML_CONFIGURE_UNATTENDED_ROUTES = frozenset({
    "/runner/actions/configure-unattended",
    "/unattended/actions/configure",
})
HTML_RUN_UNATTENDED_ROUND_ROUTES = frozenset({
    "/runner/actions/run-unattended-round",
    "/unattended/actions/run-round",
})
HTML_PATROL_UNATTENDED_ROUTES = frozenset({
    "/runner/actions/patrol-unattended",
    "/unattended/actions/patrol",
})
HTML_RUN_INTEGRATION_WORKER_ROUTES = frozenset({
    "/integration/actions/run-worker",
    "/integration/outbox/actions/run-worker",
})
HTML_REPLAY_DEAD_LETTERS_ROUTES = frozenset({
    "/integration/actions/replay-dead-letters",
    "/integration/outbox/actions/replay-dead-letters",
})
HTML_SYNC_CI_DECISIONS_ROUTES = frozenset({
    "/integration/actions/sync-ci-decisions",
    "/integration/outbox/actions/sync-ci-admission-decisions",
})

API_CREATE_TASK_ROUTES = frozenset({"/api/tasks/actions/create-task", "/api/tasks/actions/create"})
API_ARCHIVE_TASK_ROUTES = frozenset({"/api/tasks/actions/archive-task", "/api/tasks/actions/delete"})
API_CREATE_RUN_ROUTES = frozenset({"/api/tasks/actions/create-run", "/api/runs/actions/create"})
API_EXECUTE_RUN_ROUTES = frozenset({"/api/tasks/actions/execute-run", "/api/runs/actions/execute"})
API_CONFIGURE_UNATTENDED_ROUTES = frozenset({
    "/api/runner/actions/configure-unattended",
    "/api/unattended/actions/configure",
})
API_RUN_UNATTENDED_ROUND_ROUTES = frozenset({
    "/api/runner/actions/run-unattended-round",
    "/api/unattended/actions/run-round",
})
API_PATROL_UNATTENDED_ROUTES = frozenset({
    "/api/runner/actions/patrol-unattended",
    "/api/unattended/actions/patrol",
})
API_RUN_INTEGRATION_WORKER_ROUTES = frozenset({
    "/api/integration/actions/run-worker",
    "/api/integration/outbox/actions/run-worker",
})
API_REPLAY_DEAD_LETTERS_ROUTES = frozenset({
    "/api/integration/actions/replay-dead-letters",
    "/api/integration/outbox/actions/replay-dead-letters",
})
API_SYNC_CI_DECISIONS_ROUTES = frozenset({
    "/api/integration/actions/sync-ci-decisions",
    "/api/integration/outbox/actions/sync-ci-admission-decisions",
})

HTML_GOLDEN_CASE_PREFIX = "/goldens/case/"
HTML_RUN_ARTIFACTS_PREFIX = "/artifacts/run/"
HTML_RUN_DETAIL_PREFIX = "/runs/"
HTML_TASK_DETAIL_PREFIX = "/tasks/task/"
HTML_UNATTENDED_DETAIL_PREFIX = "/runner/unattended/"
HTML_ADMISSION_BASELINE_PREFIX = "/admission/baseline/"

API_ADMISSION_REPORT_PREFIX = "/api/admission/reports/"
API_GOLDEN_CASE_PREFIX = "/api/goldens/case/"
API_RUN_ARTIFACTS_PREFIX = "/api/artifacts/run/"
API_RUN_DETAIL_PREFIX = "/api/runs/"
API_RELEASE_SUBMISSION_DETAIL_PREFIX = "/api/release-submissions/"
API_TASK_DETAIL_PREFIX = "/api/tasks/task/"
API_UNATTENDED_DETAIL_PREFIX = "/api/runner/unattended/"
API_ADMISSION_BASELINE_PREFIX = "/api/admission/baseline/"
API_ADMISSION_CASE_PREFIX = "/api/admission/cases/"


def is_api_route(route: str) -> bool:
    return str(route or "").startswith(API_PREFIX)


def route_in(route: str, routes: frozenset[str]) -> bool:
    return route in routes


def route_value_after_prefix(route: str, prefix: str) -> str | None:
    if not route.startswith(prefix):
        return None
    return unquote(route.removeprefix(prefix))
