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
  scripts/verify_cli_query_smoke.sh --package-name PACKAGE [options]

Required:
  --package-name PACKAGE              Target Android package name.

Optional:
  --device-id DEVICE_ID               Run on the specified device only.
  --launch-activity ACTIVITY          Launch activity, e.g. .MainActivity.
  --with-monitoring                   Keep execute-run monitoring enabled.
  --skip-device-sync                  Skip device sync in create-task/create-run only.
  --help                              Show this help message.
EOF
}

PACKAGE_NAME=""
DEVICE_ID=""
LAUNCH_ACTIVITY=""
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
OUTPUT_DIR="/tmp/android_stability_lab_cli_query_smoke_${TIMESTAMP}"
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

ensure_device_online() {
  if [[ "${DEVICE_ID}" == *:* ]]; then
    adb connect "${DEVICE_ID}" >/dev/null 2>&1 || true
  fi

  local state=""
  local attempt=0
  for attempt in 1 2 3 4 5; do
    state="$(adb -s "${DEVICE_ID}" get-state 2>/dev/null | tr -d '\r[:space:]' || true)"
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
elif mode == "device_count":
    print(data.get("device_count", 0))
elif mode == "task_count":
    print(data.get("task_count", 0))
elif mode == "run_count":
    print(data.get("run_count", 0))
elif mode == "first_run_id":
    runs = data.get("runs") or []
    print(runs[0].get("run_id", "") if runs else "")
elif mode == "report_path":
    report_paths = data.get("report_paths") or {}
    if report_paths:
        first_key = next(iter(report_paths))
        print(report_paths[first_key])
    else:
        print("")
elif mode == "html_report_path":
    report_paths = data.get("html_report_paths") or {}
    if report_paths:
        first_key = next(iter(report_paths))
        print(report_paths[first_key])
    else:
        instances = data.get("instances") or []
        print(instances[0].get("html_report_path", "") if instances else "")
elif mode == "artifact_count":
    instances = data.get("instances") or []
    print(instances[0].get("artifact_count", 0) if instances else 0)
elif mode == "issue_count":
    instances = data.get("instances") or []
    print(instances[0].get("issue_count", 0) if instances else 0)
else:
    raise SystemExit(f"unsupported json mode: {mode}")
PY
}

build_task_params_json() {
  "${PYTHON_BIN}" - "${LAUNCH_ACTIVITY}" <<'PY'
import json
import sys

launch_activity = sys.argv[1]
payload = {
    "loop_count": 1,
    "launch_wait_ms": 500,
    "kill_before_launch": True,
    "interval_ms": 500,
    "startup_timeout_ms": 1,
    "launch_timeout_seconds": 15,
}
if launch_activity:
    payload["target_activity"] = launch_activity
print(json.dumps(payload, ensure_ascii=False))
PY
}

select_device
ensure_device_online

DEVICE_JSON="${OUTPUT_DIR}/show_device.json"
DEVICE_STDERR="${OUTPUT_DIR}/show_device.stderr"
run_cli_command "show_device_sync_target" "${DEVICE_JSON}" "${DEVICE_STDERR}" show-device --device-id "${DEVICE_ID}" --sync-target-only

LIST_DEVICES_JSON="${OUTPUT_DIR}/list_devices.json"
LIST_DEVICES_STDERR="${OUTPUT_DIR}/list_devices.stderr"
run_cli_command "list_devices_sync_target" "${LIST_DEVICES_JSON}" "${LIST_DEVICES_STDERR}" list-devices --sync-device "${DEVICE_ID}"

TASK_PARAMS_JSON="$(build_task_params_json)"
CREATE_TASK_JSON="${OUTPUT_DIR}/create_task.json"
CREATE_TASK_STDERR="${OUTPUT_DIR}/create_task.stderr"
CREATE_TASK_ARGS=(
  create-task
  --task-name "CLI Query Smoke Cold Start Timeout"
  --package-name "${PACKAGE_NAME}"
  --template-type cold_start_loop
  --device "${DEVICE_ID}"
  --task-params "${TASK_PARAMS_JSON}"
)
if [[ -n "${LAUNCH_ACTIVITY}" ]]; then
  CREATE_TASK_ARGS+=(--launch-activity "${LAUNCH_ACTIVITY}")
fi
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_TASK_ARGS+=(--skip-device-sync)
fi
run_cli_command "create_task" "${CREATE_TASK_JSON}" "${CREATE_TASK_STDERR}" "${CREATE_TASK_ARGS[@]}"
TASK_ID="$(json_value "${CREATE_TASK_JSON}" task_id)"

LIST_TASKS_JSON="${OUTPUT_DIR}/list_tasks.json"
LIST_TASKS_STDERR="${OUTPUT_DIR}/list_tasks.stderr"
run_cli_command "list_tasks" "${LIST_TASKS_JSON}" "${LIST_TASKS_STDERR}" list-tasks

SHOW_TASK_JSON="${OUTPUT_DIR}/show_task.json"
SHOW_TASK_STDERR="${OUTPUT_DIR}/show_task.stderr"
run_cli_command "show_task" "${SHOW_TASK_JSON}" "${SHOW_TASK_STDERR}" show-task --task-id "${TASK_ID}"

