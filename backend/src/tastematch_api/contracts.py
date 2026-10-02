"""Events v1 the backend reads and writes: interactions (kafka/docs/02) and the training lifecycle topics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AfterValidator, BaseModel, Field, StringConstraints


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def epoch(timestamp: str) -> float:
    """ISO 8601 instant to seconds; the Yelp replay sends whole seconds and the app sends milliseconds."""
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("o horário precisa de fuso, como 2026-10-02T14:03:40Z")
    return moment.timestamp()


def _instant(value: str) -> str:
    epoch(value)
    return value


Instant = Annotated[str, AfterValidator(_instant)]


class InteractionEvent(BaseModel):
    schema_version: Literal[1] = 1
    event_id: NonBlank
    type: str
    user_id: NonBlank
    restaurant_id: NonBlank
    occurred_at: Instant


class ViewEvent(InteractionEvent):
    pass


class CommentEvent(InteractionEvent):
    text: NonBlank


class ReviewEvent(InteractionEvent):
    stars: int = Field(ge=1, le=5)


@dataclass(frozen=True)
class EventKind:
    prefix: str
    topic: str
    event_type: str
    model: type[InteractionEvent]

    def build(self, user_id: str, restaurant_id: str, idempotency_key: str | None, **fields) -> InteractionEvent:
        """A retry with the same Idempotency-Key reuses the event_id, so the consumers drop the copy."""
        return self.model(event_id=f"app:{self.prefix}:{idempotency_key or uuid4()}", type=self.event_type,
                          user_id=user_id, restaurant_id=restaurant_id, occurred_at=utc_now(), **fields)


VIEW = EventKind("view", "view-restaurant", "restaurant.viewed", ViewEvent)
COMMENT = EventKind("comment", "comment-restaurant", "restaurant.commented", CommentEvent)
REVIEW = EventKind("review", "review-restaurant", "restaurant.rated", ReviewEvent)
KINDS_BY_TOPIC = {kind.topic: kind for kind in (VIEW, COMMENT, REVIEW)}

RECOMMENDATIONS_TOPIC = "user-recommendations"
RETRAIN_TOPIC = "recommender-retrain"
READY_TOPIC = "recommender-ready"


class RecommendationsEvent(BaseModel):
    """One profile's ranked list, published by the training publisher after each new model."""

    schema_version: Literal[1] = 1
    event_id: NonBlank
    type: Literal["recommendations.generated"]
    user_id: NonBlank
    run_id: NonBlank
    generated_at: Instant
    items: list[NonBlank]


class RetrainRequestedEvent(BaseModel):
    """The complex event: the monitor asks for a training once enough new interactions arrived."""

    schema_version: Literal[1] = 1
    event_id: NonBlank
    type: Literal["recommender.retrain.requested"]
    requested_at: Instant
    source: str | None = None
    observed_counts: dict[str, int] | None = None
    force: bool = False


class ModelReadyEvent(BaseModel):
    """Published by the training worker every time a training finishes; that model is now in use."""

    schema_version: Literal[1] = 1
    event_id: NonBlank
    type: Literal["model.ready"]
    run_id: NonBlank
    metric_name: str = "NDCG@10"
    metric_value: float
    trained_until_counts: dict[str, int]
    created_at: Instant
