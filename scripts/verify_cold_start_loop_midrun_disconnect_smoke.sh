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
  scripts/verify_cold_start_loop_midrun_disconnect_smoke.sh \
    --package-name PACKAGE \
    --disconnect-device-id DEVICE_A \
    --device-id DEVICE_A \
    --device-id DEVICE_B [options]

Required:
  --package-name PACKAGE                Target Android package name.
  --disconnect-device-id DEVICE_ID      Device to disconnect during execution.
  --device-id DEVICE_ID                 Target device id. Repeat at least twice.

Optional:
  --launch-activity ACTIVITY            Launch activity, e.g. .MainActivity.
  --loop-count N                        Cold start loop count. Default: 6.
  --launch-wait-ms MS                   Wait after each launch. Default: 1000.
  --interval-ms MS                      Interval between loops. Default: 2000.
  --startup-timeout-ms MS               Startup timeout threshold. Default: 10000.
  --task-timeout-seconds SEC            Task execution timeout. Default: 90.
  --disconnect-after-seconds SEC        Delay before disconnect. Default: 2.
  --max-concurrency N                   Execute up to N instances in parallel. Default: 1.
  --with-monitoring                     Keep execute-run monitoring enabled.
  --skip-device-sync                    Skip device sync in create-task/create-run.
  --help                                Show this help message.
EOF
}

PACKAGE_NAME=""
DISCONNECT_DEVICE_ID=""
LAUNCH_ACTIVITY=""
LOOP_COUNT=6
LAUNCH_WAIT_MS=1000
INTERVAL_MS=2000
STARTUP_TIMEOUT_MS=10000
TASK_TIMEOUT_SECONDS=90
DISCONNECT_AFTER_SECONDS=2
MAX_CONCURRENCY=1
WITH_MONITORING=0
SKIP_DEVICE_SYNC=0
DEVICE_IDS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-name)
      PACKAGE_NAME="${2:-}"
      shift 2
      ;;
    --disconnect-device-id)
      DISCONNECT_DEVICE_ID="${2:-}"
      shift 2
      ;;
    --device-id)
      DEVICE_IDS+=("${2:-}")
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
    --disconnect-after-seconds)
      DISCONNECT_AFTER_SECONDS="${2:-}"
      shift 2
      ;;
    --max-concurrency)
      MAX_CONCURRENCY="${2:-}"
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

if [[ -z "${DISCONNECT_DEVICE_ID}" ]]; then
  echo "--disconnect-device-id is required." >&2
  usage >&2
  exit 1
fi

