"""Bring an existing SQLite file in line with the current models."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def migrate_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "people" not in tables:
            return

        people_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(people)"))}
        if "goal_weight_kg" not in people_cols:
            conn.execute(text("ALTER TABLE people ADD COLUMN goal_weight_kg FLOAT"))

        if "measurements" not in tables:
            return

        meas_info = list(conn.execute(text("PRAGMA table_info(measurements)")))
        meas_cols = {row[1]: row for row in meas_info}

        if "waist_cm" not in meas_cols:
            conn.execute(text("ALTER TABLE measurements ADD COLUMN waist_cm FLOAT"))
        if "interval_known" not in meas_cols:
            conn.execute(text("ALTER TABLE measurements ADD COLUMN interval_known BOOLEAN NOT NULL DEFAULT 1"))

        meas_info = list(conn.execute(text("PRAGMA table_info(measurements)")))
        weight_notnull = next(row[3] for row in meas_info if row[1] == "weight_kg")
        if not weight_notnull:
            return

        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE measurements_new (
                    id INTEGER PRIMARY KEY,
                    person_id INTEGER NOT NULL,
                    weight_kg FLOAT,
                    waist_cm FLOAT,
                    recorded_at DATETIME NOT NULL,
                    had_food BOOLEAN NOT NULL,
                    had_water BOOLEAN NOT NULL,
                    used_bathroom BOOLEAN NOT NULL,
                    interval_known BOOLEAN NOT NULL DEFAULT 0,
                    notes TEXT,
                    FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO measurements_new (
                    id, person_id, weight_kg, waist_cm, recorded_at,
                    had_food, had_water, used_bathroom, interval_known, notes
                )
                SELECT
                    id, person_id, weight_kg, waist_cm, recorded_at,
                    had_food, had_water, used_bathroom,
                    COALESCE(interval_known, 1), notes
                FROM measurements
                """
            )
        )
        conn.execute(text("DROP TABLE measurements"))
        conn.execute(text("ALTER TABLE measurements_new RENAME TO measurements"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
