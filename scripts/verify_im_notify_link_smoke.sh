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

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${OUTPUT_DIR:-/tmp/android_stability_lab_im_notify_smoke_${TIMESTAMP}}"
RUNTIME_DIR="${REPO_ROOT}/runtime/integration_outbox"
RUNTIME_BACKUP="${OUTPUT_DIR}/integration_outbox.backup"
RECEIVER_LOG="${OUTPUT_DIR}/mock_im_receiver.log"
RECEIVER_RECORDS="${OUTPUT_DIR}/mock_im_receiver.jsonl"
REGISTER_JSON="${OUTPUT_DIR}/register_im_webhook.json"
WORKER_JSON="${OUTPUT_DIR}/run_im_notify_worker.json"
SECOND_WORKER_JSON="${OUTPUT_DIR}/run_im_notify_worker_second.json"
OUTBOX_JSON="${OUTPUT_DIR}/outbox_events.json"
FAILURE_JSON="${OUTPUT_DIR}/failure_dead_letter_check.json"
IM_SECRET="${IM_SECRET:-local-im-smoke-secret}"
HOST="127.0.0.1"
PORT="${PORT:-}"
SERVER_PID=""

usage() {
  cat <<'EOF'
Usage:
  scripts/verify_im_notify_link_smoke.sh [--port PORT]

Verifies a local IM notification chain without a real IM endpoint:
  - register-im-webhook via CLI
  - run-im-notify-worker via CLI
  - signature headers and HMAC verification
  - idempotency key propagation
  - consumer receipt persistence
  - second-round deduplication
  - retry/dead-letter basics with the same mock receiver
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:-}"
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

mkdir -p "${OUTPUT_DIR}"

if [[ -z "${PORT}" ]]; then
  PORT="$("${PYTHON_BIN}" - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
fi

finish_with_error() {
  local message="$1"
  echo "${message}" >&2
  echo "Output directory: ${OUTPUT_DIR}" >&2
  if [[ -s "${RECEIVER_LOG}" ]]; then
    echo "Mock receiver log:" >&2
    cat "${RECEIVER_LOG}" >&2
  fi
  exit 1
}

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  rm -rf "${RUNTIME_DIR}"
  if [[ -d "${RUNTIME_BACKUP}" ]]; then
    mkdir -p "$(dirname "${RUNTIME_DIR}")"
    mv "${RUNTIME_BACKUP}" "${RUNTIME_DIR}"
  fi
}

trap cleanup EXIT

if [[ -d "${RUNTIME_DIR}" ]]; then
  mkdir -p "$(dirname "${RUNTIME_BACKUP}")"
  mv "${RUNTIME_DIR}" "${RUNTIME_BACKUP}"
fi
mkdir -p "${RUNTIME_DIR}"

"${PYTHON_BIN}" scripts/mock_im_receiver.py \
  --host "${HOST}" \
  --port "${PORT}" \
  --record-path "${RECEIVER_RECORDS}" \
  --secret "${IM_SECRET}" \
  --consumer-id "mock-im-smoke" \
  --receipt-prefix "im-smoke-receipt" \
  >"${RECEIVER_LOG}" 2>&1 &
SERVER_PID="$!"

"${PYTHON_BIN}" - "${HOST}" "${PORT}" <<'PY' || finish_with_error "Mock IM receiver did not become healthy."
import json
import sys
import time
from urllib.request import urlopen

