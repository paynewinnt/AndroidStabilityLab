#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
HOST="127.0.0.1"
PORT="${PORT:-8032}"
TMP_DIR="$(mktemp -d "/tmp/android_stability_lab_web_portal_smoke_XXXXXX")"
SERVER_LOG="${TMP_DIR}/server.log"
HOME_HTML="${TMP_DIR}/home.html"
TASKS_HTML="${TMP_DIR}/tasks.html"
ISSUES_HTML="${TMP_DIR}/issues.html"
RUNNER_HTML="${TMP_DIR}/runner.html"
GOLDENS_HTML="${TMP_DIR}/goldens.html"
GOLDENS_DIFF_HTML="${TMP_DIR}/goldens_diff.html"
ADMISSION_HTML="${TMP_DIR}/admission.html"
ADMISSION_DETAIL_HTML="${TMP_DIR}/admission_detail.html"
HOME_JSON="${TMP_DIR}/home.json"
RUNNER_JSON="${TMP_DIR}/runner.json"
RUNNER_FILTERED_JSON="${TMP_DIR}/runner_filtered.json"
RUNNER_SEVERITY_FILTERED_JSON="${TMP_DIR}/runner_severity_filtered.json"
GOLDENS_JSON="${TMP_DIR}/goldens.json"
GOLDENS_DIFF_JSON="${TMP_DIR}/goldens_diff.json"
GOLDENS_DIFF_FILTERED_JSON="${TMP_DIR}/goldens_diff_filtered.json"
GOLDENS_DIFF_FIELD_FILTERED_JSON="${TMP_DIR}/goldens_diff_field_filtered.json"
ADMISSION_JSON="${TMP_DIR}/admission.json"
ADMISSION_DETAIL_JSON="${TMP_DIR}/admission_detail.json"
ADMISSION_DETAIL_FILTERED_JSON="${TMP_DIR}/admission_detail_filtered.json"
GOLDEN_CASE_DETAIL_HTML="${TMP_DIR}/golden_case_detail.html"
GOLDEN_CASE_DETAIL_JSON="${TMP_DIR}/golden_case_detail.json"
REVIEW_REPORT_HTML="${TMP_DIR}/review_report.html"
LATEST_AUDIT_JSON="${TMP_DIR}/latest_audit.json"
COMPARISON_REPORT_JSON="${TMP_DIR}/comparison_report.json"
GOLDENS_DIFF_RIGHT_PATH="${TMP_DIR}/golden_diff_right.json"
RUNNER_DIR="${ROOT_DIR}/runtime/unattended_runner"
RUNNER_LOCK_PATH="${RUNNER_DIR}/runner.lock"
RUNNER_STATUS_PATH="${RUNNER_DIR}/runner_status.json"
RUNNER_LOCK_BACKUP="${TMP_DIR}/runner.lock.bak"
RUNNER_STATUS_BACKUP="${TMP_DIR}/runner_status.json.bak"
PID=""

cleanup() {
  if [[ -n "${PID}" ]] && kill -0 "${PID}" >/dev/null 2>&1; then
    kill "${PID}" >/dev/null 2>&1 || true
    wait "${PID}" >/dev/null 2>&1 || true
  fi
  if [[ -f "${RUNNER_LOCK_BACKUP}" ]]; then
    cp "${RUNNER_LOCK_BACKUP}" "${RUNNER_LOCK_PATH}"
  else
    rm -f "${RUNNER_LOCK_PATH}"
  fi
  if [[ -f "${RUNNER_STATUS_BACKUP}" ]]; then
    cp "${RUNNER_STATUS_BACKUP}" "${RUNNER_STATUS_PATH}"
  else
    rm -f "${RUNNER_STATUS_PATH}"
  fi
}

trap cleanup EXIT

cd "${ROOT_DIR}"

mkdir -p "${RUNNER_DIR}"
if [[ -f "${RUNNER_LOCK_PATH}" ]]; then
  cp "${RUNNER_LOCK_PATH}" "${RUNNER_LOCK_BACKUP}"
fi
if [[ -f "${RUNNER_STATUS_PATH}" ]]; then
  cp "${RUNNER_STATUS_PATH}" "${RUNNER_STATUS_BACKUP}"
fi

"${PYTHON_BIN}" - <<'PY' "${RUNNER_LOCK_PATH}" "${RUNNER_STATUS_PATH}"
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

