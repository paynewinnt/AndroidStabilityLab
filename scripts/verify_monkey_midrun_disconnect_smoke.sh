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
  scripts/verify_monkey_midrun_disconnect_smoke.sh \
    --package-name PACKAGE \
    --device-id HOST:PORT [options]

Required:
  --package-name PACKAGE                Target Android package name.
  --device-id HOST:PORT                 TCP device id to disconnect during Monkey execution.

Optional:
  --event-count N                       Monkey event count. Default: 300.
  --throttle-ms MS                      Monkey throttle in milliseconds. Default: 100.
  --seed N                              Optional Monkey seed.
  --verbosity N                         Monkey verbosity. Default: 1.
  --task-timeout-seconds SEC            Task execution timeout. Default: 90.
  --disconnect-after-seconds SEC        Delay before adb disconnect. Default: 3.
  --with-monitoring                     Keep execute-run monitoring enabled.
  --skip-device-sync                    Skip device sync in create-task/create-run.
  --help                                Show this help message.
EOF
}

PACKAGE_NAME=""
DEVICE_ID=""
EVENT_COUNT=300
THROTTLE_MS=100
SEED=""
VERBOSITY=1
TASK_TIMEOUT_SECONDS=90
DISCONNECT_AFTER_SECONDS=3
WITH_MONITORING=0
SKIP_DEVICE_SYNC=0

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
    --event-count)
      EVENT_COUNT="${2:-}"
      shift 2
      ;;
    --throttle-ms)
      THROTTLE_MS="${2:-}"
      shift 2
      ;;
    --seed)
      SEED="${2:-}"
      shift 2
      ;;
    --verbosity)
      VERBOSITY="${2:-}"
      shift 2
      ;;
    --task-timeout-seconds)
      TASK_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --disconnect-after-seconds)
      DISCONNECT_AFTER_SECONDS="${2:-}"
      shift 2
      ;;
    --with-monitoring)
      WITH_MONITORING=1
      shift
      ;;
    --skip-device-sync)
      SKIP_DEVICE_SYNC=1
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

if [[ -z "${DEVICE_ID}" ]]; then
  echo "--device-id is required." >&2
  usage >&2
  exit 1
fi

if [[ "${DEVICE_ID}" != *:* ]]; then
  echo "--device-id must be a TCP target like HOST:PORT." >&2
  exit 1
