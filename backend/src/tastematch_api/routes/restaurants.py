"""Restaurant catalog: the 300 Philadelphia restaurants of the Yelp sample, with live numbers from the projection."""

from __future__ import annotations

import time
from collections import Counter
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tastematch_api.contracts import COMMENT, VIEW
from tastematch_api.deps import SESSION_COOKIE, Db
from tastematch_api.store import Interaction, Rating, Restaurant, User


router = APIRouter(prefix="/api/restaurants", tags=["catálogo"])

# Every restaurant in the sample has one of these, so they would not narrow anything.
GENERIC_CATEGORIES = {"Restaurants", "Food"}

ORDER = {
    "popular": (Restaurant.review_count.desc(), Restaurant.id),
    "stars": (Restaurant.stars.desc(), Restaurant.review_count.desc(), Restaurant.id),
    "name": (Restaurant.name, Restaurant.id),
}


class RestaurantOut(BaseModel):
    id: str
    name: str
    address: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    stars: float | None
    review_count: int
    categories: list[str]
    rating_average: float | None
    rating_count: int
    views_last_hour: int


class CommentOut(BaseModel):
    user_id: str
    display_name: str | None
    text: str
    occurred_at: str


class RestaurantDetail(RestaurantOut):
    recent_comments: list[CommentOut]
    my_rating: int | None


class RestaurantPage(BaseModel):
    total: int
    items: list[RestaurantOut]


@router.get("")
def list_restaurants(
    db: Db,
    q: Annotated[str | None, Query(max_length=80, description="Busca no nome e nas categorias")] = None,
    category: Annotated[str | None, Query(max_length=80, description="Categoria exata, como Pizza")] = None,
    sort: Literal["popular", "stars", "name"] = "popular",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RestaurantPage:
    query = select(Restaurant)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Restaurant.name.ilike(pattern), Restaurant.categories.ilike(pattern)))
    if category:
        query = query.where(Restaurant.categories.like(f"%|{category}|%"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(db.scalars(query.order_by(*ORDER[sort]).limit(limit).offset(offset)))
    return RestaurantPage(total=total, items=with_live_numbers(db, rows))


class CategoryCount(BaseModel):
    name: str
    count: int


@router.get("/categories")
def list_categories(db: Db) -> list[CategoryCount]:
    """Catalog categories, most common first. Declared before /{restaurant_id} so the path is not taken as an ID."""
    counts = Counter(category for categories in db.scalars(select(Restaurant.categories))
                     for category in categories.split("|") if category and category not in GENERIC_CATEGORIES)
    return [CategoryCount(name=name, count=count)
            for name, count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))]


@router.get("/{restaurant_id}")
def get_restaurant(restaurant_id: str, request: Request, db: Db) -> RestaurantDetail:
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(404, "Restaurante não está no catálogo")
    comments = db.execute(
        select(Interaction, User.display_name).outerjoin(User, User.id == Interaction.user_id)
        .where(Interaction.restaurant_id == restaurant_id, Interaction.type == COMMENT.event_type)
        .order_by(Interaction.occurred_ts.desc(), Interaction.event_id.desc()).limit(5)
    )
    user_id = request.cookies.get(SESSION_COOKIE)
    rating = db.get(Rating, (user_id, restaurant_id)) if user_id else None
    return RestaurantDetail(
        **with_live_numbers(db, [restaurant])[0].model_dump(),
        recent_comments=[CommentOut(user_id=comment.user_id, display_name=name, text=comment.text,
                                    occurred_at=comment.occurred_at) for comment, name in comments],
        my_rating=rating.stars if rating else None,
    )


def with_live_numbers(db: Session, restaurants: list[Restaurant]) -> list[RestaurantOut]:
    """Average of each profile's latest rating, and views published to Kafka in the last hour."""
    ids = [restaurant.id for restaurant in restaurants]
    ratings = {restaurant_id: (average, count) for restaurant_id, average, count in db.execute(
        select(Rating.restaurant_id, func.avg(Rating.stars), func.count())
        .where(Rating.restaurant_id.in_(ids)).group_by(Rating.restaurant_id)
    )}
    views = dict(db.execute(
        select(Interaction.restaurant_id, func.count())
        .where(Interaction.restaurant_id.in_(ids), Interaction.type == VIEW.event_type,
               Interaction.recorded_ts >= time.time() - 3600)
        .group_by(Interaction.restaurant_id)
    ).all())
    result = []
    for restaurant in restaurants:
        average, count = ratings.get(restaurant.id, (None, 0))
        result.append(RestaurantOut(
            id=restaurant.id, name=restaurant.name, address=restaurant.address, city=restaurant.city,
            state=restaurant.state, postal_code=restaurant.postal_code, latitude=restaurant.latitude,
            longitude=restaurant.longitude, stars=restaurant.stars, review_count=restaurant.review_count,
            categories=restaurant.category_list, rating_average=round(average, 2) if average is not None else None,
            rating_count=count, views_last_hour=views.get(restaurant.id, 0),
        ))
    return result
