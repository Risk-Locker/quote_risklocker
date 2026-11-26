"""Real-time SSE event stream and active-editor presence API router."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.auth.rbac import require_role
from app.models.enums import Role
from app.models.tables import User
from app.services.realtime_hub import format_sse_message, realtime_hub

router = APIRouter(prefix="/realtime", tags=["realtime"])

RealtimeScope = Literal["ledger", "comparison", "workspace", "sessions", "clients", "upload_runs"]


class PresenceUpdateRequest(BaseModel):
    scope: RealtimeScope
    resource_id: str = Field(default="all", min_length=1, max_length=120)
    field: str | None = Field(default=None, max_length=120)
    tab_id: str | None = Field(default=None, max_length=120)


class PresenceClearRequest(BaseModel):
    scope: RealtimeScope
    resource_id: str = Field(default="all", min_length=1, max_length=120)


@router.get("/events")
async def stream_realtime_events(
    request: Request,
    user: User = Depends(current_user),
) -> StreamingResponse:
    """Read-only SSE stream delivering live updates, active editors, and heartbeats."""
    loop = asyncio.get_running_loop()
    sub_id, queue = realtime_hub.subscribe(user.id, loop)

    async def _event_generator():
        try:
            yield format_sse_message(
                "connected",
                {
                    "user_id": user.id,
                    "user_email": user.email,
                    "version": realtime_hub.current_version(),
                },
            )
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield format_sse_message(item["event"], item["data"])
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            realtime_hub.unsubscribe(sub_id)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/presence")
def get_realtime_presence(
    scope: RealtimeScope = Query(...),
    resource_id: str = Query(default="all", min_length=1, max_length=120),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Read-only snapshot of active editors + per-resource realtime revision."""
    _ = user
    state = realtime_hub.get_resource_state(scope, resource_id)
    return {
        "scope": scope,
        "resource_id": resource_id,
        "version": state["version"],
        "last_origin_tab_id": state["last_origin_tab_id"],
        "last_actor_id": state["last_actor_id"],
        "last_actor_name": state["last_actor_name"],
        "last_summary": state["last_summary"],
        "active_editors": realtime_hub.get_presence(scope, resource_id),
    }


@router.post("/presence")
def update_realtime_presence(
    payload: PresenceUpdateRequest,
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Heartbeat active editor presence for a given scope/resource/field."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    editors = realtime_hub.set_presence(
        scope=payload.scope,
        resource_id=payload.resource_id.strip() or "all",
        user_id=user.id,
        user_email=user.email,
        user_name=user.name or user.email,
        field=payload.field.strip() if payload.field else None,
        tab_id=payload.tab_id.strip() if payload.tab_id else None,
    )
    return {
        "ok": True,
        "scope": payload.scope,
        "resource_id": payload.resource_id,
        "active_editors": editors,
    }


@router.delete("/presence")
def clear_realtime_presence(
    payload: PresenceClearRequest | None = None,
    scope: RealtimeScope | None = Query(default=None),
    resource_id: str = Query(default="all", min_length=1, max_length=120),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Clear active editor presence when leaving a page or blurring an editor."""
    require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)
    target_scope = payload.scope if payload else scope
    target_resource = (payload.resource_id if payload else resource_id).strip() or "all"
    if not target_scope:
        return {"ok": True, "active_editors": []}
    editors = realtime_hub.clear_presence(
        scope=target_scope,
        resource_id=target_resource,
        user_id=user.id,
    )
    return {
        "ok": True,
        "scope": target_scope,
        "resource_id": target_resource,
        "active_editors": editors,
    }
