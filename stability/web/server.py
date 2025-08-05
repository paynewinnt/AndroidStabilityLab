from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .application import WebPortalApplication


def serve_web_portal(
    *,
    host: str,
    port: int,
    bundle: object,
    allow_remote_access: bool = False,
    portal_mode: str = "local_ops_console",
    public_base_url: str = "",
    deployment_label: str = "",
) -> None:
    """Start a blocking HTTP server for the Web portal."""
    try:
        setattr(
            bundle,
            "web_portal_config",
            {
                "mode": WebPortalApplication._normalized_portal_mode(portal_mode),
                "bound_host": host,
                "bound_port": port,
                "allow_remote_access": bool(allow_remote_access),
                "public_base_url": str(public_base_url or "").strip(),
                "deployment_label": str(deployment_label or "").strip(),
            },
        )
    except Exception:
        pass
    app = WebPortalApplication(bundle)

    class _PortalRequestHandler(BaseHTTPRequestHandler):
        def _response_headers(self, request_id: str) -> dict[str, str]:
            return app._response_boundary_headers(request_id)

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            request_headers = {str(key): str(value) for key, value in self.headers.items()}
            request_id = WebPortalApplication._request_id_from_headers(request_headers)
            request_headers.setdefault("X-Request-ID", request_id)
            request_headers.setdefault("X-ASL-Request-ID", request_id)
            status, content_type, body = app.handle_request(
                self.path,
                method="GET",
                headers=request_headers,
                client_address=str(self.client_address[0] if self.client_address else ""),
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for key, value in self._response_headers(request_id).items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
            request_headers = {str(key): str(value) for key, value in self.headers.items()}
            request_id = WebPortalApplication._request_id_from_headers(request_headers)
            request_headers.setdefault("X-Request-ID", request_id)
            request_headers.setdefault("X-ASL-Request-ID", request_id)
            status, content_type, body = app.handle_request(
                self.path,
                method="POST",
                body=body_bytes,
                content_type=str(self.headers.get("Content-Type", "") or ""),
                headers=request_headers,
                client_address=str(self.client_address[0] if self.client_address else ""),
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for key, value in self._response_headers(request_id).items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
            return

    server = ThreadingHTTPServer((host, port), _PortalRequestHandler)
    try:
        server.serve_forever()
    finally:  # pragma: no cover - stdlib cleanup path
        server.server_close()
