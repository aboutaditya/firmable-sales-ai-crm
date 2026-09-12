from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str | None
    role: str
    roles: frozenset[str]
    claims: dict

    @property
    def access_role(self) -> str:
        """Return the application role, preferring Supabase custom roles.

        Supabase commonly puts ``authenticated`` in the JWT ``role`` claim
        while the product role lives in ``roles`` or ``app_metadata``.
        Authorization decisions must use the latter when present.
        """
        for candidate in ("admin", "sales_manager", "sales_rep"):
            if candidate in self.roles:
                return candidate
        return self.role


bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthUser:
    settings = request.app.state.settings
    if not settings.auth_required and credentials is None:
        return AuthUser("anonymous", None, "anonymous", frozenset(), {})
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        token = credentials.credentials
        header = jwt.get_unverified_header(token)
        algorithm = str(header.get("alg", ""))
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer = settings.supabase_jwt_issuer
        if issuer and unverified_claims.get("iss") != issuer:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

        if algorithm == "HS256":
            if not settings.supabase_jwt_secret:
                raise HTTPException(status_code=503, detail="HS256 authentication is not configured")
            signing_key = settings.supabase_jwt_secret
        elif algorithm in {"ES256", "RS256"}:
            if not settings.supabase_jwks_url:
                raise HTTPException(status_code=503, detail="Supabase JWKS authentication is not configured")
            signing_key = jwt.PyJWKClient(settings.supabase_jwks_url).get_signing_key_from_jwt(token).key
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported bearer token algorithm")

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            options={"require": ["sub"]},
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc
    app_metadata = claims.get("app_metadata") or {}
    raw_roles = claims.get("roles") or app_metadata.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles = frozenset(str(role) for role in raw_roles)
    role = str(claims.get("role", claims.get("user_role", "authenticated")))
    roles = roles | {role}
    return AuthUser(
        user_id=str(claims["sub"]),
        email=claims.get("email"),
        role=role,
        roles=roles,
        claims=claims,
    )


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(user: AuthUser = Depends(current_user)) -> AuthUser:
        if user.user_id == "anonymous":
            return user
        if not user.roles.intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


def require_authenticated_queue_user(user: AuthUser) -> AuthUser:
    if user.user_id == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to use the assigned sales queue")
    return user