fi

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH before running this smoke script." >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="/tmp/android_stability_lab_monkey_midrun_disconnect_${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

DISCONNECT_LOG="${OUTPUT_DIR}/disconnect.log"
DISCONNECT_PID=""

finish_with_error() {
  local message="$1"
  echo "${message}" >&2
  echo "Output directory: ${OUTPUT_DIR}" >&2
  exit 1
}

cleanup() {
  if [[ -n "${DISCONNECT_PID}" ]] && kill -0 "${DISCONNECT_PID}" >/dev/null 2>&1; then
    kill "${DISCONNECT_PID}" >/dev/null 2>&1 || true
  fi
  adb connect "${DEVICE_ID}" >/dev/null 2>&1 || true
}

trap cleanup EXIT

ensure_device_online() {
  local state=""
  state="$(adb -s "${DEVICE_ID}" get-state 2>/dev/null | tr -d '\r[:space:]' || true)"
  if [[ "${state}" != "device" ]]; then
    finish_with_error "Device ${DEVICE_ID} is not online according to adb get-state."
  fi
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
    if [[ -s "${stderr_path}" ]]; then
      cat "${stderr_path}" >&2
    fi
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
  "${PYTHON_BIN}" - "${json_path}" "${mode}" <<'PY'
import json
import sys
from pathlib import Path

json_path = sys.argv[1]
mode = sys.argv[2]
with open(json_path, encoding="utf-8") as handle:
    data = json.load(handle)

if mode == "task_id":
    print(data["task_id"])
elif mode == "run_id":
    print(data["run_id"])
elif mode == "run_status":
    print(data.get("run_status", ""))
elif mode == "instance_count":
    print(data.get("instance_count", 0))
elif mode == "instance_status_counts":
    print(json.dumps(data.get("instance_status_counts", {}), ensure_ascii=False, sort_keys=True))
elif mode == "first_instance_status":
    instances = data.get("instances") or []
    print(instances[0].get("status", "") if instances else "")
elif mode == "report_path":
    report_paths = data.get("report_paths") or {}
    if report_paths:
        first_key = next(iter(report_paths))
        print(report_paths[first_key])
    else:
        print("")
elif mode == "execution_log_path":
    report_paths = data.get("report_paths") or {}
    if not report_paths:
        print("")
    else:
        first_key = next(iter(report_paths))
        report_path = Path(report_paths[first_key])
        print(report_path.parents[1] / "logs" / "execution.log")
else:
    raise SystemExit(f"unsupported json mode: {mode}")
PY
}

build_task_params_json() {
  "${PYTHON_BIN}" - \
    "${EVENT_COUNT}" \
    "${THROTTLE_MS}" \
    "${SEED}" \
    "${VERBOSITY}" \
    "${TASK_TIMEOUT_SECONDS}" <<'PY'
import json
import sys

event_count = int(sys.argv[1])
throttle_ms = int(sys.argv[2])
seed = sys.argv[3]
verbosity = int(sys.argv[4])
timeout_seconds = int(sys.argv[5])

payload = {
    "event_count": event_count,
    "throttle_ms": throttle_ms,
    "ignore_crashes": True,
    "ignore_timeouts": True,
    "ignore_security_exceptions": True,
    "force_stop_before_start": True,
    "timeout_seconds": timeout_seconds,
    "verbosity": verbosity,
}
if seed:
    payload["seed"] = int(seed)

print(json.dumps(payload, ensure_ascii=False))
PY
}

ensure_device_online

TASK_NAME_SUFFIX="$(printf '%s' "${PACKAGE_NAME}" | tr '.:' '__')"
TASK_NAME="monkey_midrun_disconnect_${TASK_NAME_SUFFIX}_${TIMESTAMP}"
TASK_PARAMS_JSON="$(build_task_params_json)"

CREATE_TASK_JSON="${OUTPUT_DIR}/create_task.json"
CREATE_TASK_STDERR="${OUTPUT_DIR}/create_task.stderr"
CREATE_RUN_JSON="${OUTPUT_DIR}/create_run.json"
CREATE_RUN_STDERR="${OUTPUT_DIR}/create_run.stderr"
EXECUTE_RUN_JSON="${OUTPUT_DIR}/execute_run.json"
EXECUTE_RUN_STDERR="${OUTPUT_DIR}/execute_run.stderr"

CREATE_TASK_ARGS=(
  create-task
  --task-name "${TASK_NAME}"
  --package-name "${PACKAGE_NAME}"
  --template-type monkey
  --created-by monkey_midrun_disconnect_smoke_script
  --timeout-seconds "${TASK_TIMEOUT_SECONDS}"
  --task-params "${TASK_PARAMS_JSON}"
  --note "monkey mid-run disconnect smoke verification"
  --device "${DEVICE_ID}"
)
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_TASK_ARGS+=(--skip-device-sync)
fi

run_cli_command "create-task" "${CREATE_TASK_JSON}" "${CREATE_TASK_STDERR}" "${CREATE_TASK_ARGS[@]}"
TASK_ID="$(json_value "${CREATE_TASK_JSON}" task_id)"

CREATE_RUN_ARGS=(
  create-run
  --task-id "${TASK_ID}"
  --requested-by monkey_midrun_disconnect_smoke_script
  --device "${DEVICE_ID}"
)
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_RUN_ARGS+=(--skip-device-sync)
fi

run_cli_command "create-run" "${CREATE_RUN_JSON}" "${CREATE_RUN_STDERR}" "${CREATE_RUN_ARGS[@]}"
RUN_ID="$(json_value "${CREATE_RUN_JSON}" run_id)"

(
  sleep "${DISCONNECT_AFTER_SECONDS}"
  {
    printf '[disconnect] at=%s device=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${DEVICE_ID}"
    adb disconnect "${DEVICE_ID}"
  } >>"${DISCONNECT_LOG}" 2>&1
) &
DISCONNECT_PID=$!

EXECUTE_RUN_ARGS=(
  execute-run
  --run-id "${RUN_ID}"
  --max-concurrency 1
)
if [[ ${WITH_MONITORING} -eq 0 ]]; then
  EXECUTE_RUN_ARGS+=(--skip-monitoring --no-persist-monitoring)
fi

run_cli_command "execute-run" "${EXECUTE_RUN_JSON}" "${EXECUTE_RUN_STDERR}" "${EXECUTE_RUN_ARGS[@]}"

wait "${DISCONNECT_PID}" || true
DISCONNECT_PID=""

RUN_STATUS="$(json_value "${EXECUTE_RUN_JSON}" run_status)"
INSTANCE_COUNT="$(json_value "${EXECUTE_RUN_JSON}" instance_count)"
INSTANCE_STATUS_COUNTS="$(json_value "${EXECUTE_RUN_JSON}" instance_status_counts)"
FIRST_INSTANCE_STATUS="$(json_value "${EXECUTE_RUN_JSON}" first_instance_status)"
REPORT_PATH="$(json_value "${EXECUTE_RUN_JSON}" report_path)"
EXECUTION_LOG_PATH="$(json_value "${EXECUTE_RUN_JSON}" execution_log_path)"

echo
echo "Monkey mid-run disconnect smoke summary"
echo "task_id: ${TASK_ID}"
echo "run_id: ${RUN_ID}"
echo "device_id: ${DEVICE_ID}"
echo "disconnect_after_seconds: ${DISCONNECT_AFTER_SECONDS}"
echo "instance_count: ${INSTANCE_COUNT}"
echo "run_status: ${RUN_STATUS}"
echo "instance_status_counts: ${INSTANCE_STATUS_COUNTS}"
echo "first_instance_status: ${FIRST_INSTANCE_STATUS}"
echo "report_path: ${REPORT_PATH}"
echo "execution_log_path: ${EXECUTION_LOG_PATH}"
echo "disconnect_log: ${DISCONNECT_LOG}"
echo "output_dir: ${OUTPUT_DIR}"

if [[ -s "${DISCONNECT_LOG}" ]]; then
  echo
  echo "Disconnect log:"
  cat "${DISCONNECT_LOG}"
fi

if [[ "${INSTANCE_COUNT}" != "1" ]]; then
  finish_with_error "Expected exactly one execution instance, got ${INSTANCE_COUNT}."
fi

if [[ "${RUN_STATUS}" != "success" ]]; then
  finish_with_error "Expected run_status=success after one reconnect retry, got ${RUN_STATUS}."
fi

if [[ "${FIRST_INSTANCE_STATUS}" != "success" ]]; then
  finish_with_error "Expected the monkey execution instance to recover and succeed, got ${FIRST_INSTANCE_STATUS}."
fi

if [[ -z "${REPORT_PATH}" || ! -f "${REPORT_PATH}" ]]; then
  finish_with_error "Expected a persisted report_path, got '${REPORT_PATH}'."
fi

if [[ -z "${EXECUTION_LOG_PATH}" || ! -f "${EXECUTION_LOG_PATH}" ]]; then
  finish_with_error "Expected execution log at '${EXECUTION_LOG_PATH}'."
fi

if ! grep -q "reconnect recovered command path" "${EXECUTION_LOG_PATH}"; then
  finish_with_error "Expected execution log to contain the Monkey reconnect-retry marker."
fi

exit 0
