def test_simulation_publishes_a_view_a_good_rating_and_a_positive_comment(logged_in, publisher, eventually):
    response = logged_in.post("/api/me/simulate", json={"category": "Pizza", "restaurants": 3})

    assert response.status_code == 202
    body = response.json()
    assert [restaurant["id"] for restaurant in body["restaurants"]] == ["r-pizza"]
    assert len(body["event_ids"]) == 3 and body["skipped_views"] == 0
    published = {topic: payload for topic, _, payload in publisher.sent}
    assert published["review-restaurant"]["stars"] == 5
    assert "Pizza" in published["comment-restaurant"]["text"] and "Loved" in published["comment-restaurant"]["text"]
    assert eventually(lambda: len(logged_in.get("/api/me/history").json()) == 3)


def test_repeating_a_simulation_skips_the_recent_view(logged_in, publisher):
    logged_in.post("/api/me/simulate", json={"category": "Pizza", "restaurants": 1})

    body = logged_in.post("/api/me/simulate", json={"category": "Pizza", "restaurants": 1}).json()

    assert body["skipped_views"] == 1 and len(body["event_ids"]) == 2


def test_unknown_category_is_rejected(logged_in, publisher):
    assert logged_in.post("/api/me/simulate", json={"category": "Nada", "restaurants": 2}).status_code == 404
    assert publisher.sent == []


def test_category_activity_counts_every_category_of_each_interaction(logged_in, eventually):
    logged_in.post("/api/me/simulate", json={"category": "Italian", "restaurants": 1})
    logged_in.post("/api/restaurants/r-sushi/views")

    rows = eventually(lambda: len(activity := logged_in.get("/api/me/categories").json()) == 4 and activity)

    assert rows == [
        {"category": "Italian", "views": 1, "comments": 1, "reviews": 1, "total": 3},
        {"category": "Pizza", "views": 1, "comments": 1, "reviews": 1, "total": 3},
        {"category": "Japanese", "views": 1, "comments": 0, "reviews": 0, "total": 1},
        {"category": "Sushi Bars", "views": 1, "comments": 0, "reviews": 0, "total": 1},
    ]


def test_category_activity_requires_a_session(client):
    assert client.get("/api/me/categories").status_code == 401
