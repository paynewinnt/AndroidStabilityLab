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
  scripts/verify_web_tasks_reboot_loop_smoke.sh --package-name PACKAGE [options]

Warning:
  This is an end-to-end smoke that submits a Web task which sends a real `adb reboot`
  to the target device. Run it only on a device that is safe to reboot.

Required:
  --package-name PACKAGE          Target Android package name for task metadata.

Optional:
  --device-id DEVICE_ID           Run on the specified device only.
  --host HOST                     Web host. Default: 127.0.0.1.
  --port PORT                     Web port. Default: 8036.
  --loop-count N                  Reboot loop count. Default: 1.
  --reboot-timeout-seconds SEC    adb reboot command timeout. Default: 15.
  --boot-wait-timeout-seconds SEC Wait for device to return after reboot. Default: 120.
  --poll-interval-seconds SEC     Poll interval while waiting for boot. Default: 5.
  --settle-ms MS                  Wait after reboot command before polling. Default: 3000.
  --task-timeout-seconds SEC      Task timeout metadata. Default: 180.
  --skip-device-refresh           Skip Web device refresh before creating Run.
  --help                          Show this help message.
EOF
}

PACKAGE_NAME=""
DEVICE_ID=""
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8036}"
LOOP_COUNT=1
REBOOT_TIMEOUT_SECONDS=15
BOOT_WAIT_TIMEOUT_SECONDS=120
POLL_INTERVAL_SECONDS=5
SETTLE_MS=3000
TASK_TIMEOUT_SECONDS=180
SKIP_DEVICE_REFRESH=0

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
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --loop-count)
      LOOP_COUNT="${2:-}"
      shift 2
      ;;
    --reboot-timeout-seconds)
      REBOOT_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --boot-wait-timeout-seconds)
      BOOT_WAIT_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --poll-interval-seconds)
      POLL_INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --settle-ms)
      SETTLE_MS="${2:-}"
      shift 2
      ;;
    --task-timeout-seconds)
      TASK_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --skip-device-refresh)
      SKIP_DEVICE_REFRESH=1
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
OUTPUT_DIR="/tmp/android_stability_lab_web_tasks_reboot_loop_smoke_${TIMESTAMP}"
SERVER_LOG="${OUTPUT_DIR}/server.log"
TASKS_HTML="${OUTPUT_DIR}/tasks.html"
REFRESH_HTML="${OUTPUT_DIR}/refresh_device.html"
CREATE_TASK_HTML="${OUTPUT_DIR}/create_task.html"
CREATE_RUN_HTML="${OUTPUT_DIR}/create_run.html"
EXECUTE_RUN_HTML="${OUTPUT_DIR}/execute_run.html"
TASKS_JSON="${OUTPUT_DIR}/tasks.json"
RUN_DETAIL_JSON="${OUTPUT_DIR}/run_detail.json"
PID=""
ACTOR_ID="tester"
BASE_URL="http://${HOST}:${PORT}"

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
    state="$(adb -s "${DEVICE_ID}" get-state 2>/dev/null | tr -d '\r' | tr -d '[:space:]' || true)"
    if [[ "${state}" == "device" ]]; then
      return 0
    fi
    sleep 1
  done

  finish_with_error "Device ${DEVICE_ID} is not online according to adb get-state."
}

assert_html_contains() {
  local path="$1"
  local expected="$2"
  if ! grep -q "${expected}" "${path}"; then
    finish_with_error "Expected '${expected}' in ${path}."
  fi
}

post_form() {
  local url="$1"
  local output_path="$2"
  shift 2
  curl -fsS \
    -H "X-ASL-Actor: ${ACTOR_ID}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    "$@" \
    "${url}" >"${output_path}"
}

