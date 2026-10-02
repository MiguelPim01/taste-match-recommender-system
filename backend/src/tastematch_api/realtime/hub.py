"""In-memory fan-out of server-sent events: one queue per open tab, plus an activity summary for everyone."""

from __future__ import annotations

import asyncio
import threading
from collections import Counter, defaultdict, deque
from collections.abc import AsyncIterator

from fastapi.sse import ServerSentEvent

from tastematch_api.contracts import InteractionEvent, ModelReadyEvent, RecommendationsEvent, RetrainRequestedEvent
from tastematch_api.kafka.projector import Projected


class Hub:
    """Queues live in the event loop; the projector thread only hands work over with call_soon_threadsafe."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue_size: int = 100):
        self._loop = loop
        self._queue_size = queue_size
        self._tabs: defaultdict[str | None, set[asyncio.Queue]] = defaultdict(set)
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()
        self._recent: deque[dict] = deque(maxlen=5)

    async def listen(self, user_id: str | None) -> AsyncIterator[ServerSentEvent]:
        queue: asyncio.Queue[ServerSentEvent | None] = asyncio.Queue(maxsize=self._queue_size)
        self._tabs[user_id].add(queue)
        try:
            yield ServerSentEvent(event="ready", data={"user_id": user_id})
            while (event := await queue.get()) is not None:
                yield event
        finally:
            self._tabs[user_id].discard(queue)
            if not self._tabs[user_id]:
                del self._tabs[user_id]

    def projected(self, items: list[Projected]) -> None:
        """Called from the projector thread after each committed batch."""
        with self._lock:
            for item in items:
                if isinstance(item.event, InteractionEvent):
                    self._counts[item.event.type] += 1
                    self._recent.append(_summary(item))
        self._loop.call_soon_threadsafe(self._deliver, items)

    def flush_activity(self, interval_s: float) -> None:
        with self._lock:
            counts, recent = dict(self._counts), list(self._recent)
            self._counts.clear()
            self._recent.clear()
        if counts:
            self._broadcast(ServerSentEvent(event="activity",
                                            data={"interval_s": interval_s, "counts": counts, "recent": recent}))

    async def run_activity(self, interval_s: float = 5.0) -> None:
        while True:
            await asyncio.sleep(interval_s)
            self.flush_activity(interval_s)

    def close(self) -> None:
        self._broadcast(None)

    def _deliver(self, items: list[Projected]) -> None:
        """Training events go to every tab; confirmations and new lists only to the profile they belong to."""
        for item in items:
            event = item.event
            if isinstance(event, RetrainRequestedEvent):
                self._broadcast(ServerSentEvent(event="retrain.requested", data={
                    "event_id": event.event_id, "requested_at": event.requested_at, "source": event.source,
                    "force": event.force,
                    "observed_total": sum(event.observed_counts.values()) if event.observed_counts else None}))
            elif isinstance(event, ModelReadyEvent):
                self._broadcast(ServerSentEvent(event="model.ready", data={
                    "run_id": event.run_id, "metric_name": event.metric_name, "metric_value": event.metric_value,
                    "created_at": event.created_at, "trained_until_total": sum(event.trained_until_counts.values())}))
            elif isinstance(event, RecommendationsEvent):
                self._send(event.user_id, ServerSentEvent(event="recommendations.updated", data={
                    "run_id": event.run_id, "generated_at": event.generated_at, "count": len(event.items)}))
            else:
                self._send(event.user_id, ServerSentEvent(event="interaction.recorded", data=_summary(item)))

    def _send(self, user_id: str, event: ServerSentEvent) -> None:
        for queue in self._tabs.get(user_id, ()):
            _offer(queue, event)

    def _broadcast(self, event: ServerSentEvent | None) -> None:
        for queues in self._tabs.values():
            for queue in queues:
                _offer(queue, event)


def _offer(queue: asyncio.Queue, event: ServerSentEvent | None) -> None:
    """A slow tab loses events instead of holding memory; on reconnect the app reloads state through GET."""
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        pass


def _summary(item: Projected) -> dict:
    """Enough for the app to print a ticket: what happened, where, and the rating or the start of the comment."""
    event = item.event
    text = getattr(event, "text", None)
    return {"event_id": event.event_id, "type": event.type, "user_id": event.user_id,
            "restaurant_id": event.restaurant_id, "occurred_at": event.occurred_at,
            "stars": getattr(event, "stars", None), "text": text[:120] if text else None}
