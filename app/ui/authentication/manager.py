import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Set
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi.responses import RedirectResponse, Response

from app.logging import logger
from app.ui.authentication.models.auth_session import AuthSession
from app.ui.authentication.models.auth_state import AuthState
from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError
from app.ui.authentication.session_store import FileSessionStore

if TYPE_CHECKING:
    from app.im.user_store import UserStore


class UserAuthenticationManager:
    def __init__(
        self,
        provider: AuthenticationProvider,
        redirect_uri: str,
        session_cookie_name: str = "impulse_auth_session",
        state_ttl_seconds: int = 300,
        session_ttl_seconds: int = 90 * 24 * 60 * 60,
        cookie_secure: bool = False,
        allowed_user_ids: Optional[Set[str]] = None,
        default_redirect_path: str = "/",
        allowed_redirect_prefixes: Optional[Set[str]] = None,
        configured_users: Optional[Dict[str, AuthUser]] = None,
        session_store: Optional[FileSessionStore] = None,
        user_store: Optional['UserStore'] = None,
    ):
        self.provider = provider
        self.redirect_uri = redirect_uri
        self.session_cookie_name = session_cookie_name
        self.state_ttl_seconds = state_ttl_seconds
        self.session_ttl_seconds = session_ttl_seconds
        self.cookie_secure = cookie_secure
        self.allowed_user_ids = {str(user_id) for user_id in (allowed_user_ids or set())}
        self.default_redirect_path = self._coerce_default_redirect_path(default_redirect_path)
        self.allowed_redirect_prefixes = self._coerce_allowed_redirect_prefixes(
            allowed_redirect_prefixes,
            self.default_redirect_path,
        )
        self._configured_users = {str(user_id): user for user_id, user in (configured_users or {}).items()}
        self.session_store = session_store or FileSessionStore(root_dir="sessions")
        self._user_store = user_store

        self._states: Dict[str, AuthState] = {}

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
        params: Optional[Mapping[str, str]] = None,
    ) -> RedirectResponse:
        params = dict(params or {})
        state = params.get("state")
        if not state:
            return self._build_error_redirect("/", "invalid_state")

        auth_state = self._pop_state(state)
        if not auth_state:
            return self._build_error_redirect("/", "invalid_state")

        if not self.provider.is_supported():
            return self._build_error_redirect(auth_state.next_path, "not_supported")

        try:
            user = await self.provider.authenticate_callback(params, self.redirect_uri)
        except AuthenticationProviderError as exc:
            error_code = self._sanitize_error(exc.code) if exc.code else "auth_failed"
            return self._build_error_redirect(auth_state.next_path, error_code)
        except Exception as exc:
            logger.warning(
                "Authentication callback failed",
                extra={"provider": self.provider.name, "error": str(exc)},
            )
            return self._build_error_redirect(auth_state.next_path, "auth_failed")

        if self.allowed_user_ids and str(user.id) not in self.allowed_user_ids:
            return self._build_error_redirect(auth_state.next_path, "not_allowed")

        session_id = secrets.token_hex(32)
        now = self._now()
        expires_at = now + timedelta(seconds=self.session_ttl_seconds)
        session = AuthSession(
            session_id=session_id,
            user_id=str(user.id),
            created_at=now,
            expires_at=expires_at,
        )
        try:
            self.session_store.save_session(session)
        except Exception as exc:
            logger.warning("Failed to save auth session", extra={"error": str(exc)})
            return self._build_error_redirect(auth_state.next_path, "auth_failed")

        response = self._build_local_redirect(auth_state.next_path)
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
        auth_user = self._resolve_user(session.user_id)
        user_data = self._enrich_from_user_store(auth_user)
        return {"authenticated": True, "user": user_data}

    def logout(self, session_id: Optional[str] = None) -> Response:
        if session_id:
            self.session_store.delete_session(session_id)

        response = Response(status_code=204)
        response.delete_cookie(key=self.session_cookie_name, path="/")
        return response

    def _pop_state(self, state: str) -> Optional[AuthState]:
        self._cleanup_states()
        return self._states.pop(state, None)

    def _get_session(self, session_id: Optional[str]) -> Optional[AuthSession]:
        if not session_id:
            return None
        return self.session_store.load_session(session_id)

    def _cleanup_states(self) -> None:
        now = self._now()
        deadline = now - timedelta(seconds=self.state_ttl_seconds)
        expired_states = [state for state, value in self._states.items() if value.created_at < deadline]
        for state in expired_states:
            self._states.pop(state, None)

    def _resolve_user(self, user_id: str) -> AuthUser:
        configured = self._configured_users.get(str(user_id))
        if configured:
            return configured
        return AuthUser(id=str(user_id), messenger=self.provider.name)

    def _enrich_from_user_store(self, auth_user: AuthUser) -> Dict[str, Any]:
        data = auth_user.model_dump()
        if not self._user_store:
            return data
        stored = self._user_store.get(auth_user.id)
        if not stored:
            return data
        for field in ("username", "full_name", "email", "timezone"):
            if not data.get(field) and stored.get(field):
                data[field] = stored[field]
        return data

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _normalize_next_path(self, next_path: Optional[str]) -> str:
        canonical = self._canonicalize_local_path(next_path)
        if not canonical:
            return self.default_redirect_path
        if not self._is_allowed_redirect_path(canonical):
            return self.default_redirect_path
        return canonical

    @staticmethod
    def _canonicalize_local_path(path: Optional[str]) -> Optional[str]:
        if not path or not path.startswith("/"):
            return None
        if path.startswith("//"):
            return None
        if "://" in path:
            return None
        if any(char in path for char in ("\r", "\n", "\\")):
            return None

        split = urlsplit(path)
        if split.scheme or split.netloc:
            return None
        normalized_path = split.path or "/"
        if not normalized_path.startswith("/"):
            return None
        return urlunsplit(("", "", normalized_path, split.query, split.fragment))

    def _build_error_redirect(self, next_path: str, error_code: str) -> RedirectResponse:
        logger.warning("Auth redirect error", extra={"error": error_code, "provider": self.provider.name})
        return self._build_local_redirect(next_path)

    def _build_local_redirect(self, next_path: str) -> RedirectResponse:
        safe_path = self._normalize_next_path(next_path)
        return RedirectResponse(url=safe_path, status_code=302)

    def _is_allowed_redirect_path(self, path: str) -> bool:
        path_only = urlsplit(path).path or "/"
        for prefix in self.allowed_redirect_prefixes:
            if prefix == "/":
                return True
            if path_only == prefix or path_only.startswith(f"{prefix}/"):
                return True
        return False

    @staticmethod
    def _coerce_default_redirect_path(path: str) -> str:
        canonical = UserAuthenticationManager._canonicalize_local_path(path)
        return canonical or "/"

    @staticmethod
    def _coerce_allowed_redirect_prefixes(
        prefixes: Optional[Set[str]],
        default_redirect_path: str,
    ) -> Set[str]:
        values = prefixes or {urlsplit(default_redirect_path).path or "/"}
        normalized_prefixes: Set[str] = set()
        for prefix in values:
            canonical = UserAuthenticationManager._canonicalize_local_path(prefix)
            if not canonical:
                continue
            path_only = (urlsplit(canonical).path or "/").rstrip("/") or "/"
            normalized_prefixes.add(path_only)
        return normalized_prefixes or {"/"}

    @staticmethod
    def _sanitize_error(error: str) -> str:
        return "".join(char for char in error if char.isalnum() or char in {"_", "-"}).strip() or "provider_error"
