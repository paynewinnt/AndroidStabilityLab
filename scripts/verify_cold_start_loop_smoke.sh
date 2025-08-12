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
  scripts/verify_cold_start_loop_smoke.sh --package-name PACKAGE [options]

Required:
  --package-name PACKAGE           Target Android package name.

Optional:
  --device-id DEVICE_ID            Run on the specified device only.
  --launch-activity ACTIVITY       Launch activity, e.g. .MainActivity.
  --loop-count N                   Cold start loop count. Default: 3.
  --launch-wait-ms MS              Wait after each launch. Default: 1000.
  --interval-ms MS                 Interval between loops. Default: 1000.
  --startup-timeout-ms MS          Startup timeout threshold. Default: 10000.
  --task-timeout-seconds SEC       Task execution timeout. Default: 60.
  --with-monitoring                Keep execute-run monitoring enabled.
  --skip-device-sync               Skip device sync in create-task/create-run.
  --help                           Show this help message.
EOF
}

PACKAGE_NAME=""
DEVICE_ID=""
LAUNCH_ACTIVITY=""
LOOP_COUNT=3
LAUNCH_WAIT_MS=1000
INTERVAL_MS=1000
STARTUP_TIMEOUT_MS=10000
TASK_TIMEOUT_SECONDS=60
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
    --launch-activity)
      LAUNCH_ACTIVITY="${2:-}"
      shift 2
      ;;
    --loop-count)
      LOOP_COUNT="${2:-}"
      shift 2
      ;;
    --launch-wait-ms)
      LAUNCH_WAIT_MS="${2:-}"
      shift 2
      ;;
    --interval-ms)
      INTERVAL_MS="${2:-}"
      shift 2
      ;;
    --startup-timeout-ms)
      STARTUP_TIMEOUT_MS="${2:-}"
      shift 2
      ;;
    --task-timeout-seconds)
      TASK_TIMEOUT_SECONDS="${2:-}"
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

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH before running this smoke script." >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="/tmp/android_stability_lab_cold_start_smoke_${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

finish_with_error() {
  local message="$1"
  echo "${message}" >&2
  echo "Output directory: ${OUTPUT_DIR}" >&2
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
    finish_with_error "No online adb devices found. Connect a device or pass --device-id."
  fi

  finish_with_error "Multiple online adb devices detected (${devices[*]}). Please rerun with --device-id."
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

json_path = sys.argv[1]
mode = sys.argv[2]
with open(json_path, encoding="utf-8") as handle:
    data = json.load(handle)

if mode == "task_id":
    print(data["task_id"])
elif mode == "run_id":
    print(data["run_id"])
elif mode == "report_path":
    report_paths = data.get("report_paths") or {}
    if report_paths:
        first_key = next(iter(report_paths))
        print(report_paths[first_key])
    else:
        print("")
elif mode == "first_instance_status":
    instances = data.get("instances") or []
    print(instances[0].get("status", "") if instances else "")
elif mode == "instance_count":
    print(data.get("instance_count", 0))
elif mode == "instance_status_counts":
    print(json.dumps(data.get("instance_status_counts", {}), ensure_ascii=False, sort_keys=True))
else:
    raise SystemExit(f"unsupported json mode: {mode}")
PY
}

build_task_params_json() {
  "${PYTHON_BIN}" - \
    "${LOOP_COUNT}" \
    "${LAUNCH_WAIT_MS}" \
    "${INTERVAL_MS}" \
    "${STARTUP_TIMEOUT_MS}" \
    "${LAUNCH_ACTIVITY}" <<'PY'
import json
import sys

loop_count = int(sys.argv[1])
launch_wait_ms = int(sys.argv[2])
interval_ms = int(sys.argv[3])
startup_timeout_ms = int(sys.argv[4])
launch_activity = sys.argv[5]

payload = {
    "loop_count": loop_count,
    "launch_wait_ms": launch_wait_ms,
    "kill_before_launch": True,
    "interval_ms": interval_ms,
    "startup_timeout_ms": startup_timeout_ms,
}
if launch_activity:
    payload["target_activity"] = launch_activity

print(json.dumps(payload, ensure_ascii=False))
PY
}

select_device

TASK_NAME_SUFFIX="$(printf '%s' "${PACKAGE_NAME}" | tr '.:' '__')"
TASK_NAME="cold_start_loop_smoke_${TASK_NAME_SUFFIX}_${TIMESTAMP}"
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
  --template-type cold_start_loop
  --device "${DEVICE_ID}"
  --created-by smoke_script
  --timeout-seconds "${TASK_TIMEOUT_SECONDS}"
  --task-params "${TASK_PARAMS_JSON}"
  --note "cold_start_loop cli smoke verification"
)
if [[ -n "${LAUNCH_ACTIVITY}" ]]; then
  CREATE_TASK_ARGS+=(--launch-activity "${LAUNCH_ACTIVITY}")