now = datetime.now(timezone.utc)
lock_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
lock_path.write_text(
    json.dumps(
        {
            "pid": 4242,
            "started_at": (now - timedelta(minutes=5)).isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
status_path.write_text(
    json.dumps(
        {
            "pid": 4242,
            "status": "running",
            "started_at": (now - timedelta(minutes=5)).isoformat(),
            "finished_at": None,
            "last_heartbeat_at": now.isoformat(),
            "interval_seconds": 60,
            "max_iterations": 0,
            "task_id": "runner-web-smoke",
            "force": False,
            "cycle_count": 4,
            "active_cycle_index": 5,
            "stopped_reason": "",
            "daily_report_paths": {
                "report_json_path": str(Path(lock_path).parent / "daily_reports" / now.date().isoformat() / "report.json"),
                "summary_markdown_path": str(Path(lock_path).parent / "daily_reports" / now.date().isoformat() / "summary.md")
            },
            "weekly_report_paths": {
                "report_json_path": str(Path(lock_path).parent / "weekly_reports" / f"{now.isocalendar().year}-W{now.isocalendar().week:02d}" / "report.json"),
                "summary_markdown_path": str(Path(lock_path).parent / "weekly_reports" / f"{now.isocalendar().year}-W{now.isocalendar().week:02d}" / "summary.md")
            },
            "latest_daily_report": {
                "report_date": now.date().isoformat(),
                "generated_at": now.isoformat(),
                "round_count": 4,
                "executed_round_count": 3,
                "failed_round_count": 1,
                "device_online_rate": 0.75,
                "failed_rate": 0.25,
                "offline_rate": 0.1,
                "recovery_success_rate": 0.5,
                "quarantined_device_count": 1,
                "top_issue_types": [{"issue_type": "device_offline", "count": 1}],
                "task_summaries": [{"task_id": "runner-web-smoke", "round_count": 4, "failed_round_count": 1}]
            },
            "latest_weekly_report": {
                "week_key": f"{now.isocalendar().year}-W{now.isocalendar().week:02d}",
                "anchor_date": now.date().isoformat(),
                "week_start_date": (now.date() - timedelta(days=now.date().weekday())).isoformat(),
                "week_end_date": (now.date() - timedelta(days=now.date().weekday()) + timedelta(days=6)).isoformat(),
                "generated_at": now.isoformat(),
                "round_count": 7,
                "executed_round_count": 5,
                "failed_round_count": 2,
                "active_day_count": 3,
                "device_online_rate": 0.8,
                "failed_rate": 0.286,
                "offline_rate": 0.143,
                "recovery_success_rate": 0.5,
                "quarantined_device_count": 1,
                "top_issue_types": [{"issue_type": "device_offline", "count": 2}],
                "daily_summaries": [{"report_date": now.date().isoformat(), "round_count": 4, "failed_round_count": 1}]
            },
            "last_patrol": {
                "generated_at": now.isoformat(),
                "task_count": 2,
                "due_task_count": 1,
                "executed_task_count": 1,
                "skipped_task_count": 1,
                "failed_rate": 0.25,
                "offline_rate": 0.1,
                "recovery_success_rate": 0.5,
                "quarantined_device_count": 1,
                "quarantine_probe_attempt_count": 1,
                "quarantine_probe_recovered_count": 1,
            },
            "recent_patrols": [
                {
                    "cycle_index": 2,
                    "finished_at": (now - timedelta(minutes=2)).isoformat(),
                    "executed_task_count": 1,
                    "failed_rate": 0.0,
                    "offline_rate": 0.0,
                    "recovery_success_rate": 1.0,
                    "quarantined_device_count": 0,
                },
                {
                    "cycle_index": 3,
                    "finished_at": (now - timedelta(minutes=1)).isoformat(),
                    "executed_task_count": 1,
                    "failed_rate": 0.0,
                    "offline_rate": 0.4,
                    "recovery_success_rate": 1.0,
                    "quarantined_device_count": 0,
                },
                {
                    "cycle_index": 4,
                    "finished_at": now.isoformat(),
                    "task_count": 2,
                    "due_task_count": 1,
                    "executed_task_count": 1,
                    "skipped_task_count": 1,
                    "failed_rate": 0.25,
                    "offline_rate": 0.1,
                    "recovery_success_rate": 0.5,
                    "quarantined_device_count": 1,
                },
            ],
            "lock_path": str(lock_path),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
PY

"${PYTHON_BIN}" - <<'PY' "${ROOT_DIR}/config/rule_replay_golden_samples.json" "${GOLDENS_DIFF_RIGHT_PATH}"
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
payload = json.loads(src.read_text(encoding="utf-8"))
payload["suite_version"] = "v2-web-diff-smoke"
payload["cases"][0]["description"] = payload["cases"][0]["description"] + " [web-diff-smoke]"
payload["cases"] = [
    item
    for item in payload["cases"]
    if item["case_id"] != "startup_timeout_guard_stays_unchanged_when_rules_match"
]
payload["cases"].append(
    {
        "case_id": "web_diff_added_case",
        "description": "Added by web diff smoke.",
        "issue_type": "device_offline",
        "layer": "identity_semantics",
        "expectation": "fingerprint_changed",
        "baseline_rules": {"fingerprint": {"version": "baseline-v1"}},
        "candidate_rules": {"fingerprint": {"version": "candidate-v1"}},
        "filters": {"package_name": "com.example.app", "issue_type": "device_offline"},
        "dataset": {
            "task": {
                "task_id": "task-web-diff",
                "task_name": "Web Diff Smoke",
                "template_type": "monkey",
                "target_app": {"package_name": "com.example.app"},
            },
            "run": {"run_id": "run-web-diff", "status": "failed", "created_at": "2025-07-22T19:00:00"},
            "instances": [
                {
                    "instance_id": "instance-web-diff",
                    "device_id": "device-web-diff",
                    "template_type": "monkey",
                    "issues": [
                        {
                            "issue_id": "issue-web-diff",
                            "issue_type": "device_offline",
                            "package_name": "com.example.app",
                            "raw_key": "transport:web-diff",
                        }
                    ],
                }
            ],
        },
        "expected": {"family_count": 1, "changed_family_count": 1, "change_summary": {"fingerprint_changed": 1}},
        "draft_metadata": {"source_run_id": "run-web-diff"},
    }
)
dst.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

"${PYTHON_BIN}" -m stability.cli serve-web --host "${HOST}" --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
PID=$!

for _ in $(seq 1 30); do
  if curl -fsS "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "http://${HOST}:${PORT}/" >"${HOME_HTML}"
curl -fsS "http://${HOST}:${PORT}/tasks" >"${TASKS_HTML}"
curl -fsS "http://${HOST}:${PORT}/issues" >"${ISSUES_HTML}"
curl -fsS "http://${HOST}:${PORT}/runner" >"${RUNNER_HTML}"
curl -fsS "http://${HOST}:${PORT}/goldens" >"${GOLDENS_HTML}"
curl -fsS "http://${HOST}:${PORT}/admission" >"${ADMISSION_HTML}"
curl -fsS "http://${HOST}:${PORT}/api/home" >"${HOME_JSON}"
curl -fsS "http://${HOST}:${PORT}/api/runner" >"${RUNNER_JSON}"
curl -fsS "http://${HOST}:${PORT}/api/runner?patrol_filter=failed" >"${RUNNER_FILTERED_JSON}"
curl -fsS "http://${HOST}:${PORT}/api/runner?severity_filter=critical" >"${RUNNER_SEVERITY_FILTERED_JSON}"
curl -fsS "http://${HOST}:${PORT}/api/goldens" >"${GOLDENS_JSON}"
curl -fsS "http://${HOST}:${PORT}/api/admission" >"${ADMISSION_JSON}"

GOLDENS_DIFF_HTML_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/goldens/diff?left_path={}&right_path={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe=""), urllib.parse.quote(sys.argv[3], safe="")))' "${PORT}" "config/rule_replay_golden_samples.json" "${GOLDENS_DIFF_RIGHT_PATH}")"
GOLDENS_DIFF_JSON_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/api/goldens/diff?left_path={}&right_path={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe=""), urllib.parse.quote(sys.argv[3], safe="")))' "${PORT}" "config/rule_replay_golden_samples.json" "${GOLDENS_DIFF_RIGHT_PATH}")"
GOLDENS_DIFF_FILTERED_JSON_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/api/goldens/diff?left_path={}&right_path={}&change_type=added&case_query={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe=""), urllib.parse.quote(sys.argv[3], safe=""), urllib.parse.quote(sys.argv[4], safe="")))' "${PORT}" "config/rule_replay_golden_samples.json" "${GOLDENS_DIFF_RIGHT_PATH}" "web_diff_added_case")"
GOLDENS_DIFF_FIELD_FILTERED_JSON_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/api/goldens/diff?left_path={}&right_path={}&changed_field={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe=""), urllib.parse.quote(sys.argv[3], safe=""), urllib.parse.quote(sys.argv[4], safe="")))' "${PORT}" "config/rule_replay_golden_samples.json" "${GOLDENS_DIFF_RIGHT_PATH}" "description")"

