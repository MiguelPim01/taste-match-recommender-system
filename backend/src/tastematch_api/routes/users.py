"""Demo profiles and session: pick one of the Yelp sample profiles or create a new one, without a password."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from tastematch_api.contracts import utc_now
from tastematch_api.deps import SESSION_COOKIE, CurrentUser, Db
from tastematch_api.store import User


router = APIRouter(prefix="/api", tags=["perfis"])


class Profile(BaseModel):
    id: str
    display_name: str
    origin: Literal["yelp", "app"]

    @classmethod
    def of(cls, user: User) -> Profile:
        return cls(id=user.id, display_name=user.display_name, origin=user.origin)


class NewProfile(BaseModel):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class SessionStart(BaseModel):
    user_id: str


@router.get("/users")
def list_profiles(db: Db) -> list[Profile]:
    return [Profile.of(user) for user in db.scalars(select(User).order_by(User.origin, User.display_name))]


@router.post("/users", status_code=201)
def create_profile(body: NewProfile, db: Db) -> Profile:
    user = User(id=f"app-{uuid4().hex[:16]}", display_name=body.display_name, origin="app", created_at=utc_now())
    db.add(user)
    db.commit()
    return Profile.of(user)


@router.post("/session")
def start_session(body: SessionStart, response: Response, db: Db) -> Profile:
    user = db.get(User, body.user_id)
    if user is None:
        raise HTTPException(404, "Perfil não encontrado")
    response.set_cookie(SESSION_COOKIE, user.id, max_age=30 * 24 * 3600, httponly=True, samesite="lax")
    return Profile.of(user)


@router.get("/session")
def current_session(user: CurrentUser) -> Profile:
    return Profile.of(user)


@router.delete("/session", status_code=204)
def end_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)