host = sys.argv[1]
port = sys.argv[2]
url = f"http://{host}:{port}/health"
for _ in range(50):
    try:
        with urlopen(url, timeout=0.2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "ok":
            raise SystemExit(0)
    except Exception:
        time.sleep(0.1)
raise SystemExit(1)
PY

run_cli_command() {
  local label="$1"
  local stdout_path="$2"
  shift 2
  echo "[$label] ${PYTHON_BIN} -m stability.cli $*"
  local status=0
  set +e
  "${PYTHON_BIN}" -m stability.cli "$@" >"${stdout_path}" 2>"${stdout_path}.stderr"
  status=$?
  set -e
  if [[ ${status} -ne 0 ]]; then
    if [[ -s "${stdout_path}.stderr" ]]; then
      cat "${stdout_path}.stderr" >&2
    fi
    finish_with_error "[$label] Command failed with exit code ${status}."
  fi
}

run_cli_command "register-im-webhook" "${REGISTER_JSON}" \
  register-im-webhook \
  --name "IM Smoke" \
  --url "http://${HOST}:${PORT}/im" \
  --created-by "im-smoke" \
  --secret-hint "local smoke hmac" \
  --signing-secret "${IM_SECRET}" \
  --signature-key-id "im-smoke-v1"

"${PYTHON_BIN}" - "${REGISTER_JSON}" <<'PY' || finish_with_error "register-im-webhook output did not expose the expected IM contract."
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
webhook = payload["webhook"]
assert webhook["name"] == "IM Smoke"
assert webhook["delivery_channel"] == "im_notify"
assert webhook["delivery_contract_version"] == "asl.im_notify.v1"
assert webhook["signature_key_id"] == "im-smoke-v1"
assert "im delivery body follows asl.im_notify.v1" in webhook["security_rules"]
PY

"${PYTHON_BIN}" - <<'PY'
from stability.app import IntegrationOutboxService

service = IntegrationOutboxService(root_dir="runtime/integration_outbox")
service.publish_event(
    event_type="admission_case.updated",
    target_type="admission_case",
    target_id="baseline_im_smoke",
    created_by="im-smoke",
    session_source="scripts/verify_im_notify_link_smoke.sh",
    audit_source={"request_path": "local-smoke"},
    payload={
        "final_decision": "conditional_pass",
        "status": "approved_with_risk",
        "final_reviewer": "qa_lead",
        "comment": "local IM smoke notification",
    },
)
PY

run_cli_command "run-im-notify-worker" "${WORKER_JSON}" \
  run-im-notify-worker \
  --webhook-name "IM Smoke" \
  --limit-per-webhook 5 \
  --interval-seconds 0 \
  --max-rounds 1 \
  --stop-when-idle

"${PYTHON_BIN}" - "${WORKER_JSON}" "${RECEIVER_RECORDS}" "${RUNTIME_DIR}/events.json" "${IM_SECRET}" "${OUTBOX_JSON}" <<'PY' \
  || finish_with_error "Delivered IM notification did not satisfy signature/idempotency/receipt assertions."
import hashlib
import hmac
import json
import sys
from pathlib import Path

worker_path, records_path, events_path, secret, outbox_copy = sys.argv[1:]
worker = json.loads(Path(worker_path).read_text(encoding="utf-8"))
assert worker["mode"] == "im_notify_worker"
rounds = worker["delivery"].get("delivery_rounds") or []
aggregate = {
    "attempted_count": sum(int(item.get("attempted_count", 0) or 0) for item in rounds),
    "delivered_count": sum(int(item.get("delivered_count", 0) or 0) for item in rounds),
}
assert aggregate["attempted_count"] == 1, aggregate
assert aggregate["delivered_count"] == 1, aggregate
records = [
    json.loads(line)
    for line in Path(records_path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
assert len(records) == 1, records
record = records[0]
headers = record["headers"]
body = record["body"]
raw_body = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
expected_signature = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
assert record["signature_valid"] is True
assert headers["x-asl-signature"] == expected_signature
assert headers["x-asl-signature-alg"] == "hmac-sha256"
assert headers["x-asl-signature-key-id"] == "im-smoke-v1"
assert headers["x-asl-delivery-contract"] == "asl.webhook_delivery.v1"
assert headers["x-asl-callback-contract-version"] == "asl.webhook_callback.v1"
assert headers["x-asl-idempotency-key"].startswith("idem:")
assert body["contract_version"] == "asl.im_notify.v1"
assert body["delivery_channel"] == "im_notify"
assert body["event"]["idempotency_key"] == headers["x-asl-idempotency-key"]
assert body["original_payload"]["final_decision"] == "conditional_pass"
events = json.loads(Path(events_path).read_text(encoding="utf-8"))
Path(outbox_copy).write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
delivered = next(item for item in events if item["event_type"] == "admission_case.updated")
assert delivered["delivery_status"] == "delivered"
assert delivered["attempt_count"] == 1
assert delivered["idempotency_key"] == headers["x-asl-idempotency-key"]
assert delivered["consumer_receipts"], delivered
receipt = delivered["consumer_receipts"][0]
assert receipt["consumer_id"] == "mock-im-smoke"
assert receipt["consumer_receipt_id"] == "im-smoke-receipt-1"
assert receipt["idempotency_key"] == delivered["idempotency_key"]
PY

run_cli_command "run-im-notify-worker-second" "${SECOND_WORKER_JSON}" \
  run-im-notify-worker \
  --webhook-name "IM Smoke" \
  --limit-per-webhook 5 \
  --interval-seconds 0 \
  --max-rounds 1 \
  --stop-when-idle

"${PYTHON_BIN}" - "${SECOND_WORKER_JSON}" "${RECEIVER_RECORDS}" <<'PY' \
  || finish_with_error "Second IM worker round was not deduplicated by consumer receipt."
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rounds = payload["delivery"].get("delivery_rounds") or []
aggregate = {
    "attempted_count": sum(int(item.get("attempted_count", 0) or 0) for item in rounds),
    "deduplicated_count": sum(int(item.get("deduplicated_count", 0) or 0) for item in rounds),
}
assert aggregate["attempted_count"] == 0, aggregate
assert aggregate["deduplicated_count"] == 1, aggregate
records = [line for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines() if line.strip()]
assert len(records) == 1, records
PY

"${PYTHON_BIN}" - "${OUTPUT_DIR}" "${IM_SECRET}" "${FAILURE_JSON}" <<'PY' \
  || finish_with_error "Failure/dead-letter foundation check failed."
import json
import sys
from datetime import datetime
from pathlib import Path

from stability.app import IntegrationOutboxService

output_dir = Path(sys.argv[1])
secret = sys.argv[2]
failure_json = Path(sys.argv[3])
attempts: list[dict[str, object]] = []


def failing_transport(url: str, headers, body: bytes):
    attempts.append({"headers": dict(headers), "body": body.decode("utf-8")})
    return 500, '{"error":"forced_failure"}'


service = IntegrationOutboxService(
    root_dir=output_dir / "dead_letter_outbox",
    retry_delay_seconds=0,
    delivery_interval_seconds=0,
    dead_letter_threshold=2,
    retry_alert_threshold=1,
    delivery_transport=failing_transport,
)
service.publish_event(
    event_type="admission_case.updated",
    target_type="admission_case",
    target_id="baseline_dead_letter_smoke",
    created_by="im-smoke",
    payload={"final_decision": "fail", "status": "blocked"},
)
service.register_im_webhook(
    name="IM Dead Letter",
    url="http://127.0.0.1:9/im",
    created_by="im-smoke",
    signing_secret=secret,
)
first = service.deliver_pending_events(
    webhook_name="IM Dead Letter",
    limit=5,
    now=datetime(2025, 7, 24, 10, 0, 0),
)
second = service.deliver_pending_events(
    webhook_name="IM Dead Letter",
    limit=5,
    now=datetime(2025, 7, 24, 10, 0, 1),
)
events = service.list_events(limit=10)
event = next(item for item in events if item.event_type == "admission_case.updated")
alert = next(item for item in events if item.event_type == "outbox.retry_alert")
assert first["failed_count"] == 1, first
assert first["alert_emitted_count"] == 1, first
assert second["dead_lettered_count"] == 1, second
assert event.delivery_status == "dead_letter"
assert event.attempt_count == 2
assert event.dead_lettered_at is not None
assert "dead-letter threshold reached" in event.last_error
assert alert.delivery_status in {"pending", "retry_pending", "dead_letter"}
failure_json.write_text(
    json.dumps(
        {
            "first": first,
            "second": second,
            "event_status": event.delivery_status,
            "attempt_count": event.attempt_count,
            "alert_event_id": alert.event_id,
            "transport_attempt_count": len(attempts),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
PY

echo "IM notify smoke passed."
echo "Output directory: ${OUTPUT_DIR}"
echo "Registered webhook: ${REGISTER_JSON}"
echo "Worker output: ${WORKER_JSON}"
echo "Receiver records: ${RECEIVER_RECORDS}"
echo "Failure/dead-letter check: ${FAILURE_JSON}"
