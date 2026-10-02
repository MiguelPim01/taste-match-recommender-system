def _list_for(user_id, *items, run_id="run-1"):
    return {"schema_version": 1, "event_id": f"recs:{run_id}:{user_id}", "type": "recommendations.generated",
            "user_id": user_id, "run_id": run_id, "generated_at": "2026-10-02T17:00:00Z", "items": list(items)}


def _rating(user_id, restaurant_id, stars):
    return {"schema_version": 1, "event_id": f"review:{user_id}:{restaurant_id}", "type": "restaurant.rated",
            "user_id": user_id, "restaurant_id": restaurant_id, "occurred_at": "2026-10-01T12:00:00Z",
            "stars": stars}


def _ids(body):
    return [(item["source"], item["restaurant"]["id"]) for item in body["items"]]


def test_profile_without_a_list_gets_what_is_popular_now(logged_in, publisher, eventually):
    publisher.append("review-restaurant", "yelp-b", _rating("yelp-b", "r-sushi", 5))

    body = eventually(lambda: (page := logged_in.get("/api/me/recommendations").json())
                      ["items"][0]["restaurant"]["id"] == "r-sushi" and page)

    assert body["source"] == "popular" and body["model"] is None
    assert _ids(body) == [("popular", "r-sushi"), ("popular", "r-pizza")]


def test_model_list_comes_first_and_drops_what_was_seen_since(logged_in, publisher, eventually):
    publisher.append("user-recommendations", "yelp-a", _list_for("yelp-a", "r-pizza", "r-sushi"))

    body = eventually(lambda: (page := logged_in.get("/api/me/recommendations").json())["source"] == "model" and page)

    assert _ids(body) == [("model", "r-pizza"), ("model", "r-sushi")]
    assert body["model"] == {"run_id": "run-1", "generated_at": "2026-10-02T17:00:00Z"}
    assert body["items"][0]["restaurant"]["name"] == "Tony's Pizza"

    logged_in.post("/api/restaurants/r-pizza/views")
    body = eventually(lambda: len((page := logged_in.get("/api/me/recommendations").json())["items"]) == 1 and page)

    assert _ids(body) == [("model", "r-sushi")]


def test_short_list_is_topped_up_with_popular(logged_in, publisher, eventually):
    publisher.append("user-recommendations", "yelp-a", _list_for("yelp-a", "r-sushi"))

    body = eventually(lambda: (page := logged_in.get("/api/me/recommendations").json())["source"] == "mixed" and page)

    assert _ids(body) == [("model", "r-sushi"), ("popular", "r-pizza")]


def test_recommendations_require_a_session(client):
    assert client.get("/api/me/recommendations").status_code == 401
