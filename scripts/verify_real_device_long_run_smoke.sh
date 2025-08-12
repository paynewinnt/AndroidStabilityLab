#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -x "./.venv/bin/python" ]]; then
  PYTHON_BIN="./.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "Python interpreter not found. Expected ./.venv/bin/python or python3 in PATH." >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage:
  scripts/verify_real_device_long_run_smoke.sh --package-name PACKAGE [options]

Purpose:
  Productized real-device long-run smoke for a short 5-10 minute path.
  By default it creates a foreground_background_loop task, creates one Run,
  executes it once with monitoring enabled, and verifies instance/report/
  monitoring snapshot/issue summary plus Web visibility.

Required:
  --package-name PACKAGE                Target Android package name.
  --device-id DEVICE_ID                 Real adb device id. Required unless exactly one device is online.

Short-path options:
  --template-type TYPE                  foreground_background_loop or standby_wake_loop. Default: foreground_background_loop.
  --execution-mode MODE                 direct, unattended, patrol, or patrol-runner. Default: direct.
  --duration-minutes N                  Planned short-path duration metadata. Default: 6.
  --loop-count N                        Loop count. Default: 10.
  --foreground-wait-ms MS               Foreground wait for foreground_background_loop. Default: 15000.
  --background-wait-ms MS               Background wait for foreground_background_loop. Default: 15000.
  --standby-wait-ms MS                  Standby wait for standby_wake_loop. Default: 15000.
  --wake-wait-ms MS                     Wake wait for standby_wake_loop. Default: 15000.
  --launch-activity ACTIVITY            Launch activity for foreground_background_loop, e.g. .MainActivity.
  --task-timeout-seconds SEC            Task execution timeout. Default: 900.
  --monitoring-backend BACKEND          Monitoring backend override passed to execution. Default: default.
  --skip-device-sync                    Skip device sync in create-task/create-run.

Web visibility options:
  --host HOST                           Web host. Default: 127.0.0.1.
  --port PORT                           Web port. Default: 8040.

Stability entry options, not enabled by default:
  --interval-minutes N                  Unattended interval. Default: 60.
  --runner-interval-seconds SEC         Patrol runner sleep interval. Default: 60.
  --runner-iterations N                 Patrol runner iterations. Default: 1.
  --run-hours N                         Manual long-run target hint for operators, e.g. 1 or 2. Default: 0.
  --patrol-runner                       Alias for --execution-mode patrol-runner.
  --require-human-disconnect-check      Print a manual device-disconnect prompt before execution.

Other:
  --help                                Show this help message.
EOF
}

PACKAGE_NAME=""
DEVICE_ID=""
TEMPLATE_TYPE="foreground_background_loop"
EXECUTION_MODE="direct"
DURATION_MINUTES=6
LOOP_COUNT=10
FOREGROUND_WAIT_MS=15000
BACKGROUND_WAIT_MS=15000
STANDBY_WAIT_MS=15000
WAKE_WAIT_MS=15000
LAUNCH_ACTIVITY=""
TASK_TIMEOUT_SECONDS=900
MONITORING_BACKEND="default"
SKIP_DEVICE_SYNC=0
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8040}"
INTERVAL_MINUTES=60
RUNNER_INTERVAL_SECONDS=60
RUNNER_ITERATIONS=1
RUN_HOURS=0
REQUIRE_HUMAN_DISCONNECT_CHECK=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-name)
      PACKAGE_NAME="${2:-}"
      shift 2
      ;;
    --device-id)
      DEVICE_ID="${2:-}"
      shift 2
      ;;
    --template-type)
      TEMPLATE_TYPE="${2:-}"
      shift 2
      ;;
    --execution-mode)
      EXECUTION_MODE="${2:-}"
      shift 2
      ;;
    --duration-minutes)
      DURATION_MINUTES="${2:-}"
      shift 2
      ;;
    --loop-count)
      LOOP_COUNT="${2:-}"
      shift 2
      ;;
    --foreground-wait-ms)
      FOREGROUND_WAIT_MS="${2:-}"
      shift 2
      ;;
    --background-wait-ms)
      BACKGROUND_WAIT_MS="${2:-}"
      shift 2
      ;;
    --standby-wait-ms)
      STANDBY_WAIT_MS="${2:-}"
      shift 2
      ;;
    --wake-wait-ms)
      WAKE_WAIT_MS="${2:-}"
      shift 2
      ;;
    --launch-activity)
      LAUNCH_ACTIVITY="${2:-}"
      shift 2
      ;;
    --task-timeout-seconds)
      TASK_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --monitoring-backend)
      MONITORING_BACKEND="${2:-}"
      shift 2
      ;;
    --skip-device-sync)
      SKIP_DEVICE_SYNC=1
      shift
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --interval-minutes)
      INTERVAL_MINUTES="${2:-}"
      shift 2
      ;;
    --runner-interval-seconds)
      RUNNER_INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --runner-iterations)
      RUNNER_ITERATIONS="${2:-}"
      shift 2
      ;;
    --run-hours)
      RUN_HOURS="${2:-}"
      shift 2
      ;;
    --patrol-runner)
      EXECUTION_MODE="patrol-runner"
      shift
      ;;
    --require-human-disconnect-check)
      REQUIRE_HUMAN_DISCONNECT_CHECK=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${PACKAGE_NAME}" ]]; then
  echo "--package-name is required." >&2
  usage >&2
  exit 1