if [[ ${#DEVICE_IDS[@]} -lt 2 ]]; then
  echo "At least two --device-id values are required." >&2
  usage >&2
  exit 1
fi

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH before running this smoke script." >&2
  exit 1
fi

device_present=0
for device_id in "${DEVICE_IDS[@]}"; do
  if [[ "${device_id}" == "${DISCONNECT_DEVICE_ID}" ]]; then
    device_present=1
    break
  fi
done

if [[ ${device_present} -ne 1 ]]; then
  echo "--disconnect-device-id must also be present in --device-id list." >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="/tmp/android_stability_lab_cold_start_midrun_disconnect_${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

DISCONNECT_DEVICE_SANITIZED="$(printf '%s' "${DISCONNECT_DEVICE_ID}" | tr '.:' '__')"
DISCONNECT_LOG="${OUTPUT_DIR}/disconnect.log"
DISCONNECT_PID=""

finish_with_error() {
  local message="$1"
  echo "${message}" >&2
  echo "Output directory: ${OUTPUT_DIR}" >&2
  exit 1
}

ensure_devices_online() {
  local serial=""
  local state=""
  for serial in "${DEVICE_IDS[@]}"; do
    state="$(adb -s "${serial}" get-state 2>/dev/null | tr -d '\r[:space:]' || true)"
    if [[ "${state}" != "device" ]]; then
      finish_with_error "Device ${serial} is not online according to adb get-state."
    fi
  done
}

cleanup() {
  if [[ -n "${DISCONNECT_PID}" ]] && kill -0 "${DISCONNECT_PID}" >/dev/null 2>&1; then
    kill "${DISCONNECT_PID}" >/dev/null 2>&1 || true
  fi
  adb connect "${DISCONNECT_DEVICE_ID}" >/dev/null 2>&1 || true
}

trap cleanup EXIT

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
elif mode == "run_status":
    print(data.get("run_status", ""))
elif mode == "instance_count":
    print(data.get("instance_count", 0))
elif mode == "instance_status_counts":
    print(json.dumps(data.get("instance_status_counts", {}), ensure_ascii=False, sort_keys=True))
elif mode == "report_paths":
    print(json.dumps(data.get("report_paths", {}), ensure_ascii=False, sort_keys=True))
elif mode == "disconnect_device_status":
    disconnect_device_id = sys.argv[3]
    instances = data.get("instances") or []
    matched = next((item for item in instances if item.get("device_id") == disconnect_device_id), {})
    print(matched.get("status", ""))
elif mode == "cancelled_count":
    print(sum(1 for item in (data.get("instances") or []) if item.get("status") == "cancelled"))
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

ensure_devices_online

# Put the disconnect target first so max_concurrency=1 always executes it before the others.
ORDERED_DEVICE_IDS=("${DISCONNECT_DEVICE_ID}")
for device_id in "${DEVICE_IDS[@]}"; do
  if [[ "${device_id}" != "${DISCONNECT_DEVICE_ID}" ]]; then
    ORDERED_DEVICE_IDS+=("${device_id}")
  fi
done

TASK_NAME_SUFFIX="$(printf '%s' "${PACKAGE_NAME}" | tr '.:' '__')"
TASK_NAME="cold_start_loop_midrun_disconnect_${TASK_NAME_SUFFIX}_${TIMESTAMP}"
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
  --created-by midrun_disconnect_smoke_script
  --timeout-seconds "${TASK_TIMEOUT_SECONDS}"
  --task-params "${TASK_PARAMS_JSON}"
  --note "cold_start_loop mid-run disconnect smoke verification"
)
for device_id in "${ORDERED_DEVICE_IDS[@]}"; do
  CREATE_TASK_ARGS+=(--device "${device_id}")
done
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
  --requested-by midrun_disconnect_smoke_script
)
for device_id in "${ORDERED_DEVICE_IDS[@]}"; do
  CREATE_RUN_ARGS+=(--device "${device_id}")
done
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_RUN_ARGS+=(--skip-device-sync)
fi

run_cli_command "create-run" "${CREATE_RUN_JSON}" "${CREATE_RUN_STDERR}" "${CREATE_RUN_ARGS[@]}"
RUN_ID="$(json_value "${CREATE_RUN_JSON}" run_id)"

(
  sleep "${DISCONNECT_AFTER_SECONDS}"
  {
    printf '[disconnect] at=%s device=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${DISCONNECT_DEVICE_ID}"
    adb disconnect "${DISCONNECT_DEVICE_ID}"
  } >>"${DISCONNECT_LOG}" 2>&1
) &
DISCONNECT_PID=$!

EXECUTE_RUN_ARGS=(
  execute-run
  --run-id "${RUN_ID}"
  --max-concurrency "${MAX_CONCURRENCY}"
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
REPORT_PATHS="$(json_value "${EXECUTE_RUN_JSON}" report_paths)"
DISCONNECT_DEVICE_STATUS="$("${PYTHON_BIN}" - "${EXECUTE_RUN_JSON}" disconnect_device_status "${DISCONNECT_DEVICE_ID}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)

disconnect_device_id = sys.argv[3]
instances = data.get("instances") or []
matched = next((item for item in instances if item.get("device_id") == disconnect_device_id), {})
print(matched.get("status", ""))
PY
)"
CANCELLED_COUNT="$(json_value "${EXECUTE_RUN_JSON}" cancelled_count)"

echo
echo "Cold Start Loop mid-run disconnect smoke summary"
echo "task_id: ${TASK_ID}"
echo "run_id: ${RUN_ID}"
echo "ordered_device_ids: ${ORDERED_DEVICE_IDS[*]}"
echo "disconnect_device_id: ${DISCONNECT_DEVICE_ID}"
echo "disconnect_after_seconds: ${DISCONNECT_AFTER_SECONDS}"
echo "instance_count: ${INSTANCE_COUNT}"
echo "run_status: ${RUN_STATUS}"
echo "instance_status_counts: ${INSTANCE_STATUS_COUNTS}"
echo "disconnect_device_status: ${DISCONNECT_DEVICE_STATUS}"
echo "cancelled_count: ${CANCELLED_COUNT}"
echo "report_paths: ${REPORT_PATHS}"
echo "disconnect_log: ${DISCONNECT_LOG}"
echo "output_dir: ${OUTPUT_DIR}"

if [[ -s "${DISCONNECT_LOG}" ]]; then
  echo
  echo "Disconnect log:"
  cat "${DISCONNECT_LOG}"
fi

if [[ "${INSTANCE_COUNT}" != "${#ORDERED_DEVICE_IDS[@]}" ]]; then
  finish_with_error "Expected ${#ORDERED_DEVICE_IDS[@]} execution instances, got ${INSTANCE_COUNT}."
fi

if [[ "${RUN_STATUS}" != "success" ]]; then
  finish_with_error "Expected run_status=success after one reconnect retry, got ${RUN_STATUS}."
fi

if [[ "${DISCONNECT_DEVICE_STATUS}" != "success" ]]; then
  finish_with_error "Expected disconnect target ${DISCONNECT_DEVICE_ID} to recover and succeed, got ${DISCONNECT_DEVICE_STATUS}."
fi

if [[ "${CANCELLED_COUNT}" != "0" ]]; then
  finish_with_error "Expected no cancelled instances after reconnect recovery, got ${CANCELLED_COUNT}."
fi

exit 0
