"""Kafka publisher that only returns after the brokers acknowledge the write."""

from __future__ import annotations

import json
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Protocol

from confluent_kafka import KafkaException, Producer


class PublishError(RuntimeError):
    """Kafka did not confirm the write."""


@dataclass(frozen=True)
class Delivery:
    topic: str
    partition: int
    offset: int


class Publisher(Protocol):
    def publish(self, topic: str, key: str, payload: dict) -> Delivery: ...

    def ping(self) -> bool: ...

    def close(self) -> None: ...


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str, timeout_s: float):
        self._timeout_s = timeout_s
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": "tastematch-backend",
            "acks": "all",
            "enable.idempotence": True,
            "message.timeout.ms": int(timeout_s * 1000),
        })
        self._stop = threading.Event()
        # Delivery callbacks only run inside poll(); this thread serves them for every request.
        self._poller = threading.Thread(target=self._poll, name="kafka-delivery", daemon=True)
        self._poller.start()

    def _poll(self) -> None:
        while not self._stop.is_set():
            self._producer.poll(0.2)

    def publish(self, topic: str, key: str, payload: dict) -> Delivery:
        result: Future[Delivery] = Future()

        def delivered(error, message) -> None:
            if error is not None:
                result.set_exception(PublishError(str(error)))
            else:
                result.set_result(Delivery(message.topic(), message.partition(), message.offset()))

        try:
            self._producer.produce(topic, key=key.encode(), on_delivery=delivered,
                                   value=json.dumps(payload, ensure_ascii=False).encode())
        except (BufferError, KafkaException) as error:
            raise PublishError(str(error)) from error
        try:
            return result.result(timeout=self._timeout_s + 5)
        except FutureTimeout as error:
            raise PublishError("Kafka não confirmou a gravação a tempo") from error

    def ping(self) -> bool:
        try:
            self._producer.list_topics(timeout=3)
            return True
        except KafkaException:
            return False

    def close(self) -> None:
        self._stop.set()
        self._poller.join(timeout=2)
        self._producer.flush(5)
