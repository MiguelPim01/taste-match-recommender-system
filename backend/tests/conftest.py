from __future__ import annotations

import json
import queue
import time

import pytest
from fastapi.testclient import TestClient

from tastematch_api.kafka.producer import Delivery, PublishError
from tastematch_api.main import create_app
from tastematch_api.settings import Settings


CATALOG = [
    {"id": "r-pizza", "name": "Tony's Pizza", "address": "1 Market St", "city": "Philadelphia", "state": "PA",
     "postal_code": "19106", "latitude": 39.95, "longitude": -75.15, "stars": 4.5, "review_count": 900,
     "categories": ["Pizza", "Italian", "Restaurants"]},
    {"id": "r-sushi", "name": "Sushi Bar", "address": "2 Walnut St", "city": "Philadelphia", "state": "PA",
     "postal_code": "19103", "latitude": 39.94, "longitude": -75.16, "stars": 4.0, "review_count": 300,
     "categories": ["Sushi Bars", "Japanese", "Restaurants"]},
]


class FakeMessage:
    def __init__(self, topic: str, key: bytes | None, value: bytes | None):
        self._topic, self._key, self._value = topic, key, value
        self._timestamp_ms = int(time.time() * 1000)

    def error(self):
        return None

    def topic(self) -> str:
        return self._topic

    def key(self) -> bytes | None:
        return self._key

    def value(self) -> bytes | None:
        return self._value

    def timestamp(self) -> tuple[int, int]:
        return 1, self._timestamp_ms


class FakeConsumer:
    def __init__(self, log: queue.Queue):
        self._log = log

    def subscribe(self, topics: list[str]) -> None:
        pass

    def consume(self, num_messages: int = 1, timeout: float = -1) -> list[FakeMessage]:
        messages = []
        try:
            messages.append(self._log.get(timeout=0.05))
            while len(messages) < num_messages:
                messages.append(self._log.get_nowait())
        except queue.Empty:
            pass
        return messages

    def commit(self, asynchronous: bool = True) -> None:
        pass

    def assignment(self) -> list:
        return []

    def close(self) -> None:
        pass


class FakeKafka:
    """Plays both sides: the API publishes here and the projector consumes from here."""

    def __init__(self):
        self.sent: list[tuple[str, str, dict]] = []
        self.down = False
        self._log: queue.Queue[FakeMessage] = queue.Queue()

    def publish(self, topic: str, key: str, payload: dict) -> Delivery:
        if self.down:
            raise PublishError("brokers fora do ar")
        self.sent.append((topic, key, payload))
        self.append(topic, key, payload)
        return Delivery(topic, 0, len(self.sent) - 1)

    def append(self, topic: str, key: str, payload: dict) -> None:
        """A message from another producer, such as the Yelp replay or the recommendation publisher."""
        self._log.put(FakeMessage(topic, key.encode(), json.dumps(payload).encode()))

    def ping(self) -> bool:
        return not self.down

    def close(self) -> None:
        pass

    def consumer(self) -> FakeConsumer:
        return FakeConsumer(self._log)


@pytest.fixture
def publisher() -> FakeKafka:
    return FakeKafka()


@pytest.fixture
def settings(tmp_path) -> Settings:
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "catalog.json").write_text(json.dumps(CATALOG), encoding="utf-8")
    (sample / "manifest.json").write_text(json.dumps({"users": ["yelp-b", "yelp-a"]}), encoding="utf-8")
    return Settings(kafka_bootstrap_servers="unused:9092", database_url=f"sqlite:///{tmp_path / 'backend.db'}",
                    sample_dir=sample, publish_timeout_s=1, view_dedup_seconds=1800, cors_origins=())


@pytest.fixture
def make_app(settings, publisher):
    return lambda: create_app(settings, publisher=publisher, consumer_factory=publisher.consumer)


@pytest.fixture
def client(make_app):
    with TestClient(make_app()) as test_client:
        yield test_client


@pytest.fixture
def logged_in(client):
    assert client.post("/api/session", json={"user_id": "yelp-a"}).status_code == 200
    return client


@pytest.fixture
def eventually():
    """The projector runs in its own thread; poll until it catches up."""
    def wait(check, timeout_s: float = 3.0):
        deadline = time.monotonic() + timeout_s
        while True:
            result = check()
            if result or time.monotonic() > deadline:
                return result
            time.sleep(0.02)
    return wait
