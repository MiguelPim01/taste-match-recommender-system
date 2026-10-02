"""Kafka consumer that projects interactions, recommendation lists and the training lifecycle into the read model."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from confluent_kafka import Consumer, KafkaException
from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection, Engine, and_, or_, select
from sqlalchemy.dialects.sqlite import insert

from tastematch_api.contracts import (KINDS_BY_TOPIC, READY_TOPIC, RECOMMENDATIONS_TOPIC, RETRAIN_TOPIC, REVIEW,
                                      InteractionEvent, ModelReadyEvent, RecommendationsEvent, RetrainRequestedEvent,
                                      epoch)
from tastematch_api.store import Interaction, ModelVersion, Rating, Recommendation, RetrainRequest


LOG = logging.getLogger(__name__)

ProjectedEvent = InteractionEvent | RecommendationsEvent | RetrainRequestedEvent | ModelReadyEvent


@dataclass(frozen=True)
class Feed:
    model: type[BaseModel]
    event_type: str
    keyed_by_user: bool = True  # os tópicos do treino usam a chave "ensemble"


FEEDS = {
    **{kind.topic: Feed(kind.model, kind.event_type) for kind in KINDS_BY_TOPIC.values()},
    RECOMMENDATIONS_TOPIC: Feed(RecommendationsEvent, "recommendations.generated"),
    RETRAIN_TOPIC: Feed(RetrainRequestedEvent, "recommender.retrain.requested", keyed_by_user=False),
    READY_TOPIC: Feed(ModelReadyEvent, "model.ready", keyed_by_user=False),
}


@dataclass(frozen=True)
class Record:
    topic: str
    key: str | None
    value: bytes | None
    recorded_ts: float


@dataclass(frozen=True)
class Projected:
    event: ProjectedEvent
    recorded_ts: float


def kafka_consumer(bootstrap_servers: str, group_id: str) -> Consumer:
    return Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "client.id": "tastematch-backend-projector",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })


def project(engine: Engine, records: list[Record]) -> list[Projected]:
    """Write a batch in one transaction and return only what changed the read model."""
    projected = []
    with engine.begin() as connection:
        for record in records:
            event = _decode(record)
            if event is not None and _save(connection, event, record.recorded_ts):
                projected.append(Projected(event, record.recorded_ts))
    return projected


def _decode(record: Record) -> ProjectedEvent | None:
    """Same rules as the Java consumers; an invalid message is skipped so it never blocks the partition."""
    feed = FEEDS.get(record.topic)
    if feed is None or record.value is None:
        return None
    try:
        event = feed.model.model_validate_json(record.value)
    except ValidationError as error:
        LOG.warning("Evento ignorado em %s: %s", record.topic, error.errors()[0]["msg"])
        return None
    if event.type != feed.event_type or (feed.keyed_by_user and record.key != event.user_id):
        LOG.warning("Evento %s ignorado: tipo ou chave Kafka diferentes do contrato", event.event_id)
        return None
    return event


def _save(connection: Connection, event: ProjectedEvent, recorded_ts: float) -> bool:
    if isinstance(event, RecommendationsEvent):
        return _save_recommendations(connection, event)
    if isinstance(event, RetrainRequestedEvent):
        return _save_retrain_request(connection, event)
    if isinstance(event, ModelReadyEvent):
        return _save_model(connection, event)
    return _save_interaction(connection, event, recorded_ts)


def _save_interaction(connection: Connection, event: InteractionEvent, recorded_ts: float) -> bool:
    occurred_ts = epoch(event.occurred_at)
    inserted = connection.execute(insert(Interaction).values(
        type=event.type, event_id=event.event_id, user_id=event.user_id, restaurant_id=event.restaurant_id,
        occurred_at=event.occurred_at, occurred_ts=occurred_ts, stars=getattr(event, "stars", None),
        text=getattr(event, "text", None), recorded_ts=recorded_ts,
    ).on_conflict_do_nothing()).rowcount
    if inserted and event.type == REVIEW.event_type:
        statement = insert(Rating).values(user_id=event.user_id, restaurant_id=event.restaurant_id,
                                          stars=event.stars, occurred_ts=occurred_ts, event_id=event.event_id)
        newer = statement.excluded
        connection.execute(statement.on_conflict_do_update(
            index_elements=[Rating.user_id, Rating.restaurant_id],
            set_={"stars": newer.stars, "occurred_ts": newer.occurred_ts, "event_id": newer.event_id},
            where=or_(newer.occurred_ts > Rating.occurred_ts,
                      and_(newer.occurred_ts == Rating.occurred_ts, newer.event_id > Rating.event_id)),
        ))
    return bool(inserted)


def _save_recommendations(connection: Connection, event: RecommendationsEvent) -> bool:
    """The key is user_id, so lists arrive in order per profile: the last one wins."""
    items = json.dumps(event.items)
    current = connection.execute(select(Recommendation.run_id, Recommendation.items)
                                 .where(Recommendation.user_id == event.user_id)).first()
    if current is not None and tuple(current) == (event.run_id, items):
        return False
    statement = insert(Recommendation).values(user_id=event.user_id, run_id=event.run_id,
                                              generated_at=event.generated_at, items=items)
    newer = statement.excluded
    # "items" também é um método da coleção de colunas; o acesso por chave pega a coluna.
    connection.execute(statement.on_conflict_do_update(
        index_elements=[Recommendation.user_id],
        set_={"run_id": newer.run_id, "generated_at": newer.generated_at, "items": newer["items"]},
    ))
    return True


def _save_retrain_request(connection: Connection, event: RetrainRequestedEvent) -> bool:
    return bool(connection.execute(insert(RetrainRequest).values(
        event_id=event.event_id, requested_at=event.requested_at, requested_ts=epoch(event.requested_at),
        source=event.source, force=event.force,
        observed_counts=json.dumps(event.observed_counts) if event.observed_counts is not None else None,
    ).on_conflict_do_nothing()).rowcount)


def _save_model(connection: Connection, event: ModelReadyEvent) -> bool:
    return bool(connection.execute(insert(ModelVersion).values(
        run_id=event.run_id, metric_name=event.metric_name, metric_value=event.metric_value,
        trained_until_counts=json.dumps(event.trained_until_counts), created_at=event.created_at,
        created_ts=epoch(event.created_at),
    ).on_conflict_do_nothing()).rowcount)


class Projector:
    """Consumes in a background thread; commits the offsets only after the SQLite transaction."""

    def __init__(self, engine: Engine, consumer_factory: Callable[[], Consumer],
                 on_projected: Callable[[list[Projected]], None]):
        self._engine = engine
        self._consumer_factory = consumer_factory
        self._on_projected = on_projected
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="kafka-projector", daemon=True)
        self.projected = 0
        self.lag: int | None = None

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop.is_set():
            consumer = None
            try:
                consumer = self._consumer_factory()
                consumer.subscribe(list(FEEDS))
                measured = 0.0
                while not self._stop.is_set():
                    self._step(consumer)
                    if time.monotonic() - measured >= 5:
                        self._measure_lag(consumer)
                        measured = time.monotonic()
            except Exception:
                LOG.exception("Projetor falhou; reiniciando sem confirmar o lote atual")
                self._stop.wait(3)
            finally:
                if consumer is not None:
                    consumer.close()

    def _step(self, consumer: Consumer) -> None:
        messages = consumer.consume(num_messages=500, timeout=1.0)
        if not messages:
            return
        records = []
        for message in messages:
            if message.error():
                raise KafkaException(message.error())
            key = message.key()
            _, timestamp_ms = message.timestamp()
            records.append(Record(message.topic(), key.decode() if key else None, message.value(),
                                  timestamp_ms / 1000 if timestamp_ms > 0 else time.time()))
        projected = project(self._engine, records)
        consumer.commit(asynchronous=False)
        self.projected += len(projected)
        if projected:
            self._on_projected(projected)

    def _measure_lag(self, consumer: Consumer) -> None:
        """Messages still to project: high watermark minus position, summed over the assigned partitions.
        Until a partition delivers something its position is unknown, so the committed offset stands in."""
        assignment = consumer.assignment()
        if not assignment:
            return
        try:
            committed = {(item.topic, item.partition): item.offset
                         for item in consumer.committed(assignment, timeout=2)}
            total = 0
            for partition in consumer.position(assignment):
                low, high = consumer.get_watermark_offsets(partition, timeout=2, cached=False)
                offset = partition.offset if partition.offset >= 0 else committed.get((partition.topic, partition.partition), -1)
                total += max(0, high - (offset if offset >= 0 else low))
            self.lag = total
        except KafkaException as error:
            LOG.warning("Não foi possível medir o atraso do projetor: %s", error)