curl -fsS "${GOLDENS_DIFF_HTML_URL}" >"${GOLDENS_DIFF_HTML}"
curl -fsS "${GOLDENS_DIFF_JSON_URL}" >"${GOLDENS_DIFF_JSON}"
curl -fsS "${GOLDENS_DIFF_FILTERED_JSON_URL}" >"${GOLDENS_DIFF_FILTERED_JSON}"
curl -fsS "${GOLDENS_DIFF_FIELD_FILTERED_JSON_URL}" >"${GOLDENS_DIFF_FIELD_FILTERED_JSON}"

GOLDEN_CASE_ID="$("${PYTHON_BIN}" -c 'import json, sys; data=json.load(open(sys.argv[1], "r", encoding="utf-8")); items=data.get("cases", []); print(items[0]["case_id"] if items else "")' "${GOLDENS_JSON}")"

if [[ -n "${GOLDEN_CASE_ID}" ]]; then
  curl -fsS "http://${HOST}:${PORT}/goldens/case/${GOLDEN_CASE_ID}" >"${GOLDEN_CASE_DETAIL_HTML}"
  curl -fsS "http://${HOST}:${PORT}/api/goldens/case/${GOLDEN_CASE_ID}" >"${GOLDEN_CASE_DETAIL_JSON}"
