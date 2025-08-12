#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _load_counter(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return int(payload.get("request_count", 0) or 0) if isinstance(payload, dict) else 0


def _save_counter(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request_count": count}, ensure_ascii=False), encoding="utf-8")


def _signature_valid(headers: dict[str, str], body: bytes, secret: str) -> bool:
    signature = headers.get("x-asl-signature", "")
    if not secret:
        expected = "sha256=" + hashlib.sha256(body).hexdigest()
    else:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
    return hmac.compare_digest(signature, expected)


def _feishu_signature_valid(body: Any, secret: str) -> bool:
    if not isinstance(body, dict):
        return False
    timestamp = str(body.get("timestamp", "") or "")
    signature = str(body.get("sign", "") or "")
    if not timestamp or not signature:
        return False
    string_to_sign = f"{timestamp}\n{secret}"
    expected = base64.b64encode(
        hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(signature, expected)


def _make_handler(args: argparse.Namespace):
    record_path = Path(args.record_path)
    state_path = Path(args.state_path or f"{args.record_path}.state")

    class MockIMReceiver(BaseHTTPRequestHandler):
        server_version = "ASLMockIMReceiver/1.0"

        def log_message(self, format: str, *values: object) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:
            if self.path == "/health":
                _json_response(
                    self,
                    200,
                    {
                        "status": "ok",
                        "receiver": args.consumer_id,
                        "request_count": _load_counter(state_path),
                    },
                )
                return
            _json_response(self, 404, {"error": "not_found"})

        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(content_length)
            headers = {str(key).lower(): str(value) for key, value in self.headers.items()}
            current_count = _load_counter(state_path) + 1
            _save_counter(state_path, current_count)
            try:
                parsed_body: Any = json.loads(body.decode("utf-8"))
            except Exception:
                parsed_body = body.decode("utf-8", errors="replace")
            record = {
                "received_at": datetime.now(timezone.utc).isoformat(),
                "request_index": current_count,
                "path": self.path,
                "headers": headers,
                "body": parsed_body,
                "signature_valid": _signature_valid(headers, body, args.secret),
                "feishu_signature_valid": _feishu_signature_valid(parsed_body, args.feishu_secret),
                "idempotency_key": headers.get("x-asl-idempotency-key", ""),
                "event_id": headers.get("x-asl-event-id", ""),
                "event_type": headers.get("x-asl-event-type", ""),
            }
            record_path.parent.mkdir(parents=True, exist_ok=True)
            with record_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
            if current_count <= int(args.fail_first):
                _json_response(
                    self,
                    int(args.failure_status),
                    {
                        "error": "forced_failure",
                        "request_index": current_count,
                        "consumer_id": args.consumer_id,
                    },
                )
                return
            _json_response(
                self,
                int(args.success_status),
                {
                    "receipt_id": f"{args.receipt_prefix}-{current_count}",
                    "consumer_id": args.consumer_id,
                    "received_event_id": headers.get("x-asl-event-id", ""),
                    "idempotency_key": headers.get("x-asl-idempotency-key", ""),
                },
            )

    return MockIMReceiver


def main() -> int:
    parser = argparse.ArgumentParser(description="Local mock IM receiver for ASL webhook smoke tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--record-path", required=True)
    parser.add_argument("--state-path", default="")
    parser.add_argument("--secret", default="")
    parser.add_argument("--feishu-secret", default="")
    parser.add_argument("--consumer-id", default="mock-im")
    parser.add_argument("--receipt-prefix", default="mock-im-receipt")
    parser.add_argument("--fail-first", type=int, default=0)
    parser.add_argument("--failure-status", type=int, default=500)
    parser.add_argument("--success-status", type=int, default=202)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), _make_handler(args))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