json_query() {
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

if mode == "task_by_name":
    task_name = args[0]
    for task in data.get("tasks", []) or []:
        if task.get("task_name") == task_name:
            print(task.get("task_id", ""))
            break
elif mode == "latest_run_for_task":
    task_id = args[0]
    for run in data.get("runs", []) or []:
        if run.get("task_id") == task_id:
            print(run.get("run_id", ""))
            break
elif mode == "run_status":
    print((data.get("run") or {}).get("run_status", ""))
elif mode == "instance_count":
    print(len((data.get("run") or {}).get("instances", []) or []))
elif mode == "first_instance_status":
    instances = (data.get("run") or {}).get("instances", []) or []
    print(instances[0].get("status", "") if instances else "")
elif mode == "report_path":
    report_paths = (data.get("run") or {}).get("report_paths", {}) or {}
    if report_paths:
        print(next(iter(report_paths.values())))
    else:
        instances = (data.get("run") or {}).get("instances", []) or []
        print(instances[0].get("report_path", "") if instances else "")
elif mode == "instance_status_counts":
    print(json.dumps((data.get("run") or {}).get("instance_status_counts", {}) or {}, ensure_ascii=False, sort_keys=True))
else:
    raise SystemExit(f"unsupported json mode: {mode}")
PY
}

