"""Training cycle dashboard: event rate, distance to the next training, requests and models; plus the retrain shortcut."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from tastematch_api.contracts import COMMENT, RETRAIN_TOPIC, REVIEW, VIEW, RetrainRequestedEvent, utc_now
from tastematch_api.deps import Db, IdempotencyKey, Pub
from tastematch_api.kafka.producer import PublishError
from tastematch_api.store import Interaction, ModelVersion, RetrainRequest


router = APIRouter(prefix="/api", tags=["painel"])

# Same names the training uses in observed_counts and trained_until_counts.
SIGNALS = {VIEW.event_type: "views", COMMENT.event_type: "comments", REVIEW.event_type: "reviews"}
WINDOW_MINUTES = 15


class MinuteCount(BaseModel):
    minute: str
    views: int = 0
    comments: int = 0
    reviews: int = 0


class NextTraining(BaseModel):
    threshold: int
    new_events: int
    remaining: int


class RetrainRequestOut(BaseModel):
    event_id: str
    requested_at: str
    source: str | None
    force: bool
    observed_total: int | None


class ModelOut(BaseModel):
    run_id: str
    metric_name: str
    metric_value: float
    trained_until_total: int
    created_at: str

    @classmethod
    def of(cls, model: ModelVersion) -> ModelOut:
        return cls(run_id=model.run_id, metric_name=model.metric_name, metric_value=model.metric_value,
                   trained_until_total=sum(json.loads(model.trained_until_counts).values()),
                   created_at=model.created_at)


class RecentEvent(BaseModel):
    event_id: str
    type: str
    user_id: str
    restaurant_id: str
    occurred_at: str
    stars: int | None
    text: str | None
    recorded_at: str


class Dashboard(BaseModel):
    totals: dict[str, int]
    events_per_minute: list[MinuteCount]
    next_training: NextTraining
    current_model: ModelOut | None
    models: list[ModelOut]
    retrain_requests: list[RetrainRequestOut]
    request_after_last_model: bool
    recent_events: list[RecentEvent]


class RetrainAccepted(BaseModel):
    event_id: str
    topic: str
    partition: int
    offset: int


@router.get("/dashboard")
def dashboard(request: Request, db: Db) -> Dashboard:
    totals = projected_totals(db)
    models = list(db.scalars(select(ModelVersion).order_by(ModelVersion.created_ts.desc()).limit(20)))
    current = models[0] if models else None
    # The worker counts new events against the snapshot of the last training, which model.ready carries.
    trained = json.loads(current.trained_until_counts) if current else {}
    new_events = sum(max(0, total - trained.get(signal, 0)) for signal, total in totals.items()) if current else 0
    threshold = request.app.state.settings.retrain_min_events
    requests = list(db.scalars(select(RetrainRequest).order_by(RetrainRequest.requested_ts.desc()).limit(10)))
    return Dashboard(
        totals=totals,
        events_per_minute=_per_minute(db),
        next_training=NextTraining(threshold=threshold, new_events=new_events,
                                   remaining=max(0, threshold - new_events)),
        current_model=ModelOut.of(current) if current else None,
        models=[ModelOut.of(model) for model in models],
        retrain_requests=[RetrainRequestOut(
            event_id=item.event_id, requested_at=item.requested_at, source=item.source, force=item.force,
            observed_total=sum(json.loads(item.observed_counts).values()) if item.observed_counts else None,
        ) for item in requests],
        request_after_last_model=bool(requests) and (current is None or requests[0].requested_ts > current.created_ts),
        recent_events=[RecentEvent(
            event_id=item.event_id, type=item.type, user_id=item.user_id, restaurant_id=item.restaurant_id,
            occurred_at=item.occurred_at, stars=item.stars, text=item.text[:120] if item.text else None,
            recorded_at=_iso(item.recorded_ts),
        ) for item in db.scalars(select(Interaction)
                                 .order_by(Interaction.recorded_ts.desc(), Interaction.event_id.desc()).limit(14))],
    )


@router.post("/admin/retrain", status_code=202)
def request_retrain(db: Db, publisher: Pub, idempotency_key: IdempotencyKey = None) -> RetrainAccepted:
    """Demonstration shortcut: a forced request skips the new-events threshold."""
    event = RetrainRequestedEvent(event_id=f"backend:{idempotency_key or uuid4()}",
                                  type="recommender.retrain.requested", requested_at=utc_now(), source="backend",
                                  observed_counts=projected_totals(db), force=True)
    try:
        delivery = publisher.publish(RETRAIN_TOPIC, "ensemble", event.model_dump())
    except PublishError as error:
        raise HTTPException(503, "Kafka indisponível. Tente de novo com o mesmo Idempotency-Key.",
                            headers={"Retry-After": "5"}) from error
    return RetrainAccepted(event_id=event.event_id, topic=delivery.topic, partition=delivery.partition,
                           offset=delivery.offset)


def projected_totals(db: Session) -> dict[str, int]:
    counts = dict(db.execute(select(Interaction.type, func.count()).group_by(Interaction.type)).all())
    return {signal: counts.get(event_type, 0) for event_type, signal in SIGNALS.items()}


def _per_minute(db: Session) -> list[MinuteCount]:
    """Events published to Kafka per minute over the last 15 minutes, oldest first, zeros included."""
    last = int(time.time() // 60) * 60
    first = last - (WINDOW_MINUTES - 1) * 60
    minute = (cast(Interaction.recorded_ts / 60, Integer) * 60).label("minute")
    rows = db.execute(select(minute, Interaction.type, func.count())
                      .where(Interaction.recorded_ts >= first).group_by(minute, Interaction.type))
    buckets = {start: MinuteCount(minute=_iso(start)) for start in range(first, last + 60, 60)}
    for start, event_type, count in rows:
        if start in buckets:
            setattr(buckets[start], SIGNALS[event_type], count)
    return list(buckets.values())


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
