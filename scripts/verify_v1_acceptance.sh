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
  scripts/verify_v1_acceptance.sh [options]

Default behavior:
  Run the safe local V1 acceptance baseline only:
  - unittest discover
  - compileall
  - shell syntax checks for smoke scripts
  - CLI help checks
  - list-runs / show-run history-query sanity check

Optional real-device smoke flags:
  --run-extended-artifacts-smoke
  --run-cli-query-smoke
  --run-monkey-smoke
  --run-cold-start-smoke
  --run-cold-start-multi-device-smoke
  --run-cold-start-midrun-disconnect-smoke
  --run-foreground-background-smoke
  --run-web-foreground-background-smoke
  --run-install-uninstall-smoke
  --run-web-install-uninstall-smoke
  --run-reboot-smoke
  --run-web-reboot-smoke
  --run-standby-wake-smoke
  --run-web-standby-wake-smoke
  --run-monkey-midrun-disconnect-smoke

Shared optional arguments:
  --with-monitoring                     Keep execute-run monitoring enabled.
  --skip-device-sync                    Skip device sync in smoke scripts.

Cold start smoke arguments:
  --cold-start-package PACKAGE          Package for cold_start_loop smoke scripts.
  --cold-start-launch-activity ACT      Optional launch activity.
  --cold-start-device-id DEVICE_ID      Device id for cold_start_loop smoke. Repeat for multi-device modes.
  --cold-start-disconnect-device-id ID  Disconnect target for midrun cold_start_loop smoke.

Foreground/background smoke arguments:
  --foreground-background-package PACKAGE      Package for foreground_background_loop smoke.
  --foreground-background-launch-activity ACT  Optional launch activity.
  --foreground-background-device-id DEVICE_ID  Device id for foreground_background_loop smoke.
  --web-foreground-background-port PORT        Optional Web smoke port. Default: 8035.

Install/uninstall smoke arguments:
  --install-uninstall-package PACKAGE          Package for install_uninstall_loop smoke.
  --install-uninstall-apk-path APK             APK path for install_uninstall_loop smoke.
  --install-uninstall-device-id DEVICE_ID      Device id for install_uninstall_loop smoke.
  --web-install-uninstall-port PORT            Optional Web smoke port. Default: 8036.

Reboot smoke arguments:
  --reboot-package PACKAGE                     Package metadata for reboot_loop smoke.
  --reboot-device-id DEVICE_ID                 Device id for reboot_loop smoke.
  --web-reboot-port PORT                       Optional Web smoke port. Default: 8037.

Standby/wake smoke arguments:
  --standby-wake-package PACKAGE               Package metadata for standby_wake_loop smoke.
  --standby-wake-device-id DEVICE_ID           Device id for standby_wake_loop smoke.
  --web-standby-wake-port PORT                 Optional Web smoke port. Default: 8038.

Monkey smoke arguments:
  --monkey-package PACKAGE              Package for Monkey smoke scripts.
  --monkey-device-id DEVICE_ID          Device id for Monkey smoke; TCP target required for midrun disconnect smoke.

Other:
  --help                               Show this help message.
EOF
}

