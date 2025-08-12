from __future__ import annotations

import json
from urllib.parse import urlencode

from .web_portal_bundles import bundle
from .web_portal_fakes_collaboration import _FakeCollaborationService
from .web_portal_fakes_core import default_runner_status, writable_bundle
from .web_portal_fakes_integration import (
    _FakeIntegrationOutboxService,
    _FakeReleaseSubmissionService,
)
from .web_portal_fakes_quality import _FakeQualityGateService
from .web_portal_missing_audit import bundle_with_missing_latest_audit


def post_json_or_skip(test_case, app, route: str, fields: dict[str, str], *, headers: dict[str, str] | None = None) -> dict[str, object]:
    status, content_type, body = app.handle_request(
        route,
        method="POST",
        body=urlencode(fields).encode("utf-8"),
        content_type="application/x-www-form-urlencoded",
        headers=headers or {"X-ASL-Actor": "tester"},
    )
    if status == 404:
        test_case.skipTest(f"{route} is not implemented yet")
    test_case.assertEqual(status, 200)
    test_case.assertIn("application/json", content_type)
    return json.loads(body.decode("utf-8"))


__all__ = (
    "bundle",
    "bundle_with_missing_latest_audit",
    "writable_bundle",
    "default_runner_status",
    "post_json_or_skip",
    "_FakeCollaborationService",
    "_FakeIntegrationOutboxService",
    "_FakeReleaseSubmissionService",
    "_FakeQualityGateService",
)
