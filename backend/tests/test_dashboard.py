def _model(run_id, ndcg, created_at, **counts):
    return {"schema_version": 1, "event_id": f"model_ready:{run_id}", "type": "model.ready", "run_id": run_id,
            "bundle_uri": f"runs:/{run_id}/bundle", "metric_name": "NDCG@10", "metric_value": ndcg,
            "trained_until_counts": counts, "created_at": created_at}


def _request(event_id, requested_at, source="sqlite-monitor", force=False, **counts):
    payload = {"schema_version": 1, "event_id": event_id, "type": "recommender.retrain.requested",
               "requested_at": requested_at, "source": source, "force": force}
    return payload | ({"observed_counts": counts} if counts else {})


def test_dashboard_counts_new_events_since_the_model_in_use(logged_in, publisher, eventually):
    publisher.append("recommender-ready", "ensemble",
                     _model("run-1", 0.47, "2026-10-02T10:00:00Z", views=0, comments=0, reviews=0))
    for restaurant in ("r-pizza", "r-sushi"):
        logged_in.post(f"/api/restaurants/{restaurant}/views")
    logged_in.put("/api/restaurants/r-pizza/rating", json={"stars": 5})

    body = eventually(lambda: (page := logged_in.get("/api/dashboard").json())["totals"]["reviews"] == 1
                      and page["current_model"] and page)

    assert body["totals"] == {"views": 2, "comments": 0, "reviews": 1}
    assert body["next_training"] == {"threshold": 300, "new_events": 3, "remaining": 297}
    assert body["current_model"]["run_id"] == "run-1"
    assert len(body["events_per_minute"]) == 15
    assert body["events_per_minute"][-1] | {"minute": None} == {"minute": None, "views": 2, "comments": 0,
                                                                 "reviews": 1}
    assert [event["type"] for event in body["recent_events"]].count("restaurant.viewed") == 2
    rating = next(event for event in body["recent_events"] if event["type"] == "restaurant.rated")
    assert (rating["restaurant_id"], rating["stars"], rating["recorded_at"][-1]) == ("r-pizza", 5, "Z")


def test_models_and_requests_are_listed_newest_first(client, publisher, eventually):
    for topic, payload in [
        ("recommender-retrain", _request("retrain:a", "2026-10-02T10:00:00Z", views=10, comments=5, reviews=5)),
        ("recommender-ready", _model("run-1", 0.47, "2026-10-02T10:01:00Z", views=10, comments=5, reviews=5)),
        ("recommender-retrain", _request("retrain:b", "2026-10-02T11:00:00Z", views=400, comments=5, reviews=5)),
        ("recommender-ready", _model("run-2", 0.51, "2026-10-02T11:01:00Z", views=400, comments=5, reviews=5)),
        ("recommender-retrain", _request("manual:c", "2026-10-02T12:00:00Z", source="cli", force=True)),
    ]:
        publisher.append(topic, "ensemble", payload)

    body = eventually(lambda: len((page := client.get("/api/dashboard").json())["retrain_requests"]) == 3
                      and len(page["models"]) == 2 and page)

    assert [model["run_id"] for model in body["models"]] == ["run-2", "run-1"]
    assert (body["current_model"]["metric_value"], body["current_model"]["trained_until_total"]) == (0.51, 410)
    assert [(item["event_id"], item["observed_total"], item["force"]) for item in body["retrain_requests"]] == \
        [("manual:c", None, True), ("retrain:b", 410, False), ("retrain:a", 20, False)]
    assert body["request_after_last_model"] is True


def test_retrain_shortcut_publishes_a_forced_request(client, publisher, eventually):
    response = client.post("/api/admin/retrain", headers={"Idempotency-Key": "painel-0001"})

    assert response.status_code == 202
    assert response.json()["event_id"] == "backend:painel-0001"
    topic, key, payload = publisher.sent[-1]
    assert (topic, key) == ("recommender-retrain", "ensemble")
    assert (payload["type"], payload["source"], payload["force"]) == ("recommender.retrain.requested", "backend", True)
    assert payload["observed_counts"] == {"views": 0, "comments": 0, "reviews": 0}
    body = eventually(lambda: (page := client.get("/api/dashboard").json())["retrain_requests"] and page)
    assert body["retrain_requests"][0]["event_id"] == "backend:painel-0001"


def test_retrain_shortcut_answers_503_when_kafka_is_down(client, publisher):
    publisher.down = True

    response = client.post("/api/admin/retrain")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
