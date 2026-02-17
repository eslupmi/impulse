from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi.responses import RedirectResponse, Response

from app.logging import logger
from app.ui.authentication.models.auth_session import AuthSession
from app.ui.authentication.models.auth_state import AuthState
from app.ui.authentication.providers.base_provider import AuthenticationProvider


class UserAuthenticationManager:
    def __init__(
        self,
        provider: AuthenticationProvider,
        redirect_uri: str,
        session_cookie_name: str = "impulse_auth_session",
        state_ttl_seconds: int = 300,
        session_ttl_seconds: int = 8 * 60 * 60,
        cookie_secure: bool = False,
    ):
        self.provider = provider
        self.redirect_uri = redirect_uri
        self.session_cookie_name = session_cookie_name
        self.state_ttl_seconds = state_ttl_seconds
        self.session_ttl_seconds = session_ttl_seconds
        self.cookie_secure = cookie_secure

        self._states: Dict[str, AuthState] = {}
        self._sessions: Dict[str, AuthSession] = {}

    def start_auth(self, next_path: Optional[str] = None) -> RedirectResponse:
        safe_next_path = self._normalize_next_path(next_path)
        if not self.provider.is_supported():
            return self._build_error_redirect(safe_next_path, "not_supported")

        state = uuid4().hex
        self._states[state] = AuthState(
            state=state,
            next_path=safe_next_path,
            created_at=self._now(),
        )

        try:
            authorization_url = self.provider.build_authorization_url(state, self.redirect_uri)
        except Exception as exc:
            logger.warning(
                "Failed to build authorization URL",
                extra={"provider": self.provider.name, "error": str(exc)},
            )
            return self._build_error_redirect(safe_next_path, "auth_start_failed")

        return RedirectResponse(url=authorization_url, status_code=302)

    async def handle_callback(
        self,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
    ) -> RedirectResponse:
        if not state:
            return self._build_error_redirect("/", "invalid_state")

        auth_state = self._pop_state(state)
        if not auth_state:
            return self._build_error_redirect("/", "invalid_state")

        if error:
            return self._build_error_redirect(auth_state.next_path, self._sanitize_error(error))

        if not code:
            return self._build_error_redirect(auth_state.next_path, "missing_code")

        if not self.provider.is_supported():
            return self._build_error_redirect(auth_state.next_path, "not_supported")

        try:
            access_token = await self.provider.exchange_code(code, self.redirect_uri)
            user = await self.provider.fetch_user(access_token)
        except Exception as exc:
            logger.warning(
                "Authentication callback failed",
                extra={"provider": self.provider.name, "error": str(exc)},
            )
            return self._build_error_redirect(auth_state.next_path, "auth_failed")

        session_id = uuid4().hex
        now = self._now()
        expires_at = now + timedelta(seconds=self.session_ttl_seconds)
        self._sessions[session_id] = AuthSession(
            session_id=session_id,
            user=user,
            created_at=now,
            expires_at=expires_at,
        )

        response = RedirectResponse(url=auth_state.next_path, status_code=302)
        response.set_cookie(
            key=self.session_cookie_name,
            value=session_id,
            httponly=True,
            secure=self.cookie_secure,
            samesite="lax",
            max_age=self.session_ttl_seconds,
            path="/",
        )
        return response

    def get_current_user(self, session_id: Optional[str] = None) -> dict:
        session = self._get_session(session_id)
        if not session:
            return {"authenticated": False}
        return {"authenticated": True, "user": session.user.model_dump()}

    def logout(self, session_id: Optional[str] = None) -> Response:
        if session_id:
            self._sessions.pop(session_id, None)

        response = Response(status_code=204)
        response.delete_cookie(key=self.session_cookie_name, path="/")
        return response

    def _pop_state(self, state: str) -> Optional[AuthState]:
        self._cleanup_states()
        return self._states.pop(state, None)

    def _get_session(self, session_id: Optional[str]) -> Optional[AuthSession]:
        if not session_id:
            return None

        self._cleanup_sessions()
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session

    def _cleanup_states(self) -> None:
        now = self._now()
        deadline = now - timedelta(seconds=self.state_ttl_seconds)
        expired_states = [state for state, value in self._states.items() if value.created_at < deadline]
        for state in expired_states:
            self._states.pop(state, None)

    def _cleanup_sessions(self) -> None:
        now = self._now()
        expired_sessions = [
            session_id
            for session_id, value in self._sessions.items()
            if value.expires_at <= now
        ]
        for session_id in expired_sessions:
            self._sessions.pop(session_id, None)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _normalize_next_path(self, next_path: Optional[str]) -> str:
        if self._is_safe_local_path(next_path):
            return next_path
        return "/"

    @staticmethod
    def _is_safe_local_path(path: Optional[str]) -> bool:
        if not path or not path.startswith("/"):
            return False
        if path.startswith("//"):
            return False
        if "://" in path:
            return False

        split = urlsplit(path)
        if split.scheme or split.netloc:
            return False
        return True

    def _build_error_redirect(self, next_path: str, error_code: str) -> RedirectResponse:
        safe_path = self._normalize_next_path(next_path)
        location = self._append_query_param(safe_path, "auth_error", error_code)
        return RedirectResponse(url=location, status_code=302)

    @staticmethod
    def _append_query_param(path: str, key: str, value: str) -> str:
        split = urlsplit(path)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query[key] = value
        new_query = urlencode(query)
        return urlunsplit(("", "", split.path or "/", new_query, split.fragment))

    @staticmethod
    def _sanitize_error(error: str) -> str:
        return "".join(char for char in error if char.isalnum() or char in {"_", "-"}).strip() or "provider_error"
