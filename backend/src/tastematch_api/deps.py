"""Request dependencies: database session, Kafka publisher and the profile in the session cookie."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from tastematch_api.kafka.producer import Publisher
from tastematch_api.store import User


SESSION_COOKIE = "tm_user"


def get_db(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher


Db = Annotated[Session, Depends(get_db)]
Pub = Annotated[Publisher, Depends(get_publisher)]
IdempotencyKey = Annotated[str | None, Header(
    pattern=r"^[A-Za-z0-9_-]{8,100}$",
    description="Repita o mesmo valor ao tentar de novo: o evento mantém o event_id e não é contado duas vezes.",
)]


def current_user(request: Request, db: Db) -> User:
    user_id = request.cookies.get(SESSION_COOKIE)
    if not user_id:
        raise HTTPException(401, "Entre com um perfil em POST /api/session")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "O perfil da sessão não existe mais; entre de novo")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
