from datetime import datetime


def test_rating_follows_contract_v1(logged_in, publisher):
    response = logged_in.put("/api/restaurants/r-pizza/rating", json={"stars": 4},
                             headers={"Idempotency-Key": "retry-key-0001"})

    assert response.status_code == 202
    assert response.json() == {"status": "published", "event_id": "app:review:retry-key-0001",
                               "type": "restaurant.rated", "topic": "review-restaurant", "partition": 0, "offset": 0}
    topic, key, payload = publisher.sent[0]
    assert (topic, key) == ("review-restaurant", "yelp-a")
    assert set(payload) == {"schema_version", "event_id", "type", "user_id", "restaurant_id", "occurred_at", "stars"}
    assert payload["schema_version"] == 1
    assert payload["user_id"] == "yelp-a" and payload["restaurant_id"] == "r-pizza" and payload["stars"] == 4
    assert payload["occurred_at"].endswith("Z")
    datetime.fromisoformat(payload["occurred_at"].replace("Z", "+00:00"))


def test_retry_with_same_key_reuses_event_id(logged_in, publisher):
    for _ in range(2):
        logged_in.post("/api/restaurants/r-sushi/comments", json={"text": "Great fish"},
                       headers={"Idempotency-Key": "same-key-123"})

    assert [payload["event_id"] for _, _, payload in publisher.sent] == ["app:comment:same-key-123"] * 2


def test_comment_is_trimmed_and_cannot_be_blank(logged_in, publisher):
    assert logged_in.post("/api/restaurants/r-sushi/comments", json={"text": "   "}).status_code == 422

    response = logged_in.post("/api/restaurants/r-sushi/comments", json={"text": "  Excellent food.  "})

    assert response.status_code == 202
    topic, _, payload = publisher.sent[-1]
    assert topic == "comment-restaurant"
    assert payload["type"] == "restaurant.commented" and payload["text"] == "Excellent food."


def test_stars_outside_one_to_five_are_rejected(logged_in, publisher):
    for stars in (0, 6):
        assert logged_in.put("/api/restaurants/r-pizza/rating", json={"stars": stars}).status_code == 422
    assert publisher.sent == []


def test_repeated_view_is_skipped(logged_in, publisher):
    statuses = [logged_in.post(f"/api/restaurants/{restaurant}/views").json()["status"]
                for restaurant in ("r-pizza", "r-pizza", "r-sushi")]

    assert statuses == ["published", "skipped", "published"]
    assert [(topic, payload["type"]) for topic, _, payload in publisher.sent] == \
        [("view-restaurant", "restaurant.viewed")] * 2


def test_failed_view_can_be_retried(logged_in, publisher):
    publisher.down = True
    assert logged_in.post("/api/restaurants/r-pizza/views").status_code == 503

    publisher.down = False

    assert logged_in.post("/api/restaurants/r-pizza/views").json()["status"] == "published"


def test_interactions_require_a_session(client, publisher):
    assert client.post("/api/restaurants/r-pizza/views").status_code == 401
    assert publisher.sent == []


def test_unknown_restaurant_is_not_published(logged_in, publisher):
    assert logged_in.put("/api/restaurants/nao-existe/rating", json={"stars": 5}).status_code == 404
    assert publisher.sent == []


def test_kafka_down_answers_503_with_retry_after(logged_in, publisher):
    publisher.down = True

    response = logged_in.put("/api/restaurants/r-pizza/rating", json={"stars": 5})

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


def test_malformed_idempotency_key_is_rejected(logged_in, publisher):
    response = logged_in.put("/api/restaurants/r-pizza/rating", json={"stars": 5}, headers={"Idempotency-Key": "a b"})

    assert response.status_code == 422
    assert publisher.sent == []