fi

case "${TEMPLATE_TYPE}" in
  foreground_background_loop|standby_wake_loop)
    ;;
  *)
    echo "--template-type must be foreground_background_loop or standby_wake_loop." >&2
    exit 1
    ;;
esac

case "${EXECUTION_MODE}" in
  direct|unattended|patrol|patrol-runner)
    ;;
  *)
    echo "--execution-mode must be direct, unattended, patrol, or patrol-runner." >&2
    exit 1
    ;;
esac

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH before running this smoke script." >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="/tmp/android_stability_lab_real_device_long_run_smoke_${TIMESTAMP}"
SERVER_LOG="${OUTPUT_DIR}/server.log"
BASE_URL="http://${HOST}:${PORT}"
PID=""

mkdir -p "${OUTPUT_DIR}"

cleanup() {
  if [[ -n "${PID}" ]] && kill -0 "${PID}" >/dev/null 2>&1; then
    kill "${PID}" >/dev/null 2>&1 || true
    wait "${PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

finish_with_error() {
  local message="$1"
  echo "${message}" >&2
  echo "Output directory: ${OUTPUT_DIR}" >&2
  if [[ -s "${SERVER_LOG}" ]]; then
    echo "Server log:" >&2
    tail -40 "${SERVER_LOG}" >&2 || true
  fi
  exit 1
}

select_device() {
  if [[ -n "${DEVICE_ID}" ]]; then
    return 0
  fi

  local devices=()
  local serial=""
  local status=""
  while read -r serial status _; do
    if [[ "${serial}" == "List" || -z "${serial}" ]]; then
      continue
    fi
    if [[ "${status}" == "device" ]]; then
      devices+=("${serial}")
    fi
  done < <(adb devices)

  if [[ ${#devices[@]} -eq 1 ]]; then
    DEVICE_ID="${devices[0]}"
    return 0
  fi

  if [[ ${#devices[@]} -eq 0 ]]; then
    finish_with_error "No online adb devices found. Connect a real device or pass --device-id."
  fi

  finish_with_error "Multiple online adb devices detected (${devices[*]}). Please rerun with --device-id."
}

ensure_device_online() {
  if [[ "${DEVICE_ID}" == *:* ]]; then
    adb connect "${DEVICE_ID}" >/dev/null 2>&1 || true
  fi

  local state=""
  local attempt=0
  for attempt in 1 2 3 4 5; do
    state="$(adb -s "${DEVICE_ID}" get-state 2>/dev/null | LC_ALL=C tr -d '\r\n\t ' || true)"
    if [[ "${state}" == "device" ]]; then
      return 0
    fi
    sleep 1
  done

  finish_with_error "Device ${DEVICE_ID} is not online according to adb get-state."
}

run_cli_command() {
  local label="$1"
  local stdout_path="$2"
  local stderr_path="$3"
  shift 3

  echo "[$label] Running: ${PYTHON_BIN} -m stability.cli $*"

  local status=0
  set +e
  "${PYTHON_BIN}" -m stability.cli "$@" >"${stdout_path}" 2>"${stderr_path}"
  status=$?
  set -e

  if [[ ${status} -ne 0 ]]; then
    echo "[$label] Command failed with exit code ${status}." >&2
    [[ -s "${stderr_path}" ]] && cat "${stderr_path}" >&2
    if [[ -s "${stdout_path}" ]]; then
      echo "[$label] stdout:" >&2
      cat "${stdout_path}" >&2
    fi
    echo "Output directory: ${OUTPUT_DIR}" >&2
    exit "${status}"
  fi
}

json_value() {
  local json_path="$1"
  local mode="$2"
  shift 2
  "${PYTHON_BIN}" - "${json_path}" "${mode}" "$@" <<'PY'
import json
import sys
from pathlib import Path

json_path = Path(sys.argv[1])
mode = sys.argv[2]
args = sys.argv[3:]
data = json.loads(json_path.read_text(encoding="utf-8"))

def first_instance(payload):
    instances = payload.get("instances") or []
    return dict(instances[0] or {}) if instances else {}

def nested_run(payload):
    return dict(payload.get("run") or payload)

# Handles direct run_id plus unattended round/executed_rounds payloads.
def first_run_id(value):
    if isinstance(value, dict):
        run_id = str(value.get("run_id", "") or "").strip()
        if run_id:
            return run_id
        for nested in value.values():
            found = first_run_id(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = first_run_id(nested)
            if found:
                return found
    return ""

if mode == "task_id":
    print(data["task_id"])
elif mode == "run_id":
    print(first_run_id(data))
elif mode == "run_status":
    run = nested_run(data)
    print(run.get("run_status") or run.get("status") or "")
elif mode == "instance_count":
    print(len(data.get("instances") or []))
elif mode == "first_instance_status":
    print(first_instance(data).get("status", ""))
elif mode == "report_path":
    report_paths = data.get("report_paths") or {}
    if report_paths:
        print(next(iter(report_paths.values())))
    else:
        print(first_instance(data).get("report_path", "") or "")
elif mode == "issue_count":
    print(first_instance(data).get("issue_count", 0))
elif mode == "monitoring_snapshot_path":
    print(first_instance(data).get("monitoring_snapshot_path", "") or "")
elif mode == "api_tasks_has_run":
    run_id = args[0]
    print("yes" if run_id and run_id in json.dumps(data, ensure_ascii=False) else "no")
elif mode == "performance_sample_count":
    print(int((data.get("summary") or {}).get("sample_count", 0) or 0))
elif mode == "issue_summary_count":
    print(int((data.get("summary") or {}).get("issue_count", 0) or 0))
elif mode == "runner_page":
    print(data.get("page", ""))
else:
    raise SystemExit(f"unsupported json mode: {mode}")
PY
}

build_task_params_json() {
  if [[ "${TEMPLATE_TYPE}" == "foreground_background_loop" ]]; then
    "${PYTHON_BIN}" - \
      "${LOOP_COUNT}" \
      "${FOREGROUND_WAIT_MS}" \
      "${BACKGROUND_WAIT_MS}" \
      "${LAUNCH_ACTIVITY}" <<'PY'
import json
import sys

payload = {
    "loop_count": int(sys.argv[1]),
    "foreground_wait_ms": int(sys.argv[2]),
    "background_wait_ms": int(sys.argv[3]),
    "launch_timeout_seconds": 20,
    "home_timeout_seconds": 10,
}
if sys.argv[4]:
    payload["target_activity"] = sys.argv[4]
print(json.dumps(payload, ensure_ascii=False))
PY
  else
    "${PYTHON_BIN}" - \
      "${LOOP_COUNT}" \
      "${STANDBY_WAIT_MS}" \
      "${WAKE_WAIT_MS}" <<'PY'
import json
import sys

payload = {
    "loop_count": int(sys.argv[1]),
    "standby_wait_ms": int(sys.argv[2]),
    "wake_wait_ms": int(sys.argv[3]),
    "command_timeout_seconds": 10,
    "unlock_after_wake": True,
}
print(json.dumps(payload, ensure_ascii=False))
PY
  fi
}

wait_for_web() {
  for _ in $(seq 1 30); do
    if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

assert_file_exists() {
  local path="$1"
  local label="$2"
  if [[ -z "${path}" || ! -f "${path}" ]]; then
    finish_with_error "Expected ${label} to point to an existing file, got '${path}'."
  fi
}

assert_html_visible() {
  local path="$1"
  local label="$2"
  if [[ ! -s "${path}" ]]; then
    finish_with_error "Expected ${label} response to be non-empty."
  fi
}

select_device
ensure_device_online

if [[ ${RUN_HOURS} -gt 0 ]]; then
  echo "Manual long-run hint: operator requested ${RUN_HOURS} hour(s), but this smoke still executes one bounded short round only."
fi

if [[ ${REQUIRE_HUMAN_DISCONNECT_CHECK} -eq 1 ]]; then
  echo "Manual check: keep a human ready to inspect/recover device ${DEVICE_ID} if a mid-run disconnect is observed."
fi

TASK_NAME_SUFFIX="$(printf '%s' "${PACKAGE_NAME}" | sed 's/[.:]/_/g')"
TASK_NAME="real_device_long_run_smoke_${TEMPLATE_TYPE}_${TASK_NAME_SUFFIX}_${TIMESTAMP}"
TASK_PARAMS_JSON="$(build_task_params_json)"

CREATE_TASK_JSON="${OUTPUT_DIR}/create_task.json"
CREATE_TASK_STDERR="${OUTPUT_DIR}/create_task.stderr"
CREATE_RUN_JSON="${OUTPUT_DIR}/create_run.json"
CREATE_RUN_STDERR="${OUTPUT_DIR}/create_run.stderr"
EXECUTE_JSON="${OUTPUT_DIR}/execute.json"
EXECUTE_STDERR="${OUTPUT_DIR}/execute.stderr"
SHOW_RUN_JSON="${OUTPUT_DIR}/show_run.json"
SHOW_RUN_STDERR="${OUTPUT_DIR}/show_run.stderr"
CONFIGURE_JSON="${OUTPUT_DIR}/configure_unattended.json"
CONFIGURE_STDERR="${OUTPUT_DIR}/configure_unattended.stderr"

CREATE_TASK_ARGS=(
  create-task
  --task-name "${TASK_NAME}"
  --package-name "${PACKAGE_NAME}"
  --template-type "${TEMPLATE_TYPE}"
  --device "${DEVICE_ID}"
  --created-by smoke_script
  --duration-seconds "$((DURATION_MINUTES * 60))"
  --timeout-seconds "${TASK_TIMEOUT_SECONDS}"
  --sampling-interval 5
  --metric cpu
  --metric memory
  --task-params "${TASK_PARAMS_JSON}"
  --metadata "{\"source\":\"real-device-long-run-smoke\",\"execution_mode\":\"${EXECUTION_MODE}\"}"
  --note "real device long-run product smoke; short bounded verification"
)
if [[ -n "${LAUNCH_ACTIVITY}" && "${TEMPLATE_TYPE}" == "foreground_background_loop" ]]; then
  CREATE_TASK_ARGS+=(--launch-activity "${LAUNCH_ACTIVITY}")
fi
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_TASK_ARGS+=(--skip-device-sync)
fi

run_cli_command "create-task" "${CREATE_TASK_JSON}" "${CREATE_TASK_STDERR}" "${CREATE_TASK_ARGS[@]}"
TASK_ID="$(json_value "${CREATE_TASK_JSON}" task_id)"

RUN_ID=""

if [[ "${EXECUTION_MODE}" == "direct" ]]; then
  CREATE_RUN_ARGS=(
    create-run
    --task-id "${TASK_ID}"
    --device "${DEVICE_ID}"
    --requested-by smoke_script
    --metadata "{\"source\":\"real-device-long-run-smoke\",\"mode\":\"direct\"}"
  )
  if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
    CREATE_RUN_ARGS+=(--skip-device-sync)
  fi

  run_cli_command "create-run" "${CREATE_RUN_JSON}" "${CREATE_RUN_STDERR}" "${CREATE_RUN_ARGS[@]}"
  RUN_ID="$(json_value "${CREATE_RUN_JSON}" run_id)"

  run_cli_command "execute-run" "${EXECUTE_JSON}" "${EXECUTE_STDERR}" \
    execute-run \
    --run-id "${RUN_ID}" \
    --max-concurrency 1 \
    --retry-count 0 \
    --monitoring-backend "${MONITORING_BACKEND}"
else
  run_cli_command "configure-unattended" "${CONFIGURE_JSON}" "${CONFIGURE_STDERR}" \
    configure-unattended-task \
    --task-id "${TASK_ID}" \
    --interval-minutes "${INTERVAL_MINUTES}" \
    --device "${DEVICE_ID}" \
    --desired-device-count 1 \
    --failure-threshold 1 \
    --max-round-history 3 \
    --rotation-strategy fixed \
    --start-now

  if [[ "${EXECUTION_MODE}" == "unattended" ]]; then
    run_cli_command "run-unattended-round" "${EXECUTE_JSON}" "${EXECUTE_STDERR}" \
      run-unattended-round \
      --task-id "${TASK_ID}" \
      --requested-by smoke_script \
      --max-concurrency 1 \
      --retry-count 0 \
      --monitoring-backend "${MONITORING_BACKEND}"
  elif [[ "${EXECUTION_MODE}" == "patrol" ]]; then
    run_cli_command "patrol-unattended-tasks" "${EXECUTE_JSON}" "${EXECUTE_STDERR}" \
      patrol-unattended-tasks \
      --task-id "${TASK_ID}" \
      --force \
      --requested-by smoke_script \
      --max-concurrency 1 \
      --retry-count 0 \
      --monitoring-backend "${MONITORING_BACKEND}"
  else
    run_cli_command "run-unattended-patrol-runner" "${EXECUTE_JSON}" "${EXECUTE_STDERR}" \
      run-unattended-patrol-runner \
      --task-id "${TASK_ID}" \
      --force \
      --interval-seconds "${RUNNER_INTERVAL_SECONDS}" \
      --max-iterations "${RUNNER_ITERATIONS}" \
      --requested-by smoke_script \
      --max-concurrency 1 \
      --retry-count 0 \
      --monitoring-backend "${MONITORING_BACKEND}"
  fi
  RUN_ID="$(json_value "${EXECUTE_JSON}" run_id)"
fi

if [[ -z "${RUN_ID}" ]]; then
  finish_with_error "Execution did not return a run_id."
fi

run_cli_command "show-run" "${SHOW_RUN_JSON}" "${SHOW_RUN_STDERR}" show-run --run-id "${RUN_ID}"

RUN_STATUS="$(json_value "${SHOW_RUN_JSON}" run_status)"
INSTANCE_COUNT="$(json_value "${SHOW_RUN_JSON}" instance_count)"
INSTANCE_STATUS="$(json_value "${SHOW_RUN_JSON}" first_instance_status)"
REPORT_PATH="$(json_value "${SHOW_RUN_JSON}" report_path)"
ISSUE_COUNT="$(json_value "${SHOW_RUN_JSON}" issue_count)"
MONITORING_SNAPSHOT_PATH="$(json_value "${SHOW_RUN_JSON}" monitoring_snapshot_path)"

if [[ "${RUN_STATUS}" != "success" ]]; then
  finish_with_error "Expected run_status=success, got '${RUN_STATUS}'."
fi

if [[ "${INSTANCE_COUNT}" != "1" ]]; then
  finish_with_error "Expected exactly one execution instance, got ${INSTANCE_COUNT}."
fi

if [[ "${INSTANCE_STATUS}" != "success" ]]; then
  finish_with_error "Expected first instance status=success, got '${INSTANCE_STATUS}'."
fi

assert_file_exists "${REPORT_PATH}" "report_path"
assert_file_exists "${MONITORING_SNAPSHOT_PATH}" "monitoring_snapshot_path"

"${PYTHON_BIN}" -m stability.cli serve-web --host "${HOST}" --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
PID=$!

if ! wait_for_web; then
  finish_with_error "Web portal did not become healthy at ${BASE_URL}."
fi

TASKS_HTML="${OUTPUT_DIR}/tasks.html"
RUNNER_HTML="${OUTPUT_DIR}/runner.html"
PERFORMANCE_HTML="${OUTPUT_DIR}/performance.html"
TASKS_JSON="${OUTPUT_DIR}/tasks.json"
RUNNER_JSON="${OUTPUT_DIR}/runner.json"
PERFORMANCE_JSON="${OUTPUT_DIR}/performance.json"
ISSUES_JSON="${OUTPUT_DIR}/issues.json"

curl -fsS "${BASE_URL}/tasks" >"${TASKS_HTML}"
curl -fsS "${BASE_URL}/runner" >"${RUNNER_HTML}"
curl -fsS "${BASE_URL}/performance" >"${PERFORMANCE_HTML}"
curl -fsS "${BASE_URL}/api/tasks" >"${TASKS_JSON}"
curl -fsS "${BASE_URL}/api/runner" >"${RUNNER_JSON}"
curl -fsS "${BASE_URL}/api/performance" >"${PERFORMANCE_JSON}"
curl -fsS "${BASE_URL}/api/issues?limit=20" >"${ISSUES_JSON}"

assert_html_visible "${TASKS_HTML}" "/tasks"
assert_html_visible "${RUNNER_HTML}" "/runner"
assert_html_visible "${PERFORMANCE_HTML}" "/performance"

API_TASKS_HAS_RUN="$(json_value "${TASKS_JSON}" api_tasks_has_run "${RUN_ID}")"
PERFORMANCE_SAMPLE_COUNT="$(json_value "${PERFORMANCE_JSON}" performance_sample_count)"
ISSUE_SUMMARY_COUNT="$(json_value "${ISSUES_JSON}" issue_summary_count)"
RUNNER_PAGE="$(json_value "${RUNNER_JSON}" runner_page)"

if [[ "${API_TASKS_HAS_RUN}" != "yes" ]]; then
  finish_with_error "Expected /api/tasks to include run ${RUN_ID}."
fi

if [[ "${PERFORMANCE_SAMPLE_COUNT}" -lt 1 ]]; then
  finish_with_error "Expected /api/performance to expose at least one monitoring sample."
fi

if [[ "${RUNNER_PAGE}" != "runner" ]]; then
  finish_with_error "Expected /api/runner page='runner', got '${RUNNER_PAGE}'."
fi

echo
echo "Real-device long-run smoke summary"
echo "task_id: ${TASK_ID}"
echo "run_id: ${RUN_ID}"
echo "device_id: ${DEVICE_ID}"
echo "template_type: ${TEMPLATE_TYPE}"
echo "execution_mode: ${EXECUTION_MODE}"
echo "run_status: ${RUN_STATUS}"
echo "instance_count: ${INSTANCE_COUNT}"
echo "first_instance_status: ${INSTANCE_STATUS}"
echo "issue_count: ${ISSUE_COUNT}"
echo "issue_summary_count: ${ISSUE_SUMMARY_COUNT}"
echo "report_path: ${REPORT_PATH}"
echo "monitoring_snapshot_path: ${MONITORING_SNAPSHOT_PATH}"
echo "performance_sample_count: ${PERFORMANCE_SAMPLE_COUNT}"
echo "web_base_url: ${BASE_URL}"
echo "output_dir: ${OUTPUT_DIR}"
