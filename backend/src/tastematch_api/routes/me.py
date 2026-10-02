"""What the session profile did and what to show it next, both read from the projection; plus the test simulator."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from tastematch_api.contracts import COMMENT, REVIEW, VIEW, NonBlank
from tastematch_api.deps import CurrentUser, Db, Pub
from tastematch_api.routes.dashboard import SIGNALS
from tastematch_api.routes.interactions import ViewThrottle, publish_interaction
from tastematch_api.routes.restaurants import GENERIC_CATEGORIES, RestaurantOut, with_live_numbers
from tastematch_api.store import Interaction, Rating, Recommendation, Restaurant

# English on purpose: training scores comments with VADER, which only reads English.
POSITIVE_COMMENTS = [
    "Great {category} spot. Loved the food and the friendly staff!",
    "Excellent {category}: fresh, delicious and worth the visit.",
    "Amazing {category} experience, great flavors and quick service.",
]


router = APIRouter(prefix="/api/me", tags=["perfis"])


class HistoryItem(BaseModel):
    event_id: str
    type: str
    restaurant_id: str
    restaurant_name: str | None
    stars: int | None
    text: str | None
    occurred_at: str


class ModelVersion(BaseModel):
    run_id: str
    generated_at: str


class RecommendedItem(BaseModel):
    source: Literal["model", "popular"]
    restaurant: RestaurantOut


class Recommendations(BaseModel):
    source: Literal["model", "mixed", "popular"]
    model: ModelVersion | None
    items: list[RecommendedItem]


class CategoryActivity(BaseModel):
    category: str
    views: int
    comments: int
    reviews: int
    total: int


class SimulationIn(BaseModel):
    category: NonBlank
    restaurants: int = Field(default=6, ge=1, le=20)


class SimulatedRestaurant(BaseModel):
    id: str
    name: str


class Simulation(BaseModel):
    category: str
    restaurants: list[SimulatedRestaurant]
    event_ids: list[str]
    skipped_views: int


@router.get("/history")
def history(user: CurrentUser, db: Db, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[HistoryItem]:
    rows = db.execute(
        select(Interaction, Restaurant.name).outerjoin(Restaurant, Restaurant.id == Interaction.restaurant_id)
        .where(Interaction.user_id == user.id)
        .order_by(Interaction.occurred_ts.desc(), Interaction.event_id.desc()).limit(limit)
    )
    return [HistoryItem(event_id=interaction.event_id, type=interaction.type, restaurant_id=interaction.restaurant_id,
                        restaurant_name=name, stars=interaction.stars, text=interaction.text,
                        occurred_at=interaction.occurred_at) for interaction, name in rows]


@router.get("/recommendations")
def recommendations(user: CurrentUser, db: Db, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> Recommendations:
    """The model list minus what the profile saw since training, topped up with what is popular now."""
    seen = set(db.scalars(select(Interaction.restaurant_id).where(Interaction.user_id == user.id).distinct()))
    saved = db.get(Recommendation, user.id)
    chosen = [(restaurant_id, "model") for restaurant_id in (json.loads(saved.items) if saved else [])
              if restaurant_id not in seen][:limit]
    if len(chosen) < limit:
        taken = seen | {restaurant_id for restaurant_id, _ in chosen}
        chosen += [(restaurant_id, "popular") for restaurant_id in _popular_now(db)
                   if restaurant_id not in taken][:limit - len(chosen)]

    catalog = {restaurant.id: restaurant for restaurant in
               db.scalars(select(Restaurant).where(Restaurant.id.in_([restaurant_id for restaurant_id, _ in chosen])))}
    chosen = [(restaurant_id, source) for restaurant_id, source in chosen if restaurant_id in catalog]
    restaurants = with_live_numbers(db, [catalog[restaurant_id] for restaurant_id, _ in chosen])
    sources = {source for _, source in chosen}
    return Recommendations(
        source="mixed" if len(sources) == 2 else ("model" if sources == {"model"} else "popular"),
        model=ModelVersion(run_id=saved.run_id, generated_at=saved.generated_at) if saved else None,
        items=[RecommendedItem(source=source, restaurant=restaurant)
               for (_, source), restaurant in zip(chosen, restaurants)],
    )


@router.get("/categories")
def category_activity(user: CurrentUser, db: Db) -> list[CategoryActivity]:
    """How many of the profile's interactions touched each category; one interaction counts for every category
    of its restaurant."""
    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    rows = db.execute(select(Interaction.type, Restaurant.categories)
                      .join(Restaurant, Restaurant.id == Interaction.restaurant_id)
                      .where(Interaction.user_id == user.id))
    for event_type, categories in rows:
        for category in categories.split("|"):
            if category and category not in GENERIC_CATEGORIES:
                counts[category][SIGNALS[event_type]] += 1
    activity = [CategoryActivity(category=category, views=count["views"], comments=count["comments"],
                                 reviews=count["reviews"], total=sum(count.values()))
                for category, count in counts.items()]
    return sorted(activity, key=lambda row: (-row.total, row.category))


@router.post("/simulate", status_code=202)
def simulate(body: SimulationIn, request: Request, user: CurrentUser, db: Db, publisher: Pub) -> Simulation:
    """Test tool: a view, a 4 or 5 star rating and a positive comment per restaurant of one category, published
    through Kafka exactly like the app's own actions. Unseen restaurants come first, so repeated runs widen the taste."""
    candidates = list(db.scalars(select(Restaurant).where(Restaurant.categories.like(f"%|{body.category}|%"))
                                 .order_by(Restaurant.review_count.desc(), Restaurant.id)))
    if not candidates:
        raise HTTPException(404, "Nenhum restaurante nessa categoria")
    seen = set(db.scalars(select(Interaction.restaurant_id).where(Interaction.user_id == user.id).distinct()))
    chosen = ([restaurant for restaurant in candidates if restaurant.id not in seen]
              + [restaurant for restaurant in candidates if restaurant.id in seen])[:body.restaurants]

    throttle: ViewThrottle = request.app.state.view_throttle
    event_ids: list[str] = []
    skipped_views = 0
    for index, restaurant in enumerate(chosen):
        if throttle.seen_recently(user.id, restaurant.id):
            skipped_views += 1
        else:
            event_ids.append(publish_interaction(publisher, VIEW, VIEW.build(user.id, restaurant.id, None)).event_id)
            throttle.mark(user.id, restaurant.id)
        rating = REVIEW.build(user.id, restaurant.id, None, stars=5 if index % 2 == 0 else 4)
        comment = COMMENT.build(user.id, restaurant.id, None,
                                text=POSITIVE_COMMENTS[index % len(POSITIVE_COMMENTS)].format(category=body.category))
        event_ids.append(publish_interaction(publisher, REVIEW, rating).event_id)
        event_ids.append(publish_interaction(publisher, COMMENT, comment).event_id)
    return Simulation(category=body.category, event_ids=event_ids, skipped_views=skipped_views,
                      restaurants=[SimulatedRestaurant(id=restaurant.id, name=restaurant.name) for restaurant in chosen])


def _popular_now(db: Session) -> list[str]:
    """Restaurants with the most 4 and 5 star ratings, counting each profile's latest rating once."""
    return list(db.scalars(
        select(Restaurant.id)
        .outerjoin(Rating, and_(Rating.restaurant_id == Restaurant.id, Rating.stars >= 4))
        .group_by(Restaurant.id)
        .order_by(func.count(Rating.user_id).desc(), Restaurant.review_count.desc(), Restaurant.id)
    ))
