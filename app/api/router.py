from fastapi import APIRouter, HTTPException, Request

from app.im.groups import serialize_groups
from app.im.user_groups import serialize_user_groups
from app.webhook import serialize_webhooks

_MSG_INCIDENT_NOT_FOUND = "Incident not found"
_MSG_GROUP_NOT_FOUND = "Group not found"
_MSG_USER_NOT_FOUND = "User not found"
_MSG_USER_GROUP_NOT_FOUND = "User group not found"
_MSG_WEBHOOK_NOT_FOUND = "Webhook not found"


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/incidents")
    async def get_incidents(request: Request):
        return request.app.state.incidents.serialize()

    @router.get("/incidents/{uniq_id}")
    async def get_incident(request: Request, uniq_id: str):
        incident = request.app.state.incidents.get_by_uniq_id(uniq_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=_MSG_INCIDENT_NOT_FOUND)
        return incident.serialize()

    @router.get("/groups")
    async def get_groups(request: Request):
        return serialize_groups(request.app.state.messenger.groups)

    @router.get("/groups/{group_name}")
    async def get_group(request: Request, group_name: str):
        group = request.app.state.messenger.groups.get(group_name)
        if group is None:
            raise HTTPException(status_code=404, detail=_MSG_GROUP_NOT_FOUND)
        return group.serialize()

    @router.get("/users")
    async def get_users(request: Request):
        return request.app.state.messenger.users.serialize()

    @router.get("/users/{user_name}")
    async def get_user(request: Request, user_name: str):
        payload = request.app.state.messenger.users.serialize_one(user_name)
        if payload is None:
            raise HTTPException(status_code=404, detail=_MSG_USER_NOT_FOUND)
        return payload

    @router.get("/user_groups")
    async def get_user_groups(request: Request):
        return serialize_user_groups(request.app.state.messenger.user_groups)

    @router.get("/user_groups/{user_group_name}")
    async def get_user_group(request: Request, user_group_name: str):
        user_group = request.app.state.messenger.user_groups.get(user_group_name)
        if user_group is None:
            raise HTTPException(status_code=404, detail=_MSG_USER_GROUP_NOT_FOUND)
        return user_group.serialize()

    @router.get("/webhooks")
    async def get_webhooks(request: Request):
        return serialize_webhooks(request.app.state.webhooks)

    @router.get("/webhooks/{webhook_name}")
    async def get_webhook(request: Request, webhook_name: str):
        webhook = request.app.state.webhooks.get(webhook_name)
        if webhook is None:
            raise HTTPException(status_code=404, detail=_MSG_WEBHOOK_NOT_FOUND)
        return webhook.serialize()

    return router
