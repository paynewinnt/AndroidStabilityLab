from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import mimetypes
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, quote, urlparse

from stability.domain import AppError, SamplingConfig, TaskDefinition, TaskTargetApp, TaskTemplateType, normalize_app_error
from stability.domain.value_objects import new_id
from stability.web.request_context import (
    REQUIRED_TRUSTED_SSO_CLAIMS,
    TRUSTED_SSO_HEADERS,
    WRITABLE_IDENTITY_FORM_FIELDS,
    assert_no_identity_override_fields,
    bearer_token,
    build_request_context,
    cookie_value,
    has_trusted_sso_headers,
    header_value,
    identity_override_fields,
    parse_request_payload,
    request_id_from_headers,
    split_header_claims,
    trusted_sso_claims_from_headers,
)
from stability.web import payloads as portal_payloads
from stability.web import renderers as portal_renderers
from stability.web.routes import (
    API_ADMISSION_BASELINE_PREFIX,
    API_ADMISSION_CASE_PREFIX,
    API_ADMISSION_REPORT_PREFIX,
    API_ARCHIVE_TASK_ROUTES,
    API_CONFIGURE_UNATTENDED_ROUTES,
    API_CREATE_RUN_ROUTES,
    API_CREATE_TASK_ROUTES,
    API_EXECUTE_RUN_ROUTES,
    API_GOLDEN_CASE_PREFIX,
    API_PATROL_UNATTENDED_ROUTES,
    API_RELEASE_SUBMISSION_DETAIL_PREFIX,
    API_REPLAY_DEAD_LETTERS_ROUTES,
    API_RUN_ARTIFACTS_PREFIX,
    API_RUN_DETAIL_PREFIX,
    API_RUN_INTEGRATION_WORKER_ROUTES,
    API_RUN_UNATTENDED_ROUND_ROUTES,
    API_SYNC_CI_DECISIONS_ROUTES,
    API_TASK_DETAIL_PREFIX,
    API_UNATTENDED_DETAIL_PREFIX,
    HTML_ADMISSION_BASELINE_PREFIX,
    HTML_ARCHIVE_TASK_ROUTES,
    HTML_CONFIGURE_UNATTENDED_ROUTES,
    HTML_CREATE_RUN_ROUTES,
    HTML_CREATE_TASK_ROUTES,
    HTML_EXECUTE_RUN_ROUTES,
    HTML_GOLDEN_CASE_PREFIX,
    HTML_PATROL_UNATTENDED_ROUTES,
    HTML_REPLAY_DEAD_LETTERS_ROUTES,
    HTML_RUN_ARTIFACTS_PREFIX,
    HTML_RUN_DETAIL_PREFIX,
    HTML_RUN_INTEGRATION_WORKER_ROUTES,
    HTML_RUN_UNATTENDED_ROUND_ROUTES,
    HTML_SYNC_CI_DECISIONS_ROUTES,
    HTML_TASK_DETAIL_PREFIX,
    HTML_UNATTENDED_DETAIL_PREFIX,
    is_api_route,
    route_in,
    route_value_after_prefix,
)


class _ApplicationClassReference:
    def __init__(self) -> None:
        self._target: type[object] | None = None

    def bind(self, target: type[object]) -> None:
        self._target = target

    def __getattr__(self, name: str) -> Any:
        if self._target is None:
            raise RuntimeError("WebPortalApplication is not bound yet.")
        return getattr(self._target, name)


WebPortalApplication = _ApplicationClassReference()


def bind_web_portal_application(target: type[object]) -> None:
    WebPortalApplication.bind(target)
