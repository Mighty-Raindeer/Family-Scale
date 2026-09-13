"""Family health tracker application factory."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask

from app.config import Config
from app.db import init_db


def create_app(config_object: type[Config] | None = None) -> Flask:
    cfg = config_object or Config
    cfg.ensure_directories()

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_mapping(
        SECRET_KEY=cfg.SECRET_KEY,
        SQLALCHEMY_DATABASE_URI=cfg.SQLALCHEMY_DATABASE_URI,
        SQLALCHEMY_ECHO=cfg.SQLALCHEMY_ECHO,
        DATA_DIR=str(cfg.DATA_DIR),
        DEBUG=cfg.DEBUG,
        TIMEZONE=cfg.TIMEZONE,
    )

    init_db(app)

    from app.routes import bp

    app.register_blueprint(bp)

    tz = ZoneInfo(cfg.TIMEZONE)

    @app.template_filter("localtime")
    def localtime(value: datetime, fmt: str = "%b %-d, %-I:%M %p") -> str:
        if value is None:
            return ""
        if value.tzinfo is None:
            from datetime import timezone

            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(tz).strftime(fmt)

    @app.template_filter("weight")
    def weight_filter(kg: float, unit: str) -> str:
        from app.units import format_weight

        return format_weight(kg, unit)

    @app.template_filter("weight_num")
    def weight_num_filter(kg: float | None, unit: str) -> str:
        from app.units import format_weight_short

        return format_weight_short(kg, unit)

    @app.template_filter("waist")
    def waist_filter(cm: float | None, unit: str) -> str:
        from app.units import format_waist

        return format_waist(cm, unit)

    @app.template_filter("waist_num")
    def waist_num_filter(cm: float | None, unit: str) -> str:
        from app.units import format_waist_short

        return format_waist_short(cm, unit)

    @app.template_filter("distance")
    def distance_filter(meters: float | None, unit: str) -> str:
        from app.units import format_distance

        return format_distance(meters, unit)

    @app.template_filter("duration")
    def duration_filter(seconds: int | None) -> str:
        from app.units import format_duration

        return format_duration(seconds)

    @app.template_filter("pace")
    def pace_filter(meters: float | None, seconds: int | None, unit: str) -> str:
        from app.units import format_pace

        return format_pace(meters, seconds, unit)

    @app.context_processor
    def inject_now():
        from datetime import timezone

        return {"now_local": datetime.now(timezone.utc).astimezone(tz)}

    return app
