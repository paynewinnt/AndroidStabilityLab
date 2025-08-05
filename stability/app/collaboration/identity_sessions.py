from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from stability.domain import CollaborationActor, CollaborationSession
from stability.domain.collaboration_models import CollaborationExternalIdentity, CollaborationUserProfile
from stability.domain.value_objects import new_id, utcnow


class IdentitySessionsMixin:
    def list_external_identities(self) -> tuple[CollaborationExternalIdentity, ...]:
        identities = []
        for payload in self._load_identity_registry().values():
            if isinstance(payload, Mapping):
                identities.append(self._external_identity_from_payload(payload))
        return tuple(identities)

    def list_user_profiles(self) -> tuple[CollaborationUserProfile, ...]:
        profiles: dict[str, CollaborationUserProfile] = {}
        identities_by_actor: dict[str, list[CollaborationExternalIdentity]] = {}
        for identity in self.list_external_identities():
            identities_by_actor.setdefault(identity.actor_id, []).append(identity)
        for actor in self._actors.values():
            if actor.is_active:
                profiles[actor.actor_id] = self._user_profile_for_actor(
                    actor,
                    external_identities=tuple(identities_by_actor.pop(actor.actor_id, [])),
                )
        for actor_id, identities in identities_by_actor.items():
            identity = sorted(
                identities,
                key=lambda item: item.updated_at or item.created_at or datetime.min,
                reverse=True,
            )[0]
            profiles[actor_id] = self._user_profile_for_external_identity(identity, external_identities=tuple(identities))
        return tuple(sorted(profiles.values(), key=lambda item: (item.display_name.lower(), item.actor_id)))

    def get_user_profile(self, profile_id: str) -> CollaborationUserProfile:
        key = str(profile_id or "").strip()
        if not key:
            raise ValueError("profile_id is required.")
        for profile in self.list_user_profiles():
            if key in {profile.profile_id, profile.actor_id, profile.identity_id}:
                return profile
        raise ValueError(f"Unknown collaboration user profile: {key}")

    def sync_user_profile_from_sso(
        self,
        claims: Mapping[str, Any],
        *,
        auth_mechanism: str = "sso_header",
        session_source: str = "header:sso",
        ttl_seconds: int | None = None,
    ) -> CollaborationUserProfile:
        resolved = self.resolve_sso_actor(
            claims,
            auth_mechanism=auth_mechanism,
            session_source=session_source,
            ttl_seconds=ttl_seconds,
        )
        return resolved["user_profile"]

    def actor_identity_id(self, actor_id: str) -> str:
        return self._identity_id_for_actor(self.get_actor(actor_id))

    def actor_session_token(self, actor_id: str) -> str:
        return self.issue_session(actor_id, issued_by="system").session_token

    def actor_session_id(
        self,
        actor_id: str,
        *,
        auth_mechanism: str = "",
        session_token: str = "",
    ) -> str:
        if session_token.strip():
            resolved = self.resolve_session(session_token)
            return resolved.session_id
        return self._session_id_for_actor(
            self.get_actor(actor_id),
            auth_mechanism=auth_mechanism,
            session_token=session_token,
        )

    def resolve_session_token(self, session_token: str) -> CollaborationActor:
        return self.get_actor(self.resolve_session(session_token).actor_id)

    def issue_session(
        self,
        actor_id: str,
        *,
        issued_by: str = "",
        ttl_seconds: int | None = None,
        auth_mechanism: str = "issued_session",
        session_source: str = "collaboration_service.issue_session",
    ) -> CollaborationSession:
        actor = self.get_actor(actor_id)
        existing = self._active_session_for_actor(actor.actor_id)
        current_time = utcnow()
        if existing is not None and not self._session_expiring(existing, current_time):
            return existing
        ttl = max(int(ttl_seconds or self._default_session_ttl_seconds), 60)
        raw = f"{self._issued_session_namespace}:{actor.role_key}:{actor.actor_id}:{new_id('session')}"
        session = CollaborationSession(
            session_token=raw,
            session_id=self._session_id_for_token(raw),
            actor_id=actor.actor_id,
            identity_id=self._identity_id_for_actor(actor),
            auth_mechanism=str(auth_mechanism or "issued_session"),
            issued_at=current_time,
            expires_at=current_time + timedelta(seconds=ttl),
            issued_by=str(issued_by or actor.actor_id or "system"),
            permission_scope=tuple(actor.permissions),
            session_source=str(session_source or "collaboration_service.issue_session"),
        )
        self._save_session(session)
        return session

    def resolve_sso_actor(
        self,
        claims: Mapping[str, Any],
        *,
        auth_mechanism: str = "sso_header",
        session_source: str = "header:sso",
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Register or resolve an actor from trusted SSO claims.

        The returned audit source can be passed to existing action methods; those
        methods continue to enforce the collaboration permission matrix.
        """

        identity = self._external_identity_from_claims(
            claims,
            auth_mechanism=auth_mechanism,
            session_source=session_source,
        )
        actor = self._actor_for_external_identity(identity)
        session = self._issue_sso_session(
            identity=identity,
            actor=actor,
            claims=claims,
            auth_mechanism=auth_mechanism,
            session_source=session_source,
            ttl_seconds=ttl_seconds,
        )
        identity = replace(identity, session_id=session.session_id, updated_at=utcnow())
        self._save_external_identity(identity)
        user_profile = self._user_profile_for_actor(actor, external_identities=(identity,))
        return {
            "actor": actor,
            "identity": identity,
            "session": session,
            "user_profile": user_profile,
            "actor_id": actor.actor_id,
            "actor_identity_id": identity.identity_id,
            "session_source": session.session_source,
            "audit_source": self._audit_source_for_external_identity(identity, session),
        }

    def revoke_session(
        self,
        session_token: str,
        *,
        revoked_by: str,
        reason: str = "",
    ) -> CollaborationSession:
        session = self.resolve_session(session_token)
        if session.revoked_at is not None:
            return session
        updated = replace(
            session,
            revoked_at=utcnow(),
            revoked_by=str(revoked_by or "system"),
            revoke_reason=str(reason or "").strip(),
        )
        self._save_session(updated)
        return updated

    def resolve_session(self, session_token: str) -> CollaborationSession:
        token = str(session_token or "").strip()
        if not token:
            raise ValueError("session_token is required.")
        payload = self._load_session_registry().get(token)
        if isinstance(payload, Mapping):
            session = self._session_from_payload(payload)
            if session.revoked_at is not None:
                raise PermissionError(f"Session revoked: {token}")
            if session.expires_at is not None and session.expires_at <= utcnow():
                raise PermissionError(f"Session expired: {token}")
            self.get_actor(session.actor_id)
            return session
        for actor in self._actors.values():
            if actor.is_active and self._session_token_for_actor(actor) == token:
                migrated = CollaborationSession(
                    session_token=token,
                    session_id=self._session_id_for_token(token),
                    actor_id=actor.actor_id,
                    identity_id=self._identity_id_for_actor(actor),
                    auth_mechanism="legacy_static_session_migrated",
                    issued_at=utcnow(),
                    expires_at=utcnow() + timedelta(seconds=self._default_session_ttl_seconds),
                    issued_by="system",
                    permission_scope=tuple(actor.permissions),
                    session_source="collaboration_service.legacy_session_migration",
                )
                self._save_session(migrated)
                return migrated
        raise ValueError(f"Unknown collaboration session token: {token}")

    def get_actor(self, actor_id: str) -> CollaborationActor:
        key = actor_id.strip()
        if not key:
            raise ValueError("actor_id is required.")
        actor = self._actors.get(key)
        if actor is None or not actor.is_active:
            raise ValueError(f"Unknown collaboration actor: {key}")
        return actor

    def authorize_action(
        self,
        *,
        actor_id: str,
        actor_identity_id: str = "",
        permission: str,
        audit_source: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission=permission,
            audit_source=audit_source,
        )
        return {
            "actor": actor,
            "audit_source": audit_payload,
        }

    def _require_permission(self, *, actor_id: str, permission: str) -> tuple[CollaborationActor, dict[str, Any]]:
        actor = self.get_actor(actor_id)
        policy = dict(self._permission_policies.get(permission, {}) or {})
        if permission not in set(actor.permissions):
            raise PermissionError(f"Actor '{actor.actor_id}' cannot perform '{permission}'.")
        allowed_roles = {str(item).strip() for item in policy.get("allowed_roles", ()) if str(item).strip()}
        if allowed_roles and actor.role_key not in allowed_roles:
            raise PermissionError(
                f"Actor '{actor.actor_id}' role '{actor.role_key}' is outside permission boundary for '{permission}'."
            )
        permission_check_id = self._permission_check_id(actor_id=actor.actor_id, permission=permission)
        return actor, {
            "permission_check_id": permission_check_id,
            "required_permission": permission,
            "permission_boundary": "collaboration_permission_matrix_v1",
            "permission_check_status": "granted",
            "permission_grant_source": "actor_permissions_and_policy",
            "permission_policy": policy,
        }

    def _authorize_actor(
        self,
        *,
        actor_id: str,
        actor_identity_id: str,
        permission: str,
        audit_source: Mapping[str, Any] | None,
    ) -> tuple[CollaborationActor, dict[str, Any]]:
        actor, permission_payload = self._require_permission(actor_id=actor_id, permission=permission)
        audit_payload = self._audit_source_with_identity(
            actor=actor,
            actor_identity_id=actor_identity_id,
            audit_source=audit_source,
        )
        audit_payload.update(permission_payload)
        return actor, audit_payload

    def _user_profile_for_actor(
        self,
        actor: CollaborationActor,
        *,
        external_identities: Sequence[CollaborationExternalIdentity] = (),
    ) -> CollaborationUserProfile:
        identities = tuple(external_identities)
        latest_identity = self._latest_external_identity(identities)
        if latest_identity is None:
            return CollaborationUserProfile(
                profile_id=self._identity_id_for_actor(actor),
                actor_id=actor.actor_id,
                identity_id=self._identity_id_for_actor(actor),
                display_name=actor.display_name,
                role_key=actor.role_key,
                permissions=tuple(actor.permissions),
                source="collaboration_actor_registry",
                is_active=actor.is_active,
            )
        role_key = actor.role_key or self._role_key_from_claims(latest_identity.role_claims)
        permissions = tuple(actor.permissions or self._roles.get(role_key, self._roles["observer"]).permissions)
        return CollaborationUserProfile(
            profile_id=latest_identity.identity_id,
            actor_id=actor.actor_id,
            identity_id=latest_identity.identity_id,
            display_name=latest_identity.external_display_name or actor.display_name,
            role_key=role_key,
            permissions=permissions,
            email=latest_identity.external_email,
            organization_id=latest_identity.organization_id,
            team_ids=tuple(latest_identity.team_ids),
            external_identities=identities,
            last_seen_at=latest_identity.updated_at,
            source="trusted_sso_organization",
            is_active=actor.is_active,
        )

    def _user_profile_for_external_identity(
        self,
        identity: CollaborationExternalIdentity,
        *,
        external_identities: Sequence[CollaborationExternalIdentity] = (),
    ) -> CollaborationUserProfile:
        role_key = self._role_key_from_claims(identity.role_claims)
        actor = self._actors.get(identity.actor_id)
        if actor is not None:
            return self._user_profile_for_actor(actor, external_identities=external_identities)
        permissions = tuple(self._roles[role_key].permissions)
        return CollaborationUserProfile(
            profile_id=identity.identity_id,
            actor_id=identity.actor_id,
            identity_id=identity.identity_id,
            display_name=identity.external_display_name or identity.external_email,
            role_key=role_key,
            permissions=permissions,
            email=identity.external_email,
            organization_id=identity.organization_id,
            team_ids=tuple(identity.team_ids),
            external_identities=tuple(external_identities or (identity,)),
            last_seen_at=identity.updated_at,
            source="trusted_sso_organization",
            is_active=True,
        )

    @staticmethod
    def _latest_external_identity(
        identities: Sequence[CollaborationExternalIdentity],
    ) -> CollaborationExternalIdentity | None:
        if not identities:
            return None
        return sorted(
            identities,
            key=lambda item: item.updated_at or item.created_at or datetime.min,
            reverse=True,
        )[0]

    def _external_identity_from_claims(
        self,
        claims: Mapping[str, Any],
        *,
        auth_mechanism: str,
        session_source: str,
    ) -> CollaborationExternalIdentity:
        if not isinstance(claims, Mapping):
            raise ValueError("SSO claims must be a mapping.")
        provider = self._claim_text(claims, "provider", "identity_provider", "iss")
        external_subject_id = self._claim_text(claims, "external_subject_id", "sub", "subject")
        external_email = self._claim_text(claims, "external_email", "email")
        external_display_name = self._claim_text(claims, "external_display_name", "display_name", "name") or external_email
        organization_id = self._claim_text(claims, "organization_id", "org_id", "organization")
        if not provider:
            raise ValueError("SSO provider is required.")
        if not external_subject_id:
            raise ValueError("SSO external_subject_id is required.")
        if not external_email:
            raise ValueError("SSO external_email is required.")
        if not organization_id:
            raise PermissionError("SSO organization_id is required.")
        if self._trusted_organization_ids and organization_id not in self._trusted_organization_ids:
            raise PermissionError(f"SSO organization '{organization_id}' is outside the trusted organization boundary.")

        identity_id = self._identity_id_for_external_subject(
            provider=provider,
            external_subject_id=external_subject_id,
        )
        actor_id = self._actor_id_for_external_subject(
            provider=provider,
            external_subject_id=external_subject_id,
        )
        existing_payload = self._load_identity_registry().get(identity_id)
        created_at = utcnow()
        if isinstance(existing_payload, Mapping):
            existing = self._external_identity_from_payload(existing_payload)
            if existing.organization_id != organization_id:
                raise PermissionError(
                    f"SSO organization mismatch for external identity '{identity_id}': {organization_id}"
                )
            created_at = existing.created_at or created_at
        return CollaborationExternalIdentity(
            identity_id=identity_id,
            actor_id=actor_id,
            provider=provider,
            external_subject_id=external_subject_id,
            external_email=external_email,
            external_display_name=external_display_name,
            organization_id=organization_id,
            team_ids=self._claim_sequence(claims, "team_ids", "teams", "groups"),
            role_claims=self._claim_sequence(claims, "role_claims", "roles", "role"),
            auth_mechanism=str(auth_mechanism or "sso_header"),
            session_id=str(self._claim_text(claims, "session_id", "sid", "sso_session_id") or ""),
            session_source=str(session_source or "header:sso"),
            created_at=created_at,
            updated_at=utcnow(),
        )

    def _actor_for_external_identity(self, identity: CollaborationExternalIdentity) -> CollaborationActor:
        role_key = self._role_key_from_claims(identity.role_claims)
        permissions = tuple(self._roles[role_key].permissions)
        actor = CollaborationActor(
            actor_id=identity.actor_id,
            display_name=identity.external_display_name or identity.external_email,
            role_key=role_key,
            permissions=permissions,
            is_active=True,
        )
        self._actors[actor.actor_id] = actor
        return actor

    def _issue_sso_session(
        self,
        *,
        identity: CollaborationExternalIdentity,
        actor: CollaborationActor,
        claims: Mapping[str, Any],
        auth_mechanism: str,
        session_source: str,
        ttl_seconds: int | None,
    ) -> CollaborationSession:
        current_time = utcnow()
        ttl = max(int(ttl_seconds or self._default_session_ttl_seconds), 60)
        external_session_id = self._claim_text(claims, "session_id", "sid", "sso_session_id") or identity.identity_id
        token = self._sso_session_token(
            provider=identity.provider,
            organization_id=identity.organization_id,
            external_subject_id=identity.external_subject_id,
            external_session_id=external_session_id,
        )
        session = CollaborationSession(
            session_token=token,
            session_id=self._session_id_for_token(token),
            actor_id=actor.actor_id,
            identity_id=identity.identity_id,
            auth_mechanism=str(auth_mechanism or "sso_header"),
            issued_at=current_time,
            expires_at=current_time + timedelta(seconds=ttl),
            issued_by=identity.provider,
            permission_scope=tuple(actor.permissions),
            session_source=str(session_source or "header:sso"),
            identity_provider=identity.provider,
            external_subject_id=identity.external_subject_id,
            organization_id=identity.organization_id,
        )
        self._save_session(session)
        return session

    def _audit_source_for_external_identity(
        self,
        identity: CollaborationExternalIdentity,
        session: CollaborationSession,
    ) -> dict[str, Any]:
        return {
            "auth_mechanism": identity.auth_mechanism,
            "identity_provider": identity.provider,
            "organization_id": identity.organization_id,
            "external_subject_id": identity.external_subject_id,
            "external_email": identity.external_email,
            "external_display_name": identity.external_display_name,
            "team_ids": list(identity.team_ids),
            "role_claims": list(identity.role_claims),
            "resolved_identity_id": identity.identity_id,
            "resolved_session_id": session.session_id,
            "resolved_session_token": session.session_token,
            "identity_boundary": "trusted_sso_organization",
            "trusted_role_source": "sso_role_claims",
        }

    def _role_key_from_claims(self, role_claims: Sequence[str]) -> str:
        for item in role_claims:
            claim = str(item or "").strip()
            candidates = (claim, claim.split(":")[-1], claim.split("/")[-1])
            for candidate in candidates:
                role_key = candidate.strip().lower()
                if role_key in self._roles:
                    return role_key
        return "observer"

    @staticmethod
    def _claim_text(claims: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            raw = claims.get(key)
            if raw is None:
                continue
            if isinstance(raw, (list, tuple, set)):
                raw = next((item for item in raw if str(item).strip()), "")
            value = str(raw or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _claim_sequence(claims: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
        for key in keys:
            raw = claims.get(key)
            if raw is None:
                continue
            if isinstance(raw, str):
                return tuple(item.strip() for item in raw.split(",") if item.strip())
            if isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
                return tuple(str(item).strip() for item in raw if str(item).strip())
            value = str(raw or "").strip()
            if value:
                return (value,)
        return ()

    def _audit_source_with_identity(
        self,
        *,
        actor: CollaborationActor,
        actor_identity_id: str = "",
        audit_source: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(audit_source or {})
        external_identity = self._external_identity_for_actor(actor.actor_id)
        expected_identity_id = external_identity.identity_id if external_identity else self._identity_id_for_actor(actor)
        requested_identity_id = str(
            actor_identity_id or payload.get("resolved_identity_id", "") or ""
        ).strip()
        binding_status = "verified"
        if requested_identity_id and requested_identity_id != expected_identity_id:
            raise PermissionError(
                f"Actor identity mismatch for '{actor.actor_id}': {requested_identity_id}"
            )
        if not requested_identity_id:
            binding_status = "service_backfilled"
        resolved_session_token = str(payload.get("resolved_session_token", "") or "").strip()
        if resolved_session_token:
            resolved_session = self.resolve_session(resolved_session_token)
            if resolved_session.actor_id != actor.actor_id:
                raise PermissionError(
                    f"Session actor mismatch for '{actor.actor_id}': {resolved_session.actor_id}"
                )
            if resolved_session.identity_id and resolved_session.identity_id != expected_identity_id:
                raise PermissionError(
                    f"Session identity mismatch for '{actor.actor_id}': {resolved_session.identity_id}"
                )
            payload["resolved_session_expires_at"] = (
                resolved_session.expires_at.isoformat() if resolved_session.expires_at else None
            )
            payload["session_binding_status"] = "verified"
        else:
            payload["session_binding_status"] = "service_backfilled"
        payload["resolved_actor_id"] = actor.actor_id
        payload["resolved_identity_id"] = expected_identity_id
        payload["resolved_role_key"] = actor.role_key
        payload["actor_role_key"] = str(payload.get("actor_role_key", "") or actor.role_key)
        payload["identity_binding_status"] = binding_status
        payload["trusted_role_source"] = str(
            payload.get("trusted_role_source", "")
            or ("sso_role_claims" if external_identity else "collaboration_actor_registry")
        )
        payload["identity_namespace"] = self._identity_namespace
        payload["auth_mechanism"] = str(payload.get("auth_mechanism", "") or "issued_session")
        payload["resolved_session_id"] = str(
            payload.get("resolved_session_id", "")
            or self._session_id_for_actor(
                actor,
                auth_mechanism=str(payload.get("auth_mechanism", "") or "issued_session"),
                session_token=str(payload.get("resolved_session_token", "") or ""),
            )
        )
        payload["audit_event_id"] = str(
            payload.get("audit_event_id", "") or self._audit_event_id(actor_id=actor.actor_id)
        )
        payload["session_namespace"] = self._session_id_namespace
        payload.setdefault("identity_boundary", "trusted_sso_organization" if external_identity else "collaboration_actor_registry")
        if external_identity is not None:
            payload["identity_provider"] = external_identity.provider
            payload["organization_id"] = external_identity.organization_id
            payload["external_subject_id"] = external_identity.external_subject_id
            payload["external_email"] = external_identity.external_email
            payload["external_display_name"] = external_identity.external_display_name
            payload["team_ids"] = list(external_identity.team_ids)
            payload["role_claims"] = list(external_identity.role_claims)
        return payload

    @classmethod
    def _identity_id_for_actor(cls, actor: CollaborationActor) -> str:
        role_key = str(actor.role_key or "").strip() or "actor"
        actor_id = str(actor.actor_id or "").strip()
        return f"{cls._identity_namespace}:{role_key}:{actor_id}"

    @classmethod
    def _identity_id_for_external_subject(cls, *, provider: str, external_subject_id: str) -> str:
        provider_key = cls._stable_key(provider)
        digest = hashlib.sha256(str(external_subject_id or "").strip().encode("utf-8")).hexdigest()[:16]
        return f"{cls._external_identity_namespace}:{provider_key}:{digest}"

    @classmethod
    def _actor_id_for_external_subject(cls, *, provider: str, external_subject_id: str) -> str:
        raw = f"{str(provider or '').strip()}:{str(external_subject_id or '').strip()}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"sso_{digest}"

    @classmethod
    def _sso_session_token(
        cls,
        *,
        provider: str,
        organization_id: str,
        external_subject_id: str,
        external_session_id: str,
    ) -> str:
        raw = ":".join(
            (
                cls._session_token_namespace,
                "sso",
                str(provider or "").strip(),
                str(organization_id or "").strip(),
                str(external_subject_id or "").strip(),
                str(external_session_id or "").strip(),
            )
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"{cls._session_token_namespace}:sso:{digest}"

    @staticmethod
    def _stable_key(value: str) -> str:
        return "".join(item if item.isalnum() or item in {"-", "_"} else "_" for item in str(value or "").strip().lower()) or "provider"

    @classmethod
    def _session_token_for_actor(cls, actor: CollaborationActor) -> str:
        role_key = str(actor.role_key or "").strip() or "actor"
        actor_id = str(actor.actor_id or "").strip()
        return f"{cls._session_token_namespace}:{role_key}:{actor_id}"

    @classmethod
    def _session_id_for_token(cls, session_token: str) -> str:
        digest = hashlib.sha256(str(session_token or "").strip().encode("utf-8")).hexdigest()[:16]
        return f"{cls._session_id_namespace}:{digest}"

    @classmethod
    def _session_id_for_actor(
        cls,
        actor: CollaborationActor,
        *,
        auth_mechanism: str = "",
        session_token: str = "",
    ) -> str:
        raw = str(session_token or "").strip()
        if not raw:
            raw = f"{str(auth_mechanism or 'actor_registry').strip()}:{str(actor.role_key or 'actor').strip()}:{str(actor.actor_id or '').strip()}"
        return cls._session_id_for_token(raw)

    @classmethod
    def _permission_check_id(cls, *, actor_id: str, permission: str) -> str:
        raw = f"{cls._permission_check_namespace}:{actor_id}:{permission}"
        return f"{cls._permission_check_namespace}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"

    @classmethod
    def _audit_event_id(cls, *, actor_id: str) -> str:
        raw = f"{cls._audit_event_namespace}:{actor_id}:{new_id('audit')}"
        return f"{cls._audit_event_namespace}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"