build_task_params_json() {
  "${PYTHON_BIN}" - \
    "${LOOP_COUNT}" \
    "${REBOOT_TIMEOUT_SECONDS}" \
    "${BOOT_WAIT_TIMEOUT_SECONDS}" \
    "${POLL_INTERVAL_SECONDS}" \
    "${SETTLE_MS}" <<'PY'
import json
import sys

payload = {
    "loop_count": int(sys.argv[1]),
    "reboot_timeout_seconds": int(sys.argv[2]),
    "boot_wait_timeout_seconds": int(sys.argv[3]),
    "poll_interval_seconds": int(sys.argv[4]),
    "settle_ms": int(sys.argv[5]),
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

echo "WARNING: reboot_loop Web smoke will submit a real adb reboot task to the target device." >&2

select_device
ensure_device_online

"${PYTHON_BIN}" -m stability.cli serve-web --host "${HOST}" --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
PID=$!

for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
  finish_with_error "Web portal did not become healthy at ${BASE_URL}."
fi

curl -fsS "${BASE_URL}/tasks" >"${TASKS_HTML}"
assert_html_contains "${TASKS_HTML}" "/tasks/actions/create-task"
assert_html_contains "${TASKS_HTML}" "/tasks/actions/create-run"
assert_html_contains "${TASKS_HTML}" "/tasks/actions/execute-run"
assert_html_contains "${TASKS_HTML}" "reboot_loop"

if [[ ${SKIP_DEVICE_REFRESH} -eq 0 ]]; then
  post_form "${BASE_URL}/device-pools/actions/refresh" "${REFRESH_HTML}" \
    --data-urlencode "device_id=${DEVICE_ID}"
  assert_html_contains "${REFRESH_HTML}" "已刷新设备"
fi

TASK_NAME_SUFFIX="$(printf '%s' "${PACKAGE_NAME}" | tr '.:' '__')"
TASK_NAME="web_reboot_loop_smoke_${TASK_NAME_SUFFIX}_${TIMESTAMP}"
TASK_PARAMS_JSON="$(build_task_params_json)"

post_form "${BASE_URL}/tasks/actions/create-task" "${CREATE_TASK_HTML}" \
  --data-urlencode "task_name=${TASK_NAME}" \
  --data-urlencode "package_name=${PACKAGE_NAME}" \
  --data-urlencode "template_type=reboot_loop" \
  --data-urlencode "devices=${DEVICE_ID}" \
  --data-urlencode "sampling_interval=5" \
  --data-urlencode "metrics=cpu" \
  --data-urlencode "metrics=memory" \
  --data-urlencode "task_params=${TASK_PARAMS_JSON}" \
  --data-urlencode "metadata={\"source\":\"web-smoke\",\"entry\":\"/tasks\",\"warning\":\"real-device-reboot\"}" \
  --data-urlencode "note=reboot_loop web tasks smoke; this task intentionally reboots the target device"

assert_html_contains "${CREATE_TASK_HTML}" "已创建任务"
assert_html_contains "${CREATE_TASK_HTML}" "${TASK_NAME}"

curl -fsS "${BASE_URL}/api/tasks" >"${TASKS_JSON}"
TASK_ID="$(json_query "${TASKS_JSON}" task_by_name "${TASK_NAME}")"
if [[ -z "${TASK_ID}" ]]; then
  finish_with_error "Created task '${TASK_NAME}' was not found in /api/tasks."
fi

post_form "${BASE_URL}/tasks/actions/create-run" "${CREATE_RUN_HTML}" \
  --data-urlencode "task_id=${TASK_ID}" \
  --data-urlencode "devices=${DEVICE_ID}" \
  --data-urlencode "metadata={\"source\":\"web-smoke\",\"entry\":\"/tasks\",\"warning\":\"real-device-reboot\"}"

assert_html_contains "${CREATE_RUN_HTML}" "已创建 Run"

curl -fsS "${BASE_URL}/api/tasks" >"${TASKS_JSON}"
RUN_ID="$(json_query "${TASKS_JSON}" latest_run_for_task "${TASK_ID}")"
if [[ -z "${RUN_ID}" ]]; then
  finish_with_error "Created run for task '${TASK_ID}' was not found in /api/tasks."
fi

post_form "${BASE_URL}/tasks/actions/execute-run" "${EXECUTE_RUN_HTML}" \
  --data-urlencode "run_id=${RUN_ID}" \
  --data-urlencode "monitoring_backend=default" \
  --data-urlencode "retry_count=0" \
  --data-urlencode "max_concurrency=1" \
  --data-urlencode "stop_on_failure=0" \
  --data-urlencode "skip_monitoring=1" \
  --data-urlencode "no_persist_monitoring=1"

assert_html_contains "${EXECUTE_RUN_HTML}" "Run 状态"
assert_html_contains "${EXECUTE_RUN_HTML}" "success"
assert_html_contains "${EXECUTE_RUN_HTML}" "${RUN_ID}"

curl -fsS "${BASE_URL}/api/runs/${RUN_ID}" >"${RUN_DETAIL_JSON}"
RUN_STATUS="$(json_query "${RUN_DETAIL_JSON}" run_status)"
INSTANCE_COUNT="$(json_query "${RUN_DETAIL_JSON}" instance_count)"
INSTANCE_STATUS="$(json_query "${RUN_DETAIL_JSON}" first_instance_status)"
INSTANCE_STATUS_COUNTS="$(json_query "${RUN_DETAIL_JSON}" instance_status_counts)"
REPORT_PATH="$(json_query "${RUN_DETAIL_JSON}" report_path)"

echo
echo "Web /tasks Reboot Loop smoke summary"
echo "base_url: ${BASE_URL}"
echo "task_id: ${TASK_ID}"
echo "run_id: ${RUN_ID}"
echo "device_id: ${DEVICE_ID}"
echo "run_status: ${RUN_STATUS}"
echo "instance_count: ${INSTANCE_COUNT}"
echo "first_instance_status: ${INSTANCE_STATUS}"
echo "instance_status_counts: ${INSTANCE_STATUS_COUNTS}"
echo "report_path: ${REPORT_PATH:-<none>}"
echo "output_dir: ${OUTPUT_DIR}"

if [[ "${RUN_STATUS}" != "success" ]]; then
  finish_with_error "Expected run_status=success, got '${RUN_STATUS}'."
fi

if [[ "${INSTANCE_COUNT}" != "1" ]]; then
  finish_with_error "Expected exactly one execution instance, got ${INSTANCE_COUNT}."
fi

if [[ "${INSTANCE_STATUS}" != "success" ]]; then
  finish_with_error "Expected first instance status=success, got '${INSTANCE_STATUS}'."
fi

if [[ -z "${REPORT_PATH}" || ! -f "${REPORT_PATH}" ]]; then
  finish_with_error "Expected report_path to point to an existing file, got '${REPORT_PATH}'."
fi
