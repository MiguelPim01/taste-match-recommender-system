"""Small JSON Kafka adapter for replay and training lifecycle events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import sleep

from confluent_kafka import Producer


TOPICS = {
    "restaurant.viewed": "view-restaurant",
    "restaurant.commented": "comment-restaurant",
    "restaurant.rated": "review-restaurant",
}
REQUEST_TOPIC = "recommender-retrain"
READY_TOPIC = "recommender-ready"


def bootstrap_servers() -> str:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092,localhost:39092,localhost:49092")


def producer() -> Producer:
    return Producer({"bootstrap.servers": bootstrap_servers(), "acks": "all", "enable.idempotence": True})


def publish(client: Producer, topic: str, key: str, payload: dict) -> None:
    result = []

    def delivered(error, _message):
        result.append(error)

    client.produce(topic, key=key.encode(), value=json.dumps(payload, ensure_ascii=False).encode(),
                   on_delivery=delivered)
    if client.flush(30) != 0 or not result or result[0] is not None:
        raise RuntimeError(f"Falha ao publicar em {topic}: {result}")


def replay(path: Path, interval_ms: int = 0) -> dict[str, int]:
    client = producer()
    counts = {topic: 0 for topic in TOPICS.values()}
    with path.open(encoding="utf-8") as source:
        for line in source:
            event = json.loads(line)
            topic = TOPICS[event["type"]]
            publish(client, topic, event["user_id"], event)
            counts[topic] += 1
            if interval_ms:
                sleep(interval_ms / 1000)
    return counts
