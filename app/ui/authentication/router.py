from typing import Annotated, Optional

from fastapi import APIRouter, Query, Request

from app.ui.authentication.manager import UserAuthenticationManager


def create_auth_router(manager: UserAuthenticationManager) -> APIRouter:
    router = APIRouter()

    @router.get("/auth/login")
    async def auth_login(next_path: Annotated[Optional[str], Query(alias="next")] = None):
        return manager.start_auth(next_path=next_path)

    @router.get("/auth/callback")
    async def auth_callback(request: Request):
        return await manager.handle_callback(params=dict(request.query_params))

    @router.get("/auth/me")
    async def auth_me(request: Request):
        session_id = request.cookies.get(manager.session_cookie_name)
        return manager.get_current_user(session_id=session_id)

    @router.post("/auth/logout")
    async def auth_logout(request: Request):
        session_id = request.cookies.get(manager.session_cookie_name)
        return manager.logout(session_id=session_id)

    return router
