"""Health check used by the Compose healthcheck: Kafka reachable, catalog loaded and projector alive."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select

from tastematch_api.deps import Db, Pub
from tastematch_api.store import Restaurant, User


router = APIRouter(tags=["saúde"])


@router.get("/api/health")
def health(request: Request, response: Response, db: Db, publisher: Pub) -> dict:
    kafka = publisher.ping()
    projector = request.app.state.projector
    restaurants = db.scalar(select(func.count()).select_from(Restaurant)) or 0
    profiles = db.scalar(select(func.count()).select_from(User)) or 0
    healthy = kafka and restaurants > 0 and projector.running
    response.status_code = 200 if healthy else 503
    return {"status": "ok" if healthy else "degraded", "kafka": kafka, "restaurants": restaurants,
            "profiles": profiles,
            "projector": {"running": projector.running, "events": projector.projected, "lag": projector.lag}}