WITH_MONITORING=0
SKIP_DEVICE_SYNC=0
RUN_COLD_START_SMOKE=0
RUN_COLD_START_MULTI_DEVICE_SMOKE=0
RUN_COLD_START_MIDRUN_DISCONNECT_SMOKE=0
RUN_FOREGROUND_BACKGROUND_SMOKE=0
RUN_WEB_FOREGROUND_BACKGROUND_SMOKE=0
RUN_INSTALL_UNINSTALL_SMOKE=0
RUN_WEB_INSTALL_UNINSTALL_SMOKE=0
RUN_REBOOT_SMOKE=0
RUN_WEB_REBOOT_SMOKE=0
RUN_STANDBY_WAKE_SMOKE=0
RUN_WEB_STANDBY_WAKE_SMOKE=0
RUN_EXTENDED_ARTIFACTS_SMOKE=0
RUN_CLI_QUERY_SMOKE=0
RUN_MONKEY_SMOKE=0
RUN_MONKEY_MIDRUN_DISCONNECT_SMOKE=0
COLD_START_PACKAGE=""
COLD_START_LAUNCH_ACTIVITY=""
COLD_START_DISCONNECT_DEVICE_ID=""
FOREGROUND_BACKGROUND_PACKAGE=""
FOREGROUND_BACKGROUND_LAUNCH_ACTIVITY=""
FOREGROUND_BACKGROUND_DEVICE_ID=""
WEB_FOREGROUND_BACKGROUND_PORT="8035"
INSTALL_UNINSTALL_PACKAGE=""
INSTALL_UNINSTALL_APK_PATH=""
INSTALL_UNINSTALL_DEVICE_ID=""
WEB_INSTALL_UNINSTALL_PORT="8036"
REBOOT_PACKAGE=""
REBOOT_DEVICE_ID=""
WEB_REBOOT_PORT="8037"
STANDBY_WAKE_PACKAGE=""
STANDBY_WAKE_DEVICE_ID=""
WEB_STANDBY_WAKE_PORT="8038"
MONKEY_PACKAGE=""
MONKEY_DEVICE_ID=""
COLD_START_DEVICE_IDS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-monitoring)
      WITH_MONITORING=1
      shift
      ;;
    --skip-device-sync)
      SKIP_DEVICE_SYNC=1
      shift
      ;;
    --run-cold-start-smoke)
      RUN_COLD_START_SMOKE=1
      shift
      ;;
    --run-cold-start-multi-device-smoke)
      RUN_COLD_START_MULTI_DEVICE_SMOKE=1
      shift
      ;;
    --run-cold-start-midrun-disconnect-smoke)
      RUN_COLD_START_MIDRUN_DISCONNECT_SMOKE=1
      shift
      ;;
    --run-foreground-background-smoke)
      RUN_FOREGROUND_BACKGROUND_SMOKE=1
      shift
      ;;
    --run-web-foreground-background-smoke)
      RUN_WEB_FOREGROUND_BACKGROUND_SMOKE=1
      shift
      ;;
    --run-install-uninstall-smoke)
      RUN_INSTALL_UNINSTALL_SMOKE=1
      shift
      ;;
    --run-web-install-uninstall-smoke)
      RUN_WEB_INSTALL_UNINSTALL_SMOKE=1
      shift
      ;;
    --run-reboot-smoke)
      RUN_REBOOT_SMOKE=1
      shift
      ;;
    --run-web-reboot-smoke)
      RUN_WEB_REBOOT_SMOKE=1
      shift
      ;;
    --run-standby-wake-smoke)
      RUN_STANDBY_WAKE_SMOKE=1
      shift
      ;;
    --run-web-standby-wake-smoke)
      RUN_WEB_STANDBY_WAKE_SMOKE=1
      shift
      ;;
    --run-extended-artifacts-smoke)
      RUN_EXTENDED_ARTIFACTS_SMOKE=1
      shift
      ;;
    --run-cli-query-smoke)
      RUN_CLI_QUERY_SMOKE=1
      shift
      ;;
    --run-monkey-smoke)
      RUN_MONKEY_SMOKE=1
      shift
      ;;
    --run-monkey-midrun-disconnect-smoke)
      RUN_MONKEY_MIDRUN_DISCONNECT_SMOKE=1
      shift
      ;;
    --cold-start-package)
      COLD_START_PACKAGE="${2:-}"
      shift 2
      ;;
    --cold-start-launch-activity)
      COLD_START_LAUNCH_ACTIVITY="${2:-}"
      shift 2
      ;;
    --cold-start-device-id)
      COLD_START_DEVICE_IDS+=("${2:-}")
      shift 2
      ;;
    --cold-start-disconnect-device-id)
      COLD_START_DISCONNECT_DEVICE_ID="${2:-}"
      shift 2
      ;;
    --foreground-background-package)
      FOREGROUND_BACKGROUND_PACKAGE="${2:-}"
      shift 2
      ;;
    --foreground-background-launch-activity)
      FOREGROUND_BACKGROUND_LAUNCH_ACTIVITY="${2:-}"
      shift 2
      ;;
    --foreground-background-device-id)
      FOREGROUND_BACKGROUND_DEVICE_ID="${2:-}"
      shift 2
      ;;
    --web-foreground-background-port)
      WEB_FOREGROUND_BACKGROUND_PORT="${2:-}"
      shift 2
      ;;
    --install-uninstall-package)
      INSTALL_UNINSTALL_PACKAGE="${2:-}"
      shift 2
      ;;
    --install-uninstall-apk-path)
      INSTALL_UNINSTALL_APK_PATH="${2:-}"
      shift 2
      ;;
    --install-uninstall-device-id)
      INSTALL_UNINSTALL_DEVICE_ID="${2:-}"
      shift 2
      ;;
    --web-install-uninstall-port)
      WEB_INSTALL_UNINSTALL_PORT="${2:-}"
      shift 2
      ;;
    --reboot-package)
      REBOOT_PACKAGE="${2:-}"
      shift 2
      ;;
    --reboot-device-id)
      REBOOT_DEVICE_ID="${2:-}"
      shift 2
      ;;
    --web-reboot-port)
      WEB_REBOOT_PORT="${2:-}"
      shift 2
      ;;
    --standby-wake-package)
      STANDBY_WAKE_PACKAGE="${2:-}"
      shift 2
      ;;
    --standby-wake-device-id)
      STANDBY_WAKE_DEVICE_ID="${2:-}"
      shift 2
      ;;
    --web-standby-wake-port)
      WEB_STANDBY_WAKE_PORT="${2:-}"
      shift 2
      ;;
    --monkey-package)
      MONKEY_PACKAGE="${2:-}"
      shift 2
      ;;
    --monkey-device-id)
      MONKEY_DEVICE_ID="${2:-}"
      shift 2
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

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="/tmp/android_stability_lab_v1_acceptance_${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"
SUMMARY_FILE="${OUTPUT_DIR}/summary.md"

