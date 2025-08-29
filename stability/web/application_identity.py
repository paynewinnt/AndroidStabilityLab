from __future__ import annotations

from typing import Any, Mapping
from stability.web.request_context import (
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


class ApplicationIdentityMixin:
    @staticmethod
    def _request_payload(
        *,
        method: str,
        body: bytes,
        content_type: str,
    ) -> dict[str, list[str]]:
        return parse_request_payload(method=method, body=body, content_type=content_type)

    def _request_context(
        self,
        *,
        query: dict[str, list[str]],
        form: dict[str, list[str]],
        headers: Mapping[str, str],
        client_address: str,
        method: str,
        route: str,
        strict_actor_resolution: bool = False,
    ) -> dict[str, Any]:
        current_actor = self._resolve_current_actor(
            query=query,
            headers=headers,
            strict=strict_actor_resolution,
        )
        return build_request_context(
            form=form,
            headers=headers,
            client_address=client_address,
            method=method,
            route=route,
            current_actor=current_actor,
            strict_actor_resolution=strict_actor_resolution,
            token_hint=self._token_hint,
        )

    @staticmethod
    def _request_id_from_headers(headers: Mapping[str, str]) -> str:
        return request_id_from_headers(headers)

    def _resolve_current_actor(
        self,
        *,
        query: Mapping[str, list[str]],
        headers: Mapping[str, str],
        strict: bool = False,
    ) -> dict[str, Any]:
        header_session_token = str(
            headers.get("X-ASL-Session-Token", "") or headers.get("x-asl-session-token", "") or ""
        ).strip()
        authorization_token = self._bearer_token(headers)
        cookie_session_token = self._cookie_value(headers, "asl_session").strip()
        query_session_token = self._str_query(dict(query), "as_session").strip()
        header_actor = str(headers.get("X-ASL-Actor", "") or headers.get("x-asl-actor", "") or "").strip()
        cookie_actor = self._cookie_value(headers, "asl_actor").strip()
        query_actor = self._str_query(dict(query), "as_actor").strip()
        sso_claims = self._trusted_sso_claims_from_headers(headers)
        sso_header_present = self._has_trusted_sso_headers(headers)
        session_candidates = (
            ("header:x-asl-session-token", header_session_token),
            ("header:authorization", authorization_token),
            ("cookie:asl_session", cookie_session_token),
            ("query:as_session", query_session_token),
        )
        direct_actor_candidates = (
            ("header:x-asl-actor", header_actor),
        )
        legacy_actor_candidates = (
            ("cookie:asl_actor", cookie_actor),
            ("query:as_actor", query_actor),
        )
        requested_actor_source = ""
        requested_actor = ""
        for source, actor_id in direct_actor_candidates + legacy_actor_candidates:
            if actor_id:
                requested_actor_source = source
                requested_actor = actor_id
                break
        requested_session_source = ""
        requested_session_token = ""
        for source, session_token in session_candidates:
            if session_token:
                requested_session_source = source
                requested_session_token = session_token
                break
        requested_source = requested_session_source or requested_actor_source
        if strict and (cookie_actor or query_actor):
            raise ValueError(
                "Writable requests do not accept cookie/query actor overrides. "
                "Use X-ASL-Actor or a stable session token instead."
            )
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "get_actor"):
            if sso_header_present:
                missing_claims = [
                    self._trusted_sso_headers[key]
                    for key in self._required_trusted_sso_claims
                    if not str(sso_claims.get(key, "") or "").strip()
                ]
                if missing_claims and strict:
                    raise ValueError(
                        "Writable requests with trusted SSO headers require: "
                        + ", ".join(missing_claims)
                        + ". Omit all SSO headers to use local session identity."
                    )
                if not missing_claims and hasattr(service, "resolve_sso_actor"):
                    try:
                        resolved = service.resolve_sso_actor(
                            sso_claims,
                            auth_mechanism="sso_header",
                            session_source="header:trusted_sso",
                        )
                    except Exception as exc:
                        if strict:
                            raise ValueError(f"Trusted SSO identity could not be resolved: {exc}") from exc
                    else:
                        return self._sso_actor_context(
                            resolved,
                            claims=sso_claims,
                            requested_actor_id=requested_actor,
                            requested_actor_source=requested_actor_source,
                            requested_session_token=requested_session_token,
                            requested_session_source=requested_session_source,
                        )
                elif strict:
                    raise ValueError(
                        "Writable requests with trusted SSO headers require collaboration_service.resolve_sso_actor."
                    )
            for source, session_token in session_candidates:
                if not session_token:
                    continue
                try:
                    actor = self._resolve_actor_from_session_token(session_token)
                except Exception:
                    continue
                return self._actor_context(
                    actor,
                    session_source=source,
                    identity_source_type="session_token",
                    auth_mechanism="session_token",
                    requested_actor_id=requested_actor,
                    requested_actor_source=requested_actor_source,
                    requested_session_token=session_token,
                    requested_session_source=source,
                )
            for source, actor_id in direct_actor_candidates:
                if not actor_id:
                    continue
                try:
                    actor = service.get_actor(actor_id)
                except Exception:
                    continue
                return self._actor_context(
                    actor,
                    session_source=source,
                    identity_source_type="header_actor",
                    auth_mechanism="header_actor",
                    requested_actor_id=actor_id,
                    requested_actor_source=source,
                    requested_session_token=requested_session_token,
                    requested_session_source=requested_session_source,
                )
            if not strict:
                for source, actor_id in legacy_actor_candidates:
                    if not actor_id:
                        continue
                    try:
                        actor = service.get_actor(actor_id)
                    except Exception:
                        continue
                    return self._actor_context(
                        actor,
                        session_source=source,
                        identity_source_type="legacy_actor_lookup",
                        auth_mechanism="legacy_actor_lookup",
                        requested_actor_id=actor_id,
                        requested_actor_source=source,
                        requested_session_token=requested_session_token,
                        requested_session_source=requested_session_source,
                    )
            if strict:
                if requested_source:
                    requested_value = requested_session_token or requested_actor
                    raise ValueError(f"Unknown current actor resolved from {requested_source}: {requested_value}")
                raise ValueError(
                    "Writable requests require a resolved identity from X-ASL-Actor or a stable session token "
                    "(X-ASL-Session-Token, Authorization Bearer, asl_session cookie, or as_session). "
                    "Query/cookie actor overrides are not accepted for POST."
                )
            actors = self._collaboration_actors()
            default_actor = next((item for item in actors if str(item.get("actor_id", "") or "") == "tester"), None)
            if default_actor is None and actors:
                default_actor = actors[0]
            if default_actor is not None:
                return {
                    **dict(default_actor),
                    "session_source": "default:collaboration_actor_registry",
                    "identity_source_type": "default_actor",
                    "auth_mechanism": "default_actor",
                    "session_token": self._session_token_for_actor(default_actor),
                    "session_id": self._session_id_for_actor(default_actor, auth_mechanism="default_actor"),
                    "session_expires_at": self._session_expires_at(self._session_token_for_actor(default_actor)),
                    "requested_actor_id": requested_actor,
                    "requested_actor_source": requested_actor_source,
                    "requested_session_token": requested_session_token,
                    "requested_session_source": requested_session_source,
                }
        if strict:
            if requested_source:
                requested_value = requested_session_token or requested_actor
                raise ValueError(f"Unknown current actor resolved from {requested_source}: {requested_value}")
            raise ValueError(
                "Writable requests require a resolved identity from X-ASL-Actor or a stable session token."
            )
        fallback_actor = query_actor or header_actor or cookie_actor or "tester"
        return {
            "actor_id": fallback_actor,
            "display_name": fallback_actor,
            "role_key": "",
            "permissions": [],
            "identity_id": self._identity_id_for_actor({"actor_id": fallback_actor, "role_key": ""}),
            "session_token": self._session_token_for_actor({"actor_id": fallback_actor, "role_key": ""}),
            "session_token_hint": self._token_hint(
                self._session_token_for_actor({"actor_id": fallback_actor, "role_key": ""})
            ),
            "identity_source_type": "default_fallback_actor",
            "auth_mechanism": "default_fallback_actor",
            "session_id": self._session_id_for_actor({"actor_id": fallback_actor, "role_key": ""}, auth_mechanism="default_fallback_actor"),
            "session_expires_at": self._session_expires_at(self._session_token_for_actor({"actor_id": fallback_actor, "role_key": ""})),
            "session_source": "default:fallback_actor",
            "requested_actor_id": requested_actor or fallback_actor,
            "requested_actor_source": requested_actor_source or "default:fallback_actor",
            "requested_session_token": requested_session_token,
            "requested_session_source": requested_session_source,
        }

    @staticmethod
    def _cookie_value(headers: Mapping[str, str], name: str) -> str:
        return cookie_value(headers, name)

    @staticmethod
    def _bearer_token(headers: Mapping[str, str]) -> str:
        return bearer_token(headers)

    @staticmethod
    def _header_value(headers: Mapping[str, str], name: str) -> str:
        return header_value(headers, name)

    def _has_trusted_sso_headers(self, headers: Mapping[str, str]) -> bool:
        return has_trusted_sso_headers(headers, self._trusted_sso_headers)

    def _trusted_sso_claims_from_headers(self, headers: Mapping[str, str]) -> dict[str, Any]:
        return trusted_sso_claims_from_headers(headers, self._trusted_sso_headers)

    @staticmethod
    def _split_header_claims(value: str) -> list[str]:
        return split_header_claims(value)

    def _resolve_actor_from_session_token(self, session_token: str) -> object:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "resolve_session_token"):
            return service.resolve_session_token(session_token)
        if service is not None and hasattr(service, "list_actors"):
            for actor in service.list_actors() or ():
                if self._session_token_for_actor(actor) == str(session_token or "").strip():
                    return actor
        raise ValueError(f"Unknown collaboration session token: {session_token}")

    def _actor_context(
        self,
        actor: object,
        *,
        session_source: str,
        identity_source_type: str,
        auth_mechanism: str,
        requested_actor_id: str = "",
        requested_actor_source: str = "",
        requested_session_token: str = "",
        requested_session_source: str = "",
    ) -> dict[str, Any]:
        actor_payload = dict(actor or {}) if isinstance(actor, Mapping) else {}
        actor_id = str(getattr(actor, "actor_id", "") or actor_payload.get("actor_id", "") or "")
        return {
            "actor_id": actor_id,
            "display_name": str(getattr(actor, "display_name", "") or actor_payload.get("display_name", "") or actor_id),
            "role_key": str(getattr(actor, "role_key", "") or actor_payload.get("role_key", "") or ""),
            "permissions": list(getattr(actor, "permissions", ()) or actor_payload.get("permissions", ()) or ()),
            "identity_id": self._identity_id_for_actor(actor),
            "session_token": self._session_token_for_actor(actor),
            "session_id": self._session_id_for_actor(
                actor,
                auth_mechanism=auth_mechanism,
                session_token=requested_session_token,
            ),
            "session_token_hint": self._token_hint(self._session_token_for_actor(actor)),
            "session_expires_at": self._session_expires_at(self._session_token_for_actor(actor)),
            "identity_source_type": identity_source_type,
            "auth_mechanism": auth_mechanism,
            "session_source": session_source,
            "requested_actor_id": requested_actor_id,
            "requested_actor_source": requested_actor_source,
            "requested_session_token": requested_session_token,
            "requested_session_source": requested_session_source,
        }

    def _sso_actor_context(
        self,
        resolved: object,
        *,
        claims: Mapping[str, Any],
        requested_actor_id: str = "",
        requested_actor_source: str = "",
        requested_session_token: str = "",
        requested_session_source: str = "",
    ) -> dict[str, Any]:
        payload = dict(resolved or {}) if isinstance(resolved, Mapping) else {}
        actor = payload.get("actor") or resolved
        if isinstance(actor, Mapping):
            actor_id = str(actor.get("actor_id", "") or "")
        else:
            actor_id = str(getattr(actor, "actor_id", "") or payload.get("actor_id", "") or "")
        service = getattr(self._bundle, "collaboration_service", None)
        if actor_id and (not hasattr(actor, "role_key")) and service is not None and hasattr(service, "get_actor"):
            try:
                actor = service.get_actor(actor_id)
            except Exception:
                pass
        identity = payload.get("identity")
        session = payload.get("session")
        audit_source = dict(payload.get("audit_source", {}) or {})
        auth_mechanism = str(
            audit_source.get("auth_mechanism", "")
            or getattr(identity, "auth_mechanism", "")
            or getattr(session, "auth_mechanism", "")
            or "sso_header"
        )
        session_source = str(
            payload.get("session_source", "")
            or getattr(session, "session_source", "")
            or getattr(identity, "session_source", "")
            or "header:trusted_sso"
        )
        external_subject_id = str(
            audit_source.get("external_subject_id", "")
            or getattr(identity, "external_subject_id", "")
            or claims.get("external_subject_id", "")
            or ""
        )
        context = self._actor_context(
            actor,
            session_source=session_source,
            identity_source_type="trusted_sso_header",
            auth_mechanism=auth_mechanism,
            requested_actor_id=requested_actor_id,
            requested_actor_source=requested_actor_source,
            requested_session_token=requested_session_token,
            requested_session_source=requested_session_source,
        )
        context["identity_id"] = self._identity_id_for_actor(actor)
        context["session_id"] = str(
            audit_source.get("resolved_session_id", "")
            or getattr(session, "session_id", "")
            or getattr(identity, "session_id", "")
            or self._session_id_for_actor(
                actor,
                auth_mechanism=auth_mechanism,
                session_token=external_subject_id,
            )
        )
        context["session_token"] = str(getattr(session, "session_token", "") or "")
        context["session_token_hint"] = self._token_hint(context.get("session_token", ""))
        context["session_expires_at"] = self._isoformat_or_none(getattr(session, "expires_at", None)) or ""
        context["identity_provider"] = str(
            audit_source.get("identity_provider", "")
            or getattr(identity, "provider", "")
            or claims.get("provider", "")
            or ""
        )
        context["external_identity_id"] = str(
            audit_source.get("external_identity_id", "")
            or getattr(identity, "identity_id", "")
            or payload.get("external_identity_id", "")
            or ""
        )
        context["external_subject_id"] = external_subject_id
        context["external_email"] = str(
            audit_source.get("external_email", "")
            or getattr(identity, "external_email", "")
            or claims.get("external_email", "")
            or ""
        )
        context["organization_id"] = str(
            audit_source.get("organization_id", "")
            or getattr(identity, "organization_id", "")
            or claims.get("organization_id", "")
            or ""
        )
        context["team_ids"] = list(
            audit_source.get("team_ids", [])
            or getattr(identity, "team_ids", ())
            or claims.get("team_ids", [])
            or []
        )
        context["role_claims"] = list(
            audit_source.get("role_claims", [])
            or getattr(identity, "role_claims", ())
            or claims.get("role_claims", [])
            or []
        )
        return context

    @classmethod
    def _identity_override_fields(cls, payload: Mapping[str, list[str]]) -> list[str]:
        return identity_override_fields(payload)

    def _session_expires_at(self, session_token: str) -> str:
        token = str(session_token or "").strip()
        if not token:
            return ""
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "resolve_session"):
            try:
                session = service.resolve_session(token)
            except Exception:
                return ""
            expires_at = getattr(session, "expires_at", None)
            return expires_at.isoformat() if expires_at else ""
        return ""

    @classmethod
    def _assert_no_identity_override_fields(cls, payload: Mapping[str, list[str]]) -> None:
        assert_no_identity_override_fields(payload)

    @staticmethod
    def _token_hint(value: object) -> str:
        token = str(value or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return f"len={len(token)}:{token}"
        return f"len={len(token)}:*{token[-8:]}"

    def _identity_id_for_actor(self, actor: object) -> str:
        actor_id = str(getattr(actor, "actor_id", None) or "")
        role_key = str(getattr(actor, "role_key", None) or "")
        if not actor_id and isinstance(actor, Mapping):
            actor_id = str(actor.get("actor_id", "") or "")
            role_key = str(actor.get("role_key", "") or "")
        if not actor_id:
            return ""
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "actor_identity_id"):
            try:
                return str(service.actor_identity_id(actor_id) or "")
            except Exception:
                pass
        normalized_role = role_key.strip() or "actor"
        return f"asl.identity.v1:{normalized_role}:{actor_id}"

    def _session_token_for_actor(self, actor: object) -> str:
        actor_id = str(getattr(actor, "actor_id", None) or "")
        role_key = str(getattr(actor, "role_key", None) or "")
        if not actor_id and isinstance(actor, Mapping):
            actor_id = str(actor.get("actor_id", "") or "")
            role_key = str(actor.get("role_key", "") or "")
        if not actor_id:
            return ""
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "actor_session_token"):
            try:
                return str(service.actor_session_token(actor_id) or "")
            except Exception:
                pass
        normalized_role = role_key.strip() or "actor"
        return f"asl.session.v1:{normalized_role}:{actor_id}"

    def _session_id_for_actor(
        self,
        actor: object,
        *,
        auth_mechanism: str = "",
        session_token: str = "",
    ) -> str:
        actor_id = str(getattr(actor, "actor_id", None) or "")
        if not actor_id and isinstance(actor, Mapping):
            actor_id = str(actor.get("actor_id", "") or "")
        if not actor_id:
            return ""
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "actor_session_id"):
            try:
                return str(
                    service.actor_session_id(
                        actor_id,
                        auth_mechanism=auth_mechanism,
                        session_token=session_token,
                    )
                    or ""
                )
            except Exception:
                pass
        raw = session_token.strip() or f"{auth_mechanism.strip() or 'actor'}:{actor_id}"
        return f"asl.session_id.v1:{self._token_hint(raw)}"

    def _current_actor_payload(
        self,
        *,
        request_context: Mapping[str, Any] | None,
        query: Mapping[str, list[str]],
    ) -> dict[str, Any]:
        current_actor = dict(dict(request_context or {}).get("current_actor", {}) or {})
        if current_actor:
            return current_actor
        return self._resolve_current_actor(query=dict(query), headers={})