fi
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_TASK_ARGS+=(--skip-device-sync)
fi

run_cli_command "create-task" "${CREATE_TASK_JSON}" "${CREATE_TASK_STDERR}" "${CREATE_TASK_ARGS[@]}"
TASK_ID="$(json_value "${CREATE_TASK_JSON}" task_id)"

CREATE_RUN_ARGS=(
  create-run
  --task-id "${TASK_ID}"
  --device "${DEVICE_ID}"
  --requested-by smoke_script
)
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_RUN_ARGS+=(--skip-device-sync)
fi

run_cli_command "create-run" "${CREATE_RUN_JSON}" "${CREATE_RUN_STDERR}" "${CREATE_RUN_ARGS[@]}"
RUN_ID="$(json_value "${CREATE_RUN_JSON}" run_id)"

EXECUTE_RUN_ARGS=(execute-run --run-id "${RUN_ID}")
if [[ ${WITH_MONITORING} -eq 0 ]]; then
  EXECUTE_RUN_ARGS+=(--skip-monitoring --no-persist-monitoring)
fi

run_cli_command "execute-run" "${EXECUTE_RUN_JSON}" "${EXECUTE_RUN_STDERR}" "${EXECUTE_RUN_ARGS[@]}"

INSTANCE_COUNT="$(json_value "${EXECUTE_RUN_JSON}" instance_count)"
INSTANCE_STATUS="$(json_value "${EXECUTE_RUN_JSON}" first_instance_status)"
INSTANCE_STATUS_COUNTS="$(json_value "${EXECUTE_RUN_JSON}" instance_status_counts)"
REPORT_PATH="$(json_value "${EXECUTE_RUN_JSON}" report_path)"

echo
echo "Cold Start Loop CLI smoke summary"
echo "task_id: ${TASK_ID}"
echo "run_id: ${RUN_ID}"
echo "device_id: ${DEVICE_ID}"
echo "instance_count: ${INSTANCE_COUNT}"
echo "first_instance_status: ${INSTANCE_STATUS}"
echo "instance_status_counts: ${INSTANCE_STATUS_COUNTS}"
echo "report_path: ${REPORT_PATH:-<none>}"
echo "output_dir: ${OUTPUT_DIR}"

if [[ "${INSTANCE_COUNT}" != "1" ]]; then
  finish_with_error "Expected exactly one execution instance, got ${INSTANCE_COUNT}."
fi

if [[ -n "${REPORT_PATH}" && ! -f "${REPORT_PATH}" ]]; then
  finish_with_error "Report path was returned but file does not exist: ${REPORT_PATH}"
fi

if [[ "${INSTANCE_STATUS}" == "success" ]]; then
  if [[ -z "${REPORT_PATH}" ]]; then
    finish_with_error "Execution succeeded but report_path is empty."
  fi
  exit 0
fi

finish_with_error "Smoke verification finished with non-success instance status: ${INSTANCE_STATUS}"