cat >"${SUMMARY_FILE}" <<EOF
# Android Stability Lab V1 Acceptance Summary

- started_at: $(date '+%Y-%m-%d %H:%M:%S %z')
- repo_root: ${REPO_ROOT}
- output_dir: ${OUTPUT_DIR}

## Steps

EOF

finish_with_error() {
  local message="$1"
  echo "${message}" >&2
  echo "Output directory: ${OUTPUT_DIR}" >&2
  echo "- FAIL: ${message}" >>"${SUMMARY_FILE}"
  exit 1
}

record_step() {
  local status="$1"
  local label="$2"
  local detail="${3:-}"
  echo "- ${status}: ${label}${detail:+ (${detail})}" >>"${SUMMARY_FILE}"
}

run_step() {
  local label="$1"
  shift
  local slug
  slug="$(printf '%s' "${label}" | tr '[:upper:] ' '[:lower:]_' | tr -cd 'a-z0-9_')"
  local stdout_path="${OUTPUT_DIR}/${slug}.stdout"
  local stderr_path="${OUTPUT_DIR}/${slug}.stderr"

  echo "[${label}] Running: $*"
  local status=0
  set +e
  "$@" >"${stdout_path}" 2>"${stderr_path}"
  status=$?
  set -e

  if [[ ${status} -ne 0 ]]; then
    record_step "FAIL" "${label}" "exit=${status}"
    if [[ -s "${stderr_path}" ]]; then
      cat "${stderr_path}" >&2
    fi
    if [[ -s "${stdout_path}" ]]; then
      cat "${stdout_path}" >&2
    fi
    finish_with_error "${label} failed with exit code ${status}."
  fi

  record_step "PASS" "${label}"
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

if mode == "run_count":
    print(data.get("run_count", 0))
elif mode == "first_run_id":
    runs = data.get("runs") or []
    print(runs[0].get("run_id", "") if runs else "")
else:
    raise SystemExit(f"unsupported json mode: {mode}")
PY
}

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    finish_with_error "Required command '${name}' was not found in PATH."
  fi
}

