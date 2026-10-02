"""Server-sent events: confirmations for the session profile and an activity summary for every tab."""

from __future__ import annotations

from collections.abc import AsyncIterable

from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from tastematch_api.deps import SESSION_COOKIE
from tastematch_api.realtime.hub import Hub


router = APIRouter(tags=["tempo real"])


@router.get("/api/stream", response_class=EventSourceResponse)
async def stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    """Without a session the tab only gets the activity summary, which is enough for the dashboard."""
    hub: Hub = request.app.state.hub
    async for event in hub.listen(request.cookies.get(SESSION_COOKIE)):
        yield event
