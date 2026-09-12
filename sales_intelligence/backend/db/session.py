from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_from_url(database_url: str) -> Engine:
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return create_engine(database_url, pool_pre_ping=True, future=True)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_engine_from_url(database_url),
        autoflush=False,
        expire_on_commit=False,
    )