fi

BASELINE_KEY="$("${PYTHON_BIN}" -c 'import json, sys; data=json.load(open(sys.argv[1], "r", encoding="utf-8")); items=data.get("baselines", []); print(items[0]["baseline_key"] if items else "")' "${ADMISSION_JSON}")"

if [[ -n "${BASELINE_KEY}" ]]; then
  curl -fsS "http://${HOST}:${PORT}/admission/baseline/${BASELINE_KEY}" >"${ADMISSION_DETAIL_HTML}"
  curl -fsS "http://${HOST}:${PORT}/api/admission/baseline/${BASELINE_KEY}" >"${ADMISSION_DETAIL_JSON}"
  curl -fsS "http://${HOST}:${PORT}/api/admission/baseline/${BASELINE_KEY}?comparison_only=1" >"${ADMISSION_DETAIL_FILTERED_JSON}"
fi

grep -q "Web 首页" "${HOME_HTML}"
grep -q "Runner 摘要卡" "${HOME_HTML}"
grep -q "Heartbeat Age(s)" "${HOME_HTML}"
grep -q "最近执行任务" "${HOME_HTML}"
grep -q "今日日报轮次" "${HOME_HTML}"
grep -q "今日日报失败轮次" "${HOME_HTML}"
grep -q "本周周报轮次" "${HOME_HTML}"
grep -q "本周周报失败轮次" "${HOME_HTML}"
grep -q "latest daily report" "${HOME_HTML}"
grep -q "latest weekly report" "${HOME_HTML}"
grep -q "继续查看完整巡检状态" "${HOME_HTML}"
grep -q "metric-ok" "${HOME_HTML}"
grep -q "metric-danger" "${HOME_HTML}"
grep -q "今日日报已经出现失败轮次或隔离设备" "${HOME_HTML}"
grep -q "打开 /runner" "${HOME_HTML}"
grep -q "查看 /api/runner" "${HOME_HTML}"
grep -q "任务大厅" "${TASKS_HTML}"
grep -q "问题中心" "${ISSUES_HTML}"
grep -q "后台巡检状态" "${RUNNER_HTML}"
grep -q "最新异常严重度" "${RUNNER_HTML}"
grep -q "严重" "${RUNNER_HTML}"
grep -q "最新心跳关联提示" "${RUNNER_HTML}"
grep -q "异常严重度分层" "${RUNNER_HTML}"
grep -q "任务影响范围：task_count=2 / due_task_count=1 / executed_task_count=1 / skipped_task_count=1" "${RUNNER_HTML}"
grep -q "跳到失败轮次过滤" "${RUNNER_HTML}"
grep -q "异常轮次快捷入口" "${RUNNER_HTML}"
grep -q "一键看失败轮次 (1)" "${RUNNER_HTML}"
grep -q "Golden Suite" "${GOLDENS_HTML}"
grep -q "Golden Suite Diff" "${GOLDENS_DIFF_HTML}"
grep -q "准入中心" "${ADMISSION_HTML}"
grep -q '"page": "home"' "${HOME_JSON}"
grep -q '"page": "runner"' "${RUNNER_JSON}"
grep -q '"page": "goldens"' "${GOLDENS_JSON}"
grep -q '"page": "golden_diff"' "${GOLDENS_DIFF_JSON}"
grep -q '"page": "admission"' "${ADMISSION_JSON}"
grep -q '"comparison_ready": true' "${GOLDENS_DIFF_JSON}"
grep -q '"diff_count": 3' "${GOLDENS_DIFF_JSON}"
grep -q "Runner 状态" "${RUNNER_HTML}"
grep -q "锁状态" "${RUNNER_HTML}"
grep -q "最近一轮 Patrol" "${RUNNER_HTML}"
grep -q "Latest Daily Report" "${RUNNER_HTML}"
grep -q "Latest Weekly Report" "${RUNNER_HTML}"
grep -q "日报日期" "${RUNNER_HTML}"
grep -q "周键" "${RUNNER_HTML}"
grep -q "最近 Patrol 历史" "${RUNNER_HTML}"
grep -q "严重度过滤" "${RUNNER_HTML}"
grep -q "全部严重度" "${RUNNER_HTML}"
grep -q "严重 (1)" "${RUNNER_HTML}"
grep -q "失败轮次" "${RUNNER_HTML}"
grep -q "展开异常详情" "${RUNNER_HTML}"
grep -q "runner.lock" "${RUNNER_HTML}"
grep -q '"status": "running"' "${RUNNER_JSON}"
grep -q '"lock_state": "active"' "${RUNNER_JSON}"
grep -q '"task_id": "runner-web-smoke"' "${RUNNER_JSON}"
grep -q '"latest_daily_report"' "${RUNNER_JSON}"
grep -q '"latest_weekly_report"' "${RUNNER_JSON}"
grep -q '"report_date":' "${RUNNER_JSON}"
grep -q '"week_key":' "${RUNNER_JSON}"
grep -q '"recent_patrols"' "${RUNNER_JSON}"
grep -q '"filter_counts"' "${RUNNER_JSON}"
grep -q '"latest_patrol_relation"' "${RUNNER_JSON}"
grep -q '"latest_patrol_severity": "严重"' "${RUNNER_JSON}"
grep -q '"severity"' "${RUNNER_JSON}"
grep -q '"level": "critical"' "${RUNNER_JSON}"
grep -q '"impact_message": "任务影响范围：task_count=2 / due_task_count=1 / executed_task_count=1 / skipped_task_count=1"' "${RUNNER_JSON}"
grep -q '"executed_task_count": 1' "${RUNNER_JSON}"
grep -q '"patrol_filter": "failed"' "${RUNNER_FILTERED_JSON}"
grep -q '"history_count_filtered": 1' "${RUNNER_FILTERED_JSON}"
grep -q '"severity_filter": "critical"' "${RUNNER_SEVERITY_FILTERED_JSON}"
grep -q '"history_count_filtered": 1' "${RUNNER_SEVERITY_FILTERED_JSON}"
grep -q '"level": "critical"' "${RUNNER_SEVERITY_FILTERED_JSON}"
grep -q "Changed Cases" "${GOLDENS_DIFF_HTML}"
grep -q "Diff 过滤" "${GOLDENS_DIFF_HTML}"
grep -q "搜索 case_id" "${GOLDENS_DIFF_HTML}"
grep -q "全部字段" "${GOLDENS_DIFF_HTML}"
grep -q "description" "${GOLDENS_DIFF_HTML}"
grep -q "字段差异摘要" "${GOLDENS_DIFF_HTML}"
grep -q "展开关键块摘要" "${GOLDENS_DIFF_HTML}"
grep -q "Baseline Rules" "${GOLDENS_DIFF_HTML}"
grep -q "Candidate Rules" "${GOLDENS_DIFF_HTML}"
grep -q "Filters" "${GOLDENS_DIFF_HTML}"
grep -q "Expected" "${GOLDENS_DIFF_HTML}"
grep -q "\[web-diff-smoke\]" "${GOLDENS_DIFF_HTML}"
grep -q "查看 Left Case" "${GOLDENS_DIFF_HTML}"
grep -q "查看 Right Case" "${GOLDENS_DIFF_HTML}"
grep -q '"change_type": "added"' "${GOLDENS_DIFF_FILTERED_JSON}"
grep -q '"case_query": "web_diff_added_case"' "${GOLDENS_DIFF_FILTERED_JSON}"
grep -q '"diff_count": 1' "${GOLDENS_DIFF_FILTERED_JSON}"
grep -q '"case_id": "web_diff_added_case"' "${GOLDENS_DIFF_FILTERED_JSON}"
grep -q '"changed_field": "description"' "${GOLDENS_DIFF_FIELD_FILTERED_JSON}"
grep -q '"diff_count": 1' "${GOLDENS_DIFF_FIELD_FILTERED_JSON}"
grep -q '"case_id": "crash_regroup_ignore_raw_key"' "${GOLDENS_DIFF_FIELD_FILTERED_JSON}"

