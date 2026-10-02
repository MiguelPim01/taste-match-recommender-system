"""Interaction commands: validate, publish to Kafka and answer 202 only after the brokers acknowledge."""

from __future__ import annotations

import logging
import threading
import time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StringConstraints

from tastematch_api.contracts import COMMENT, REVIEW, VIEW, EventKind, InteractionEvent
from tastematch_api.deps import CurrentUser, Db, IdempotencyKey, Pub
from tastematch_api.kafka.producer import Publisher, PublishError
from tastematch_api.store import Restaurant


LOG = logging.getLogger(__name__)
router = APIRouter(prefix="/api/restaurants/{restaurant_id}", tags=["interações"])


class CommentIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)


class Accepted(BaseModel):
    status: Literal["published", "skipped"]
    event_id: str | None
    type: str
    topic: str
    partition: int | None = None
    offset: int | None = None


class ViewThrottle:
    """At most one view per profile and restaurant per window, so reloading the page does not inflate counts."""

    def __init__(self, window_s: int):
        self._window_s = window_s
        self._last: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def seen_recently(self, user_id: str, restaurant_id: str) -> bool:
        with self._lock:
            last = self._last.get((user_id, restaurant_id))
        return last is not None and time.monotonic() - last < self._window_s

    def mark(self, user_id: str, restaurant_id: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._last[(user_id, restaurant_id)] = now
            if len(self._last) > 50_000:
                self._last = {pair: seen for pair, seen in self._last.items() if now - seen < self._window_s}


@router.post("/views", status_code=202)
def record_view(restaurant_id: str, request: Request, user: CurrentUser, db: Db, publisher: Pub,
                idempotency_key: IdempotencyKey = None) -> Accepted:
    _require_restaurant(db, restaurant_id)
    throttle: ViewThrottle = request.app.state.view_throttle
    if throttle.seen_recently(user.id, restaurant_id):
        return Accepted(status="skipped", event_id=None, type=VIEW.event_type, topic=VIEW.topic)
    accepted = publish_interaction(publisher, VIEW, VIEW.build(user.id, restaurant_id, idempotency_key))
    throttle.mark(user.id, restaurant_id)
    return accepted


@router.post("/comments", status_code=202)
def record_comment(restaurant_id: str, body: CommentIn, user: CurrentUser, db: Db, publisher: Pub,
                   idempotency_key: IdempotencyKey = None) -> Accepted:
    _require_restaurant(db, restaurant_id)
    return publish_interaction(publisher, COMMENT, COMMENT.build(user.id, restaurant_id, idempotency_key, text=body.text))


@router.put("/rating", status_code=202)
def record_rating(restaurant_id: str, body: RatingIn, user: CurrentUser, db: Db, publisher: Pub,
                  idempotency_key: IdempotencyKey = None) -> Accepted:
    _require_restaurant(db, restaurant_id)
    return publish_interaction(publisher, REVIEW, REVIEW.build(user.id, restaurant_id, idempotency_key, stars=body.stars))


def _require_restaurant(db: Db, restaurant_id: str) -> None:
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(404, "Restaurante não está no catálogo")


def publish_interaction(publisher: Publisher, kind: EventKind, event: InteractionEvent) -> Accepted:
    try:
        delivery = publisher.publish(kind.topic, event.user_id, event.model_dump())
    except PublishError as error:
        LOG.warning("Evento %s não publicado: %s", event.event_id, error)
        raise HTTPException(503, "Kafka indisponível. Tente de novo com o mesmo Idempotency-Key.",
                            headers={"Retry-After": "5"}) from error
    LOG.info("Evento publicado: eventId=%s, topic=%s, partition=%d, offset=%d",
             event.event_id, delivery.topic, delivery.partition, delivery.offset)
    return Accepted(status="published", event_id=event.event_id, type=kind.event_type, topic=delivery.topic,
                    partition=delivery.partition, offset=delivery.offset)
