"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from flask import Flask, g
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal: sessionmaker[Session] | None = None


def init_db(app: Flask) -> None:
    global engine, SessionLocal

    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    connect_args = {}
    if uri.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        uri,
        echo=app.config.get("SQLALCHEMY_ECHO", False),
        connect_args=connect_args,
        future=True,
    )

    if uri.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    from app import models  # noqa: F401
    from app.migrate import migrate_schema

    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)

    @app.teardown_appcontext
    def _shutdown_session(exception=None):  # noqa: ARG001
        session = g.pop("db_session", None)
        if session is not None:
            if exception is not None:
                session.rollback()
            session.close()


def get_session() -> Session:
    if "db_session" not in g:
        if SessionLocal is None:
            raise RuntimeError("Database not initialized")
        g.db_session = SessionLocal()
    return g.db_session
