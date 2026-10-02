"""Backend read model in SQLite: catalog, profiles and the projection of the interaction topics."""

from __future__ import annotations

from sqlalchemy import Boolean, Engine, Float, Index, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    postal_code: Mapped[str | None] = mapped_column(String)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    stars: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    # "|Pizza|Italian|": the delimiters let LIKE match a whole category.
    categories: Mapped[str] = mapped_column(String, default="")

    @property
    def category_list(self) -> list[str]:
        return [category for category in self.categories.split("|") if category]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    origin: Mapped[str] = mapped_column(String)  # "yelp" ou "app"
    created_at: Mapped[str] = mapped_column(String)


class Interaction(Base):
    """One row per event; (type, event_id) is unique, like processed_events in each Java database."""

    __tablename__ = "interactions"
    __table_args__ = (
        Index("ix_interactions_restaurant", "restaurant_id", "type", "recorded_ts"),
        Index("ix_interactions_user", "user_id", "occurred_ts"),
    )

    type: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String)
    restaurant_id: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[str] = mapped_column(String)
    occurred_ts: Mapped[float] = mapped_column(Float)
    stars: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(String)
    # Horário de publicação no Kafka: o replay do Yelp traz occurred_at de anos atrás.
    recorded_ts: Mapped[float] = mapped_column(Float)


class Rating(Base):
    """Latest rating per profile and restaurant, the same rule as the Java review_matrix."""

    __tablename__ = "ratings"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    stars: Mapped[int] = mapped_column(Integer)
    occurred_ts: Mapped[float] = mapped_column(Float)
    event_id: Mapped[str] = mapped_column(String)


class Recommendation(Base):
    """Latest list per profile, the same thing the compacted user-recommendations topic keeps."""

    __tablename__ = "recommendations"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String)
    generated_at: Mapped[str] = mapped_column(String)
    items: Mapped[str] = mapped_column(String)  # JSON: IDs na ordem do ranking


class RetrainRequest(Base):
    """Training requests seen on recommender-retrain: the complex event and the manual shortcuts."""

    __tablename__ = "retrain_requests"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    requested_at: Mapped[str] = mapped_column(String)
    requested_ts: Mapped[float] = mapped_column(Float, index=True)
    source: Mapped[str | None] = mapped_column(String)
    force: Mapped[bool] = mapped_column(Boolean, default=False)
    observed_counts: Mapped[str | None] = mapped_column(String)  # JSON


class ModelVersion(Base):
    """Every model announced on recommender-ready, in the order they went into use."""

    __tablename__ = "model_versions"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    metric_name: Mapped[str] = mapped_column(String)
    metric_value: Mapped[float] = mapped_column(Float)
    trained_until_counts: Mapped[str] = mapped_column(String)  # JSON
    created_at: Mapped[str] = mapped_column(String)
    created_ts: Mapped[float] = mapped_column(Float, index=True)


def create_db_engine(url: str) -> Engine:
    sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if sqlite else {})
    if sqlite:
        @event.listens_for(engine, "connect")
        def _pragmas(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    Base.metadata.create_all(engine)
    return engine
