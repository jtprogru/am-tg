import secrets
from dataclasses import dataclass, field
from typing import Annotated, Any, Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class AuthContext:
    """Identity of an authenticated alert source."""

    source_name: str
    claims: dict[str, Any] = field(default_factory=dict)  # populated by future JWT provider


class AuthProvider(Protocol):
    scheme: str

    async def authenticate(self, credentials: str) -> AuthContext | None:
        """Return the source identity, or None if these credentials are not ours."""
        ...


class StaticTokenAuthProvider:
    """Static bearer tokens from config; the token identifies the source."""

    scheme = "Bearer"

    def __init__(self, tokens: dict[str, str]) -> None:
        if not tokens:
            raise ValueError("no auth tokens configured")
        self._tokens = tokens  # token -> source name

    async def authenticate(self, credentials: str) -> AuthContext | None:
        # Compare against every entry without an early exit so timing
        # does not reveal which (or whether a) token matched.
        matched: str | None = None
        for token, source_name in self._tokens.items():
            if secrets.compare_digest(credentials.encode(), token.encode()):
                matched = source_name
        return AuthContext(source_name=matched) if matched else None


_bearer = HTTPBearer(auto_error=False)


async def authenticated_source(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext:
    """Resolve the caller through the app's ordered provider list (401 otherwise)."""
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )
    for provider in request.app.state.auth_providers:
        context = await provider.authenticate(credentials.credentials)
        if context is not None:
            return context
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token", headers={"WWW-Authenticate": "Bearer"})