build_common_smoke_args() {
  local args=()
  if [[ ${WITH_MONITORING} -eq 1 ]]; then
    args+=(--with-monitoring)
  fi
  if [[ ${SKIP_DEVICE_SYNC} -eq 1 ]]; then
    args+=(--skip-device-sync)
  fi
  if [[ ${#args[@]} -gt 0 ]]; then
    printf '%s\n' "${args[@]}"
  fi
}

append_common_smoke_args() {
  local target_name="$1"
  local item=""
  while read -r item; do
    if [[ -n "${item}" ]]; then
      eval "${target_name}+=(\"\${item}\")"
    fi
  done < <(build_common_smoke_args)
}

validate_real_smoke_args() {
  if [[ ${RUN_EXTENDED_ARTIFACTS_SMOKE} -eq 1 || ${RUN_CLI_QUERY_SMOKE} -eq 1 || ${RUN_COLD_START_SMOKE} -eq 1 || ${RUN_COLD_START_MULTI_DEVICE_SMOKE} -eq 1 || ${RUN_COLD_START_MIDRUN_DISCONNECT_SMOKE} -eq 1 || ${RUN_FOREGROUND_BACKGROUND_SMOKE} -eq 1 || ${RUN_WEB_FOREGROUND_BACKGROUND_SMOKE} -eq 1 || ${RUN_INSTALL_UNINSTALL_SMOKE} -eq 1 || ${RUN_WEB_INSTALL_UNINSTALL_SMOKE} -eq 1 || ${RUN_REBOOT_SMOKE} -eq 1 || ${RUN_WEB_REBOOT_SMOKE} -eq 1 || ${RUN_STANDBY_WAKE_SMOKE} -eq 1 || ${RUN_WEB_STANDBY_WAKE_SMOKE} -eq 1 || ${RUN_MONKEY_SMOKE} -eq 1 || ${RUN_MONKEY_MIDRUN_DISCONNECT_SMOKE} -eq 1 ]]; then
    require_command adb
  fi

  if [[ ${RUN_EXTENDED_ARTIFACTS_SMOKE} -eq 1 ]]; then
    if [[ -z "${COLD_START_PACKAGE}" || ${#COLD_START_DEVICE_IDS[@]} -lt 1 ]]; then
      finish_with_error "--run-extended-artifacts-smoke requires --cold-start-package and one --cold-start-device-id."
    fi
  fi

  if [[ ${RUN_CLI_QUERY_SMOKE} -eq 1 ]]; then
    if [[ -z "${COLD_START_PACKAGE}" || ${#COLD_START_DEVICE_IDS[@]} -lt 1 ]]; then
      finish_with_error "--run-cli-query-smoke requires --cold-start-package and one --cold-start-device-id."
    fi
  fi

  if [[ ${RUN_COLD_START_SMOKE} -eq 1 ]]; then
    if [[ -z "${COLD_START_PACKAGE}" || ${#COLD_START_DEVICE_IDS[@]} -lt 1 ]]; then
      finish_with_error "--run-cold-start-smoke requires --cold-start-package and one --cold-start-device-id."
    fi
  fi

  if [[ ${RUN_COLD_START_MULTI_DEVICE_SMOKE} -eq 1 ]]; then
    if [[ -z "${COLD_START_PACKAGE}" || ${#COLD_START_DEVICE_IDS[@]} -lt 2 ]]; then
      finish_with_error "--run-cold-start-multi-device-smoke requires --cold-start-package and at least two --cold-start-device-id values."
    fi
  fi

  if [[ ${RUN_COLD_START_MIDRUN_DISCONNECT_SMOKE} -eq 1 ]]; then
    if [[ -z "${COLD_START_PACKAGE}" || ${#COLD_START_DEVICE_IDS[@]} -lt 2 || -z "${COLD_START_DISCONNECT_DEVICE_ID}" ]]; then
      finish_with_error "--run-cold-start-midrun-disconnect-smoke requires --cold-start-package, at least two --cold-start-device-id values, and --cold-start-disconnect-device-id."
    fi
  fi

  if [[ ${RUN_FOREGROUND_BACKGROUND_SMOKE} -eq 1 ]]; then
    if [[ -z "${FOREGROUND_BACKGROUND_PACKAGE}" || -z "${FOREGROUND_BACKGROUND_DEVICE_ID}" ]]; then
      finish_with_error "--run-foreground-background-smoke requires --foreground-background-package and --foreground-background-device-id."
    fi
  fi

  if [[ ${RUN_WEB_FOREGROUND_BACKGROUND_SMOKE} -eq 1 ]]; then
    if [[ -z "${FOREGROUND_BACKGROUND_PACKAGE}" || -z "${FOREGROUND_BACKGROUND_DEVICE_ID}" ]]; then
      finish_with_error "--run-web-foreground-background-smoke requires --foreground-background-package and --foreground-background-device-id."
    fi
  fi

  if [[ ${RUN_INSTALL_UNINSTALL_SMOKE} -eq 1 || ${RUN_WEB_INSTALL_UNINSTALL_SMOKE} -eq 1 ]]; then
    if [[ -z "${INSTALL_UNINSTALL_PACKAGE}" || -z "${INSTALL_UNINSTALL_APK_PATH}" || -z "${INSTALL_UNINSTALL_DEVICE_ID}" ]]; then
      finish_with_error "--run-install-uninstall-smoke/--run-web-install-uninstall-smoke require --install-uninstall-package, --install-uninstall-apk-path, and --install-uninstall-device-id."
    fi
    if [[ ! -f "${INSTALL_UNINSTALL_APK_PATH}" ]]; then
      finish_with_error "install_uninstall APK does not exist: ${INSTALL_UNINSTALL_APK_PATH}"
    fi
  fi

  if [[ ${RUN_REBOOT_SMOKE} -eq 1 || ${RUN_WEB_REBOOT_SMOKE} -eq 1 ]]; then
    if [[ -z "${REBOOT_PACKAGE}" || -z "${REBOOT_DEVICE_ID}" ]]; then
      finish_with_error "--run-reboot-smoke/--run-web-reboot-smoke require --reboot-package and --reboot-device-id."
    fi
  fi

  if [[ ${RUN_STANDBY_WAKE_SMOKE} -eq 1 || ${RUN_WEB_STANDBY_WAKE_SMOKE} -eq 1 ]]; then
    if [[ -z "${STANDBY_WAKE_PACKAGE}" || -z "${STANDBY_WAKE_DEVICE_ID}" ]]; then
      finish_with_error "--run-standby-wake-smoke/--run-web-standby-wake-smoke require --standby-wake-package and --standby-wake-device-id."
    fi
  fi

  if [[ ${RUN_MONKEY_SMOKE} -eq 1 ]]; then
    if [[ -z "${MONKEY_PACKAGE}" || -z "${MONKEY_DEVICE_ID}" ]]; then
      finish_with_error "--run-monkey-smoke requires --monkey-package and --monkey-device-id."
    fi
  fi

  if [[ ${RUN_MONKEY_MIDRUN_DISCONNECT_SMOKE} -eq 1 ]]; then
    if [[ -z "${MONKEY_PACKAGE}" || -z "${MONKEY_DEVICE_ID}" ]]; then
      finish_with_error "--run-monkey-midrun-disconnect-smoke requires --monkey-package and --monkey-device-id."
    fi
    if [[ "${MONKEY_DEVICE_ID}" != *:* ]]; then
      finish_with_error "--run-monkey-midrun-disconnect-smoke requires a TCP --monkey-device-id like HOST:PORT."
    fi
  fi
}

validate_real_smoke_args

run_step "unit_tests" "${PYTHON_BIN}" -m unittest discover -s tests -v
run_step "compileall" "${PYTHON_BIN}" -m compileall stability tests
run_step "cli_help" "${PYTHON_BIN}" -m stability.cli --help
run_step "list_devices_help" "${PYTHON_BIN}" -m stability.cli list-devices --help
run_step "show_device_help" "${PYTHON_BIN}" -m stability.cli show-device --help
run_step "list_tasks_help" "${PYTHON_BIN}" -m stability.cli list-tasks --help
run_step "show_task_help" "${PYTHON_BIN}" -m stability.cli show-task --help
run_step "list_runs_help" "${PYTHON_BIN}" -m stability.cli list-runs --help
run_step "show_run_help" "${PYTHON_BIN}" -m stability.cli show-run --help
run_step "bash_n_verify_extended_artifacts_smoke" bash -n scripts/verify_extended_artifacts_smoke.sh
run_step "bash_n_verify_cli_query_smoke" bash -n scripts/verify_cli_query_smoke.sh
run_step "bash_n_verify_cold_start_loop_smoke" bash -n scripts/verify_cold_start_loop_smoke.sh
run_step "bash_n_verify_cold_start_loop_multi_device_smoke" bash -n scripts/verify_cold_start_loop_multi_device_smoke.sh
run_step "bash_n_verify_cold_start_loop_midrun_disconnect_smoke" bash -n scripts/verify_cold_start_loop_midrun_disconnect_smoke.sh
run_step "bash_n_verify_foreground_background_loop_smoke" bash -n scripts/verify_foreground_background_loop_smoke.sh
run_step "bash_n_verify_web_tasks_foreground_background_smoke" bash -n scripts/verify_web_tasks_foreground_background_smoke.sh
run_step "bash_n_verify_install_uninstall_loop_smoke" bash -n scripts/verify_install_uninstall_loop_smoke.sh
run_step "bash_n_verify_web_tasks_install_uninstall_smoke" bash -n scripts/verify_web_tasks_install_uninstall_smoke.sh
run_step "bash_n_verify_reboot_loop_smoke" bash -n scripts/verify_reboot_loop_smoke.sh
run_step "bash_n_verify_web_tasks_reboot_loop_smoke" bash -n scripts/verify_web_tasks_reboot_loop_smoke.sh
run_step "bash_n_verify_standby_wake_loop_smoke" bash -n scripts/verify_standby_wake_loop_smoke.sh
run_step "bash_n_verify_web_tasks_standby_wake_smoke" bash -n scripts/verify_web_tasks_standby_wake_smoke.sh
run_step "bash_n_verify_monkey_smoke" bash -n scripts/verify_monkey_smoke.sh
run_step "bash_n_verify_monkey_midrun_disconnect_smoke" bash -n scripts/verify_monkey_midrun_disconnect_smoke.sh
run_step "bash_n_verify_v1_acceptance" bash -n scripts/verify_v1_acceptance.sh

LIST_RUNS_JSON="${OUTPUT_DIR}/list_runs.json"
LIST_RUNS_STDERR="${OUTPUT_DIR}/list_runs.stderr"
set +e
"${PYTHON_BIN}" -m stability.cli list-runs --limit 1 >"${LIST_RUNS_JSON}" 2>"${LIST_RUNS_STDERR}"
LIST_RUNS_STATUS=$?
set -e
if [[ ${LIST_RUNS_STATUS} -ne 0 ]]; then
  record_step "FAIL" "list_runs_sanity" "exit=${LIST_RUNS_STATUS}"
  finish_with_error "Persistent list-runs sanity check failed."
fi
record_step "PASS" "list_runs_sanity"

LIST_DEVICES_JSON="${OUTPUT_DIR}/list_devices.json"
LIST_DEVICES_STDERR="${OUTPUT_DIR}/list_devices.stderr"
set +e
"${PYTHON_BIN}" -m stability.cli list-devices >"${LIST_DEVICES_JSON}" 2>"${LIST_DEVICES_STDERR}"
LIST_DEVICES_STATUS=$?
set -e
if [[ ${LIST_DEVICES_STATUS} -ne 0 ]]; then
  record_step "FAIL" "list_devices_sanity" "exit=${LIST_DEVICES_STATUS}"
  finish_with_error "Persistent list-devices sanity check failed."
fi
record_step "PASS" "list_devices_sanity"

LIST_TASKS_JSON="${OUTPUT_DIR}/list_tasks.json"
LIST_TASKS_STDERR="${OUTPUT_DIR}/list_tasks.stderr"
set +e
"${PYTHON_BIN}" -m stability.cli list-tasks >"${LIST_TASKS_JSON}" 2>"${LIST_TASKS_STDERR}"
LIST_TASKS_STATUS=$?
set -e
if [[ ${LIST_TASKS_STATUS} -ne 0 ]]; then
  record_step "FAIL" "list_tasks_sanity" "exit=${LIST_TASKS_STATUS}"
  finish_with_error "Persistent list-tasks sanity check failed."
fi
record_step "PASS" "list_tasks_sanity"

RUN_COUNT="$(json_value "${LIST_RUNS_JSON}" run_count)"
FIRST_RUN_ID="$(json_value "${LIST_RUNS_JSON}" first_run_id)"
if [[ "${RUN_COUNT}" =~ ^[0-9]+$ ]] && [[ "${RUN_COUNT}" -gt 0 ]] && [[ -n "${FIRST_RUN_ID}" ]]; then
  run_step "show_run_sanity" "${PYTHON_BIN}" -m stability.cli show-run --run-id "${FIRST_RUN_ID}"
else
  record_step "SKIP" "show_run_sanity" "no persisted runs available"
fi

FIRST_DEVICE_ID="$("${PYTHON_BIN}" - "${LIST_DEVICES_JSON}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
devices = data.get("devices") or []
print(devices[0].get("device_id", "") if devices else "")
PY
)"
if [[ -n "${FIRST_DEVICE_ID}" ]]; then
  run_step "show_device_sanity" "${PYTHON_BIN}" -m stability.cli show-device --device-id "${FIRST_DEVICE_ID}"
else
  record_step "SKIP" "show_device_sanity" "no persisted devices available"
fi

FIRST_TASK_ID="$("${PYTHON_BIN}" - "${LIST_TASKS_JSON}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
tasks = data.get("tasks") or []
print(tasks[0].get("task_id", "") if tasks else "")
PY
)"
if [[ -n "${FIRST_TASK_ID}" ]]; then
  run_step "show_task_sanity" "${PYTHON_BIN}" -m stability.cli show-task --task-id "${FIRST_TASK_ID}"
else
  record_step "SKIP" "show_task_sanity" "no persisted tasks available"
fi

if [[ ${RUN_EXTENDED_ARTIFACTS_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_extended_artifacts_smoke.sh
    --package-name "${COLD_START_PACKAGE}"
    --device-id "${COLD_START_DEVICE_IDS[0]}"
  )
  if [[ -n "${COLD_START_LAUNCH_ACTIVITY}" ]]; then
    args+=(--launch-activity "${COLD_START_LAUNCH_ACTIVITY}")
  fi
  append_common_smoke_args args
  run_step "extended_artifacts_smoke" "${args[@]}"
fi

if [[ ${RUN_CLI_QUERY_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_cli_query_smoke.sh
    --package-name "${COLD_START_PACKAGE}"
    --device-id "${COLD_START_DEVICE_IDS[0]}"
  )
  if [[ -n "${COLD_START_LAUNCH_ACTIVITY}" ]]; then
    args+=(--launch-activity "${COLD_START_LAUNCH_ACTIVITY}")
  fi
  append_common_smoke_args args
  run_step "cli_query_smoke" "${args[@]}"
fi

if [[ ${RUN_COLD_START_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_cold_start_loop_smoke.sh
    --package-name "${COLD_START_PACKAGE}"
    --device-id "${COLD_START_DEVICE_IDS[0]}"
  )
  if [[ -n "${COLD_START_LAUNCH_ACTIVITY}" ]]; then
    args+=(--launch-activity "${COLD_START_LAUNCH_ACTIVITY}")
  fi
  append_common_smoke_args args
  run_step "cold_start_single_device_smoke" "${args[@]}"
fi

if [[ ${RUN_COLD_START_MULTI_DEVICE_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_cold_start_loop_multi_device_smoke.sh
    --package-name "${COLD_START_PACKAGE}"
  )
  for device_id in "${COLD_START_DEVICE_IDS[@]}"; do
    args+=(--device-id "${device_id}")
  done
  if [[ -n "${COLD_START_LAUNCH_ACTIVITY}" ]]; then
    args+=(--launch-activity "${COLD_START_LAUNCH_ACTIVITY}")
  fi
  append_common_smoke_args args
  run_step "cold_start_multi_device_smoke" "${args[@]}"
fi

if [[ ${RUN_COLD_START_MIDRUN_DISCONNECT_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_cold_start_loop_midrun_disconnect_smoke.sh
    --package-name "${COLD_START_PACKAGE}"
    --disconnect-device-id "${COLD_START_DISCONNECT_DEVICE_ID}"
  )
  for device_id in "${COLD_START_DEVICE_IDS[@]}"; do
    args+=(--device-id "${device_id}")
  done
  if [[ -n "${COLD_START_LAUNCH_ACTIVITY}" ]]; then
    args+=(--launch-activity "${COLD_START_LAUNCH_ACTIVITY}")
  fi
  append_common_smoke_args args
  run_step "cold_start_midrun_disconnect_smoke" "${args[@]}"
fi

if [[ ${RUN_FOREGROUND_BACKGROUND_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_foreground_background_loop_smoke.sh
    --package-name "${FOREGROUND_BACKGROUND_PACKAGE}"
    --device-id "${FOREGROUND_BACKGROUND_DEVICE_ID}"
  )
  if [[ -n "${FOREGROUND_BACKGROUND_LAUNCH_ACTIVITY}" ]]; then
    args+=(--launch-activity "${FOREGROUND_BACKGROUND_LAUNCH_ACTIVITY}")
  fi
  append_common_smoke_args args
  run_step "foreground_background_smoke" "${args[@]}"
fi

if [[ ${RUN_WEB_FOREGROUND_BACKGROUND_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_web_tasks_foreground_background_smoke.sh
    --package-name "${FOREGROUND_BACKGROUND_PACKAGE}"
    --device-id "${FOREGROUND_BACKGROUND_DEVICE_ID}"
    --port "${WEB_FOREGROUND_BACKGROUND_PORT}"
  )
  run_step "web_foreground_background_smoke" "${args[@]}"
fi

if [[ ${RUN_INSTALL_UNINSTALL_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_install_uninstall_loop_smoke.sh
    --package-name "${INSTALL_UNINSTALL_PACKAGE}"
    --apk-path "${INSTALL_UNINSTALL_APK_PATH}"
    --device-id "${INSTALL_UNINSTALL_DEVICE_ID}"
  )
  append_common_smoke_args args
  run_step "install_uninstall_smoke" "${args[@]}"
fi

if [[ ${RUN_WEB_INSTALL_UNINSTALL_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_web_tasks_install_uninstall_smoke.sh
    --package-name "${INSTALL_UNINSTALL_PACKAGE}"
    --apk-path "${INSTALL_UNINSTALL_APK_PATH}"
    --device-id "${INSTALL_UNINSTALL_DEVICE_ID}"
    --port "${WEB_INSTALL_UNINSTALL_PORT}"
  )
  run_step "web_install_uninstall_smoke" "${args[@]}"
fi

if [[ ${RUN_REBOOT_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_reboot_loop_smoke.sh
    --package-name "${REBOOT_PACKAGE}"
    --device-id "${REBOOT_DEVICE_ID}"
  )
  append_common_smoke_args args
  run_step "reboot_smoke" "${args[@]}"
fi

if [[ ${RUN_WEB_REBOOT_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_web_tasks_reboot_loop_smoke.sh
    --package-name "${REBOOT_PACKAGE}"
    --device-id "${REBOOT_DEVICE_ID}"
    --port "${WEB_REBOOT_PORT}"
  )
  run_step "web_reboot_smoke" "${args[@]}"
fi

if [[ ${RUN_STANDBY_WAKE_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_standby_wake_loop_smoke.sh
    --package-name "${STANDBY_WAKE_PACKAGE}"
    --device-id "${STANDBY_WAKE_DEVICE_ID}"
  )
  append_common_smoke_args args
  run_step "standby_wake_smoke" "${args[@]}"
fi

if [[ ${RUN_WEB_STANDBY_WAKE_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_web_tasks_standby_wake_smoke.sh
    --package-name "${STANDBY_WAKE_PACKAGE}"
    --device-id "${STANDBY_WAKE_DEVICE_ID}"
    --port "${WEB_STANDBY_WAKE_PORT}"
  )
  run_step "web_standby_wake_smoke" "${args[@]}"
fi

if [[ ${RUN_MONKEY_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_monkey_smoke.sh
    --package-name "${MONKEY_PACKAGE}"
    --device-id "${MONKEY_DEVICE_ID}"
  )
  append_common_smoke_args args
  run_step "monkey_smoke" "${args[@]}"
fi

if [[ ${RUN_MONKEY_MIDRUN_DISCONNECT_SMOKE} -eq 1 ]]; then
  args=(
    bash
    scripts/verify_monkey_midrun_disconnect_smoke.sh
    --package-name "${MONKEY_PACKAGE}"
    --device-id "${MONKEY_DEVICE_ID}"
  )
  append_common_smoke_args args
  run_step "monkey_midrun_disconnect_smoke" "${args[@]}"
fi

echo "- PASS: v1_acceptance" >>"${SUMMARY_FILE}"
echo
echo "V1 acceptance checks completed."
echo "Summary: ${SUMMARY_FILE}"
echo "Output directory: ${OUTPUT_DIR}"
