from __future__ import annotations

from typing import Mapping
from urllib.parse import parse_qs, urlparse

from stability.domain import AppError, normalize_app_error
from stability.web.application_common import WebPortalApplication, bind_web_portal_application
from stability.web.request_context import (
    REQUIRED_TRUSTED_SSO_CLAIMS,
    TRUSTED_SSO_HEADERS,
    WRITABLE_IDENTITY_FORM_FIELDS,
    request_id_from_headers,
)
from stability.web.routes import is_api_route

from .application_helpers_admission import ApplicationAdmissionHelpersMixin
from .application_helpers_forms import ApplicationFormHelpersMixin
from .application_helpers_integration import ApplicationIntegrationHelpersMixin
from .application_identity import ApplicationIdentityMixin
from .application_runtime import ApplicationRuntimeMixin
from .feature_registry import dispatch_get, dispatch_post
from .features.admission.actions import AdmissionActionsMixin as ApplicationIssueAdmissionActionsMixin
from .features.admission.page import (
    AdmissionRecordPageMixin as ApplicationAdmissionRecordPagesMixin,
    GoldenAdmissionPageMixin as ApplicationGoldenAdmissionPagesMixin,
    QualityPageMixin as ApplicationQualityPagesMixin,
)
from .features.admission.payload import AdmissionWorkflowPayloadMixin as ApplicationPayloadAdmissionReportsMixin
from .features.collaboration.payload import CollaborationPayloadMixin as ApplicationPayloadCollaborationMixin
from .features.core.admin_components import AdminComponentsMixin as ApplicationAdminComponentsMixin
from .features.core.help_page import HelpPageMixin as ApplicationHelpPagesMixin
from .features.core.layout_page import LayoutPageMixin as ApplicationLayoutPagesMixin
from .features.core.page import CorePageMixin as ApplicationCorePagesMixin
from .features.core.payload import CorePayloadMixin as ApplicationPayloadCoreMixin
from .features.devices.actions import DevicesActionsMixin as ApplicationDeviceActionsMixin
from .features.devices.page import DevicesPageMixin as ApplicationDevicesPageMixin
from .features.devices.payload import DevicesPayloadMixin as ApplicationPayloadDevicesMixin
from .features.integration.actions import IntegrationActionsMixin as ApplicationIntegrationActionsMixin
from .features.integration.page import IntegrationPageMixin as ApplicationIntegrationPageMixin
from .features.integration.payload import IntegrationPayloadMixin as ApplicationPayloadQualityIntegrationMixin
from .features.performance.issues_page import PerformanceIssuesPageMixin as ApplicationPerformanceIssuesPagesMixin
from .features.performance.page import PerformancePageMixin as ApplicationPerformancePageMixin
from .features.performance.payload import PerformancePayloadMixin as ApplicationPerformancePayloadMixin
from .features.quick_adb.actions import QuickAdbActionsMixin as ApplicationQuickAdbActionsMixin
from .features.quick_adb.page import QuickAdbPageMixin as ApplicationQuickAdbPageMixin
from .features.quick_adb.payload import QuickAdbPayloadMixin as ApplicationQuickAdbPayloadMixin
from .features.runner.actions import RunnerActionsMixin as ApplicationRunnerActionsMixin
from .features.runner.page import (
    RunnerCardsPageMixin as ApplicationRunnerCardsPagesMixin,
    RunnerPageMixin as ApplicationRunnerPagesMixin,
)
from .features.runner.payload import RunnerPayloadMixin as ApplicationPayloadWorkflowsMixin
from .features.tasks.actions import TasksActionsMixin as ApplicationTaskActionsMixin
from .features.tasks.page import (
    TaskDetailPageMixin as ApplicationTaskIntegrationPagesMixin,
    TasksPageMixin as ApplicationRecordPagesMixin,
)
from .features.tasks.payload import TasksPayloadMixin as ApplicationTasksPayloadMixin
from .responses import ApplicationResponseMixin


