import asyncio

import pytest

from tastematch_api.contracts import REVIEW, ModelReadyEvent, RecommendationsEvent, RetrainRequestedEvent
from tastematch_api.kafka.projector import Projected
from tastematch_api.realtime.hub import Hub


def _rating_by(user_id):
    return Projected(REVIEW.build(user_id, "r-pizza", None, stars=5), 0.0)


def test_confirmation_reaches_every_tab_of_the_author_only():
    async def scenario():
        hub = Hub(asyncio.get_running_loop())
        tab, second_tab, someone_else = hub.listen("yelp-a"), hub.listen("yelp-a"), hub.listen("yelp-b")
        for stream in (tab, second_tab, someone_else):
            assert (await anext(stream)).event == "ready"

        rating = _rating_by("yelp-a")
        hub.projected([rating])

        for stream in (tab, second_tab):
            received = await asyncio.wait_for(anext(stream), 1)
            assert received.event == "interaction.recorded"
            assert received.data["event_id"] == rating.event.event_id
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(someone_else), 0.1)

    asyncio.run(scenario())


def test_activity_summary_reaches_everyone_and_close_ends_the_streams():
    async def scenario():
        hub = Hub(asyncio.get_running_loop())
        dashboard, member = hub.listen(None), hub.listen("yelp-a")
        await anext(dashboard)
        await anext(member)

        hub.projected([_rating_by("yelp-b"), _rating_by("yelp-b")])
        await asyncio.sleep(0)
        hub.flush_activity(5.0)

        for stream in (dashboard, member):
            activity = await asyncio.wait_for(anext(stream), 1)
            assert activity.event == "activity"
            assert activity.data["counts"] == {"restaurant.rated": 2}
            assert len(activity.data["recent"]) == 2

        hub.flush_activity(5.0)
        hub.close()
        for stream in (dashboard, member):
            with pytest.raises(StopAsyncIteration):
                await asyncio.wait_for(anext(stream), 1)

    asyncio.run(scenario())


def test_new_list_is_announced_to_its_owner_only_and_is_not_activity():
    async def scenario():
        hub = Hub(asyncio.get_running_loop())
        owner, someone_else = hub.listen("yelp-a"), hub.listen("yelp-b")
        await anext(owner)
        await anext(someone_else)

        hub.projected([Projected(RecommendationsEvent(
            event_id="recs:run-1:yelp-a", type="recommendations.generated", user_id="yelp-a", run_id="run-1",
            generated_at="2026-10-02T17:00:00Z", items=["r-pizza", "r-sushi"]), 0.0)])
        received = await asyncio.wait_for(anext(owner), 1)

        assert received.event == "recommendations.updated"
        assert received.data == {"run_id": "run-1", "generated_at": "2026-10-02T17:00:00Z", "count": 2}
        hub.flush_activity(5.0)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(someone_else), 0.1)

    asyncio.run(scenario())


def test_training_events_reach_every_tab():
    async def scenario():
        hub = Hub(asyncio.get_running_loop())
        dashboard, member = hub.listen(None), hub.listen("yelp-a")
        await anext(dashboard)
        await anext(member)
        counts = {"views": 200, "comments": 50, "reviews": 50}

        hub.projected([
            Projected(RetrainRequestedEvent(event_id="retrain:x", type="recommender.retrain.requested",
                                            requested_at="2026-10-02T10:00:00Z", source="sqlite-monitor",
                                            observed_counts=counts), 0.0),
            Projected(ModelReadyEvent(event_id="model_ready:r", type="model.ready", run_id="r", metric_value=0.5,
                                      trained_until_counts=counts, created_at="2026-10-02T10:01:00Z"), 0.0),
        ])

        for stream in (dashboard, member):
            requested = await asyncio.wait_for(anext(stream), 1)
            ready = await asyncio.wait_for(anext(stream), 1)
            assert (requested.event, requested.data["observed_total"]) == ("retrain.requested", 300)
            assert (ready.event, ready.data["metric_value"], ready.data["trained_until_total"]) == \
                ("model.ready", 0.5, 300)

    asyncio.run(scenario())
