import json

from sqlalchemy import func, select

from tastematch_api.kafka.projector import Record, project
from tastematch_api.store import (Interaction, ModelVersion, Rating, Recommendation, RetrainRequest,
                                  create_db_engine)


def _record(topic, key, **event):
    return Record(topic, key, json.dumps(event).encode(), 1_759_400_000.0)


def _review(event_id, stars, occurred_at, key="u-1"):
    return _record("review-restaurant", key, schema_version=1, event_id=event_id, type="restaurant.rated",
                   user_id="u-1", restaurant_id="r-pizza", occurred_at=occurred_at, stars=stars)


def test_api_actions_reach_history_and_restaurant_detail(logged_in, eventually):
    logged_in.put("/api/restaurants/r-pizza/rating", json={"stars": 4})
    logged_in.post("/api/restaurants/r-pizza/comments", json={"text": "Crosta perfeita"})

    history = eventually(lambda: len(items := logged_in.get("/api/me/history").json()) == 2 and items)

    assert {(item["type"], item["restaurant_name"]) for item in history} == \
        {("restaurant.rated", "Tony's Pizza"), ("restaurant.commented", "Tony's Pizza")}
    detail = logged_in.get("/api/restaurants/r-pizza").json()
    assert (detail["my_rating"], detail["rating_average"], detail["rating_count"]) == (4, 4.0, 1)
    assert detail["recent_comments"][0]["text"] == "Crosta perfeita"
    assert detail["recent_comments"][0]["display_name"] == "Perfil Yelp 001"


def test_views_count_in_the_last_hour(logged_in, eventually):
    logged_in.post("/api/restaurants/r-sushi/views")

    views = eventually(lambda: logged_in.get("/api/restaurants/r-sushi").json()["views_last_hour"])

    assert views == 1


def test_latest_rating_wins_and_redelivery_is_ignored(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    first = _review("review-1", 2, "2020-01-01T00:00:00Z")
    later = _review("review-2", 5, "2021-01-01T00:00:00.250Z")
    older = _review("review-0", 1, "2019-01-01T00:00:00Z")

    projected = project(engine, [first, later, first, older])

    assert [item.event.event_id for item in projected] == ["review-1", "review-2", "review-0"]
    with engine.connect() as connection:
        assert connection.scalar(select(Rating.stars)) == 5
        assert connection.scalar(select(func.count()).select_from(Interaction)) == 3


def test_invalid_messages_are_skipped_without_blocking_the_batch(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    records = [
        Record("review-restaurant", "u-1", b"{not json", 0.0),
        Record("review-restaurant", "u-1", None, 0.0),
        _review("wrong-key", 4, "2026-10-02T10:00:00Z", key="u-2"),
        _review("bad-stars", 9, "2026-10-02T10:00:00Z"),
        _review("no-zone", 3, "2026-10-02T10:00:00"),
        _record("comment-restaurant", "u-1", schema_version=1, event_id="wrong-type", type="restaurant.rated",
                user_id="u-1", restaurant_id="r-pizza", occurred_at="2026-10-02T10:00:00Z", text="oi"),
        _record("comment-restaurant", "u-1", schema_version=1, event_id="blank-text", type="restaurant.commented",
                user_id="u-1", restaurant_id="r-pizza", occurred_at="2026-10-02T10:00:00Z", text="   "),
        _review("valid", 4, "2026-10-02T10:00:00Z"),
    ]

    assert [item.event.event_id for item in project(engine, records)] == ["valid"]


def _recommendations(run_id, *items, key="u-1"):
    return _record("user-recommendations", key, schema_version=1, event_id=f"recs:{run_id}:u-1",
                   type="recommendations.generated", user_id="u-1", run_id=run_id,
                   generated_at="2026-10-02T17:00:00Z", items=list(items))


def test_recommendation_lists_replace_each_other_and_repeats_stay_quiet(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    first = _recommendations("run-1", "r-pizza", "r-sushi")

    projected = project(engine, [first, first, _recommendations("run-2", "r-sushi"),
                                 _recommendations("run-3", "r-pizza", key="u-2")])

    assert [item.event.run_id for item in projected] == ["run-1", "run-2"]
    with engine.connect() as connection:
        assert tuple(connection.execute(select(Recommendation.run_id, Recommendation.items)).one()) == \
            ("run-2", '["r-sushi"]')


def test_training_events_are_kept_once_whatever_the_key(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    counts = {"views": 3, "comments": 1, "reviews": 1}
    request = _record("recommender-retrain", "ensemble", schema_version=1, event_id="retrain:x",
                      type="recommender.retrain.requested", requested_at="2026-10-02T10:00:00.123456Z",
                      source="sqlite-monitor", observed_counts=counts)
    ready = _record("recommender-ready", "ensemble", schema_version=1, event_id="model_ready:r", type="model.ready",
                    run_id="r", metric_name="NDCG@10", metric_value=0.5, trained_until_counts=counts,
                    created_at="2026-10-02T10:01:00Z")
    unknown_type = _record("recommender-ready", "ensemble", schema_version=1, event_id="x", type="model.trained",
                           run_id="r2", metric_value=0.5, trained_until_counts=counts,
                           created_at="2026-10-02T10:02:00Z")

    projected = project(engine, [request, ready, request, ready, unknown_type])

    assert [type(item.event).__name__ for item in projected] == ["RetrainRequestedEvent", "ModelReadyEvent"]
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(RetrainRequest)) == 1
        assert connection.scalar(select(ModelVersion.metric_value)) == 0.5