class WebPortalApplication(
    ApplicationIdentityMixin,
    ApplicationAdminComponentsMixin,
    ApplicationPayloadCoreMixin,
    ApplicationRuntimeMixin,
    ApplicationTasksPayloadMixin,
    ApplicationPayloadDevicesMixin,
    ApplicationQuickAdbPayloadMixin,
    ApplicationPerformancePayloadMixin,
    ApplicationPayloadWorkflowsMixin,
    ApplicationPayloadCollaborationMixin,
    ApplicationPayloadAdmissionReportsMixin,
    ApplicationIssueAdmissionActionsMixin,
    ApplicationPayloadQualityIntegrationMixin,
    ApplicationDevicesPageMixin,
    ApplicationQuickAdbPageMixin,
    ApplicationCorePagesMixin,
    ApplicationRunnerPagesMixin,
    ApplicationRecordPagesMixin,
    ApplicationLayoutPagesMixin,
    ApplicationHelpPagesMixin,
    ApplicationRunnerCardsPagesMixin,
    ApplicationPerformancePageMixin,
    ApplicationPerformanceIssuesPagesMixin,
    ApplicationAdmissionRecordPagesMixin,
    ApplicationGoldenAdmissionPagesMixin,
    ApplicationQualityPagesMixin,
    ApplicationTaskIntegrationPagesMixin,
    ApplicationIntegrationPageMixin,
    ApplicationTaskActionsMixin,
    ApplicationQuickAdbActionsMixin,
    ApplicationRunnerActionsMixin,
    ApplicationDeviceActionsMixin,
    ApplicationIntegrationActionsMixin,
    ApplicationIntegrationHelpersMixin,
    ApplicationFormHelpersMixin,
    ApplicationResponseMixin,
    ApplicationAdmissionHelpersMixin,
):
    """Serve a lightweight HTML portal and matching JSON endpoints from the service layer."""

    _trusted_sso_headers = TRUSTED_SSO_HEADERS
    _required_trusted_sso_claims = REQUIRED_TRUSTED_SSO_CLAIMS
    _writable_identity_form_fields = WRITABLE_IDENTITY_FORM_FIELDS

    def __init__(self, bundle: object, *, title: str = "Android Stability Lab") -> None:
        self._bundle = bundle
        self._title = title

    def handle_request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str = "",
        headers: Mapping[str, str] | None = None,
        client_address: str = "",
    ) -> tuple[int, str, bytes]:
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            return self._json_response(405, {"error": "Method not allowed."})

        parsed = urlparse(path or "/")
        query = parse_qs(parsed.query, keep_blank_values=False)
        request_headers = {
            str(key): str(value)
            for key, value in dict(headers or {}).items()
            if str(key).strip()
        }
        request_id = request_id_from_headers(request_headers)
        route = parsed.path or "/"
        wants_json = is_api_route(route)

        try:
            form = self._request_payload(
                method=normalized_method,
                body=body or b"",
                content_type=content_type,
            )
            request_context = self._request_context(
                query=query,
                form=form,
                headers=request_headers,
                client_address=client_address,
                method=normalized_method,
                route=route,
                strict_actor_resolution=normalized_method == "POST",
            )

            if normalized_method == "POST":
                self._assert_no_identity_override_fields(form)
                if route == "/tasks/actions/upload-apk":
                    result = self._handle_apk_upload(body=body or b"", content_type=content_type)
                    return self._json_response(200, result)
                response = dispatch_post(self, route, query, form, request_context)
            else:
                response = dispatch_get(self, route, query, request_context)

            if response is not None:
                return response
            if wants_json:
                return self._json_response(404, {"error": "API endpoint not found.", "path": route})
            return self._html_response(404, self._render_not_found(route))
        except AppError as exc:
            error = exc.with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, f"{error.code}: {error.message}"))
        except PermissionError as exc:
            error = normalize_app_error(exc).with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, error.message))
        except ValueError as exc:
            error = normalize_app_error(exc).with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, error.message))
        except Exception as exc:  # pragma: no cover - defensive path for runtime failures
            error = normalize_app_error(exc).with_context(request_id=request_id)
            if wants_json:
                return self._json_response(error.http_status, self._app_error_payload(error, path=route))
            return self._html_response(error.http_status, self._render_error(route, error.message))


bind_web_portal_application(WebPortalApplication)


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
    from .server import serve_web_portal as _serve_web_portal

    _serve_web_portal(
        host=host,
        port=port,
        bundle=bundle,
        allow_remote_access=allow_remote_access,
        portal_mode=portal_mode,
        public_base_url=public_base_url,
        deployment_label=deployment_label,
    )