if [[ -n "${GOLDEN_CASE_ID}" ]]; then
  grep -q "Golden Case" "${GOLDEN_CASE_DETAIL_HTML}"
  grep -q "Baseline Rules" "${GOLDEN_CASE_DETAIL_HTML}"
  grep -q "\"case_id\": \"${GOLDEN_CASE_ID}\"" "${GOLDEN_CASE_DETAIL_JSON}"
  grep -q '"page": "golden_case_detail"' "${GOLDEN_CASE_DETAIL_JSON}"
fi

if [[ -n "${BASELINE_KEY}" ]]; then
  grep -q "准入详情" "${ADMISSION_DETAIL_HTML}"
  grep -q "状态摘要" "${ADMISSION_DETAIL_HTML}"
  grep -q "Review" "${ADMISSION_DETAIL_HTML}"
  grep -q "Comparison" "${ADMISSION_DETAIL_HTML}"
  grep -q "href='#section-review-report'" "${ADMISSION_DETAIL_HTML}"
  grep -q "href='#section-comparison-reports'" "${ADMISSION_DETAIL_HTML}"
  grep -q "href='#section-latest-audit'" "${ADMISSION_DETAIL_HTML}"
  grep -q "href='#section-golden-suite'" "${ADMISSION_DETAIL_HTML}"
  grep -q "查看当前报告摘要" "${ADMISSION_DETAIL_HTML}"
  grep -q "查看 comparison reports" "${ADMISSION_DETAIL_HTML}"
  grep -q "查看 latest audit 摘要" "${ADMISSION_DETAIL_HTML}"
  grep -q "case_count_total" "${ADMISSION_DETAIL_HTML}"
  grep -q "Golden Suite" "${ADMISSION_DETAIL_HTML}"
  grep -q "Review Report HTML" "${ADMISSION_DETAIL_HTML}"
  grep -q "Latest Audit HTML" "${ADMISSION_DETAIL_HTML}"
  grep -q "Baseline History" "${ADMISSION_DETAIL_HTML}"
  grep -q "展开详情" "${ADMISSION_DETAIL_HTML}"
  grep -q "\"baseline_key\": \"${BASELINE_KEY}\"" "${ADMISSION_DETAIL_JSON}"
  grep -q '"page": "admission_detail"' "${ADMISSION_DETAIL_JSON}"
  grep -q '"status_summary"' "${ADMISSION_DETAIL_JSON}"
  grep -q '"status_actions"' "${ADMISSION_DETAIL_JSON}"
  grep -q '"golden_suite"' "${ADMISSION_DETAIL_JSON}"
  grep -q '"baseline_history"' "${ADMISSION_DETAIL_JSON}"
  grep -q '"comparison_only": true' "${ADMISSION_DETAIL_FILTERED_JSON}"

  REPORT_HTML_PATH="$("${PYTHON_BIN}" -c 'import json, sys; data=json.load(open(sys.argv[1], "r", encoding="utf-8")); print(data.get("report", {}).get("html_path", ""))' "${ADMISSION_DETAIL_JSON}")"
  LATEST_AUDIT_JSON_PATH="$("${PYTHON_BIN}" -c 'import json, sys; data=json.load(open(sys.argv[1], "r", encoding="utf-8")); print(data.get("latest_audit", {}).get("detail_path", ""))' "${ADMISSION_DETAIL_JSON}")"
  COMPARISON_JSON_PATH="$("${PYTHON_BIN}" -c 'import json, sys; data=json.load(open(sys.argv[1], "r", encoding="utf-8")); items=data.get("comparison_reports", []); print(items[0].get("detail_path", "") if items else "")' "${ADMISSION_DETAIL_JSON}")"
  REPORT_HTML_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/admission/view?path={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe="")))' "${PORT}" "${REPORT_HTML_PATH}")"
  LATEST_AUDIT_JSON_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/admission/view?path={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe="")))' "${PORT}" "${LATEST_AUDIT_JSON_PATH}")"

  curl -fsS "${REPORT_HTML_URL}" >"${REVIEW_REPORT_HTML}"
  curl -fsS "${LATEST_AUDIT_JSON_URL}" >"${LATEST_AUDIT_JSON}"

  grep -q "<html" "${REVIEW_REPORT_HTML}"
  grep -q '"action_counts"' "${LATEST_AUDIT_JSON}"
  if [[ -n "${COMPARISON_JSON_PATH}" ]]; then
    COMPARISON_JSON_URL="$("${PYTHON_BIN}" -c 'import sys, urllib.parse; print("http://127.0.0.1:{}/admission/view?path={}".format(sys.argv[1], urllib.parse.quote(sys.argv[2], safe="")))' "${PORT}" "${COMPARISON_JSON_PATH}")"
    curl -fsS "${COMPARISON_JSON_URL}" >"${COMPARISON_REPORT_JSON}"
    grep -q '"comparison_id"' "${COMPARISON_REPORT_JSON}"
  fi