CREATE_RUN_JSON="${OUTPUT_DIR}/create_run.json"
CREATE_RUN_STDERR="${OUTPUT_DIR}/create_run.stderr"
CREATE_RUN_ARGS=(
  create-run
  --task-id "${TASK_ID}"
  --device "${DEVICE_ID}"
)
if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
  CREATE_RUN_ARGS+=(--skip-device-sync)
fi
run_cli_command "create_run" "${CREATE_RUN_JSON}" "${CREATE_RUN_STDERR}" "${CREATE_RUN_ARGS[@]}"
RUN_ID="$(json_value "${CREATE_RUN_JSON}" run_id)"

EXECUTE_RUN_JSON="${OUTPUT_DIR}/execute_run.json"
EXECUTE_RUN_STDERR="${OUTPUT_DIR}/execute_run.stderr"
EXECUTE_RUN_ARGS=(
  execute-run
  --run-id "${RUN_ID}"
  --skip-monitoring
)
if [[ ${WITH_MONITORING} -eq 1 ]]; then
  EXECUTE_RUN_ARGS=(execute-run --run-id "${RUN_ID}")
fi
run_cli_command "execute_run" "${EXECUTE_RUN_JSON}" "${EXECUTE_RUN_STDERR}" "${EXECUTE_RUN_ARGS[@]}"

LIST_RUNS_JSON="${OUTPUT_DIR}/list_runs.json"
LIST_RUNS_STDERR="${OUTPUT_DIR}/list_runs.stderr"
run_cli_command \
  "list_runs_filtered" \
  "${LIST_RUNS_JSON}" \
  "${LIST_RUNS_STDERR}" \
  list-runs \
  --task-id "${TASK_ID}" \
  --status failed \
  --template-type cold_start_loop \
  --package-name "${PACKAGE_NAME}" \
  --device-id "${DEVICE_ID}" \
  --has-issue true

SHOW_RUN_JSON="${OUTPUT_DIR}/show_run.json"
SHOW_RUN_STDERR="${OUTPUT_DIR}/show_run.stderr"
run_cli_command "show_run" "${SHOW_RUN_JSON}" "${SHOW_RUN_STDERR}" show-run --run-id "${RUN_ID}"

RUN_STATUS="$(json_value "${EXECUTE_RUN_JSON}" run_status)"
REPORT_PATH="$(json_value "${SHOW_RUN_JSON}" report_path)"
HTML_REPORT_PATH="$(json_value "${SHOW_RUN_JSON}" html_report_path)"
RUN_COUNT="$(json_value "${LIST_RUNS_JSON}" run_count)"
FIRST_RUN_ID="$(json_value "${LIST_RUNS_JSON}" first_run_id)"
ARTIFACT_COUNT="$(json_value "${SHOW_RUN_JSON}" artifact_count)"
ISSUE_COUNT="$(json_value "${SHOW_RUN_JSON}" issue_count)"
DEVICE_COUNT="$(json_value "${LIST_DEVICES_JSON}" device_count)"
TASK_COUNT="$(json_value "${LIST_TASKS_JSON}" task_count)"

if [[ "${RUN_STATUS}" != "failed" ]]; then
  finish_with_error "Expected run_status=failed for deterministic timeout smoke, got '${RUN_STATUS}'."
fi

if [[ "${RUN_COUNT}" -lt 1 || "${FIRST_RUN_ID}" != "${RUN_ID}" ]]; then
  finish_with_error "Filtered list-runs did not return the expected run."
fi

if [[ "${DEVICE_COUNT}" -lt 1 ]]; then
  finish_with_error "list-devices --sync returned no devices."
fi

if [[ "${TASK_COUNT}" -lt 1 ]]; then
  finish_with_error "list-tasks returned no tasks."
fi

if [[ "${ISSUE_COUNT}" -lt 1 ]]; then
  finish_with_error "Expected show-run to report at least one issue."
fi

if [[ "${ARTIFACT_COUNT}" -lt 1 ]]; then
  finish_with_error "Expected show-run to report at least one artifact."
fi

if [[ -z "${REPORT_PATH}" || ! -f "${REPORT_PATH}" ]]; then
  finish_with_error "Markdown report was not created."
fi

if [[ -z "${HTML_REPORT_PATH}" || ! -f "${HTML_REPORT_PATH}" ]]; then
  finish_with_error "HTML report was not created."
fi

if ! grep -q "bugreport.txt" "${REPORT_PATH}"; then
  finish_with_error "Markdown report does not reference bugreport.txt."
fi

if ! grep -q "bugreport.txt" "${HTML_REPORT_PATH}"; then
  finish_with_error "HTML report does not reference bugreport.txt."
fi

if ! find "$(dirname "${REPORT_PATH}")/../artifacts" -type f -name 'bugreport.txt' | grep -q .; then
  finish_with_error "No bugreport.txt artifact was captured."
fi

echo "task_id=${TASK_ID}"
echo "run_id=${RUN_ID}"
echo "run_status=${RUN_STATUS}"
echo "device_id=${DEVICE_ID}"
echo "report_path=${REPORT_PATH}"
echo "html_report_path=${HTML_REPORT_PATH}"
echo "output_dir=${OUTPUT_DIR}"
