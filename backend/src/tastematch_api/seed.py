"""Load the Yelp sample into the read model: restaurants from catalog.json, profiles from manifest.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tastematch_api.contracts import utc_now
from tastematch_api.store import Restaurant, User


LOG = logging.getLogger(__name__)


def seed_catalog(engine: Engine, sample_dir: Path) -> int:
    path = sample_dir / "catalog.json"
    if not path.exists():
        LOG.warning("Catálogo não encontrado em %s; o app fica sem restaurantes", path)
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    with Session(engine) as session, session.begin():
        for row in rows:
            session.merge(Restaurant(
                id=row["id"], name=row["name"], address=row.get("address"), city=row.get("city"),
                state=row.get("state"), postal_code=row.get("postal_code"), latitude=row.get("latitude"),
                longitude=row.get("longitude"), stars=row.get("stars"), review_count=row.get("review_count") or 0,
                categories="|" + "|".join(row.get("categories", [])) + "|",
            ))
    return len(rows)


def seed_profiles(engine: Engine, sample_dir: Path) -> int:
    """The Yelp dataset files used here carry no user names, so profiles get numbered labels."""
    path = sample_dir / "manifest.json"
    if not path.exists():
        LOG.warning("Manifesto não encontrado em %s; só haverá perfis criados no app", path)
        return 0
    user_ids = sorted(json.loads(path.read_text(encoding="utf-8"))["users"])
    with Session(engine) as session, session.begin():
        existing = set(session.scalars(select(User.id).where(User.origin == "yelp")))
        for index, user_id in enumerate(user_ids, start=1):
            if user_id not in existing:
                session.add(User(id=user_id, display_name=f"Perfil Yelp {index:03d}", origin="yelp",
                                 created_at=utc_now()))
    return len(user_ids)