fi

printf 'web_portal_smoke_dir=%s\n' "${TMP_DIR}"
printf 'server_log=%s\n' "${SERVER_LOG}"
printf 'home_html=%s\n' "${HOME_HTML}"
printf 'tasks_html=%s\n' "${TASKS_HTML}"
printf 'issues_html=%s\n' "${ISSUES_HTML}"
printf 'runner_html=%s\n' "${RUNNER_HTML}"
printf 'goldens_html=%s\n' "${GOLDENS_HTML}"
printf 'goldens_diff_html=%s\n' "${GOLDENS_DIFF_HTML}"
printf 'admission_html=%s\n' "${ADMISSION_HTML}"
printf 'admission_detail_html=%s\n' "${ADMISSION_DETAIL_HTML}"
printf 'home_json=%s\n' "${HOME_JSON}"
printf 'runner_json=%s\n' "${RUNNER_JSON}"
printf 'runner_severity_filtered_json=%s\n' "${RUNNER_SEVERITY_FILTERED_JSON}"
printf 'goldens_json=%s\n' "${GOLDENS_JSON}"
printf 'goldens_diff_json=%s\n' "${GOLDENS_DIFF_JSON}"
printf 'goldens_diff_filtered_json=%s\n' "${GOLDENS_DIFF_FILTERED_JSON}"
printf 'goldens_diff_field_filtered_json=%s\n' "${GOLDENS_DIFF_FIELD_FILTERED_JSON}"
printf 'admission_json=%s\n' "${ADMISSION_JSON}"
printf 'admission_detail_json=%s\n' "${ADMISSION_DETAIL_JSON}"
printf 'admission_detail_filtered_json=%s\n' "${ADMISSION_DETAIL_FILTERED_JSON}"
printf 'golden_case_detail_html=%s\n' "${GOLDEN_CASE_DETAIL_HTML}"
printf 'golden_case_detail_json=%s\n' "${GOLDEN_CASE_DETAIL_JSON}"
printf 'review_report_html=%s\n' "${REVIEW_REPORT_HTML}"
printf 'latest_audit_json=%s\n' "${LATEST_AUDIT_JSON}"
printf 'comparison_report_json=%s\n' "${COMPARISON_REPORT_JSON}"
printf 'baseline_key=%s\n' "${BASELINE_KEY}"
printf 'golden_case_id=%s\n' "${GOLDEN_CASE_ID}"
printf 'goldens_diff_right_path=%s\n' "${GOLDENS_DIFF_RIGHT_PATH}"
