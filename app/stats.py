"""Derived numbers from sparse measurements. Missing fields are skipped, never invented."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from app.models import Measurement


def with_weight(rows: Iterable[Measurement]) -> list[Measurement]:
    return [row for row in rows if row.weight_kg is not None]


def with_waist(rows: Iterable[Measurement]) -> list[Measurement]:
    return [row for row in rows if row.waist_cm is not None]


def average_kg(rows: Iterable[Measurement], *, since: datetime | None = None) -> float | None:
    values = []
    for row in rows:
        if row.weight_kg is None:
            continue
        if since is not None and row.recorded_at < since:
            continue
        values.append(row.weight_kg)
    if len(values) < 2:
        return None
    return sum(values) / len(values)


def trailing_average(rows: Iterable[Measurement], now: datetime, days: int = 7) -> float | None:
    return average_kg(rows, since=now - timedelta(days=days))


def delta_kg(rows: list[Measurement]) -> float | None:
    weighted = with_weight(rows)
    if len(weighted) < 2:
        return None
    return weighted[-1].weight_kg - weighted[0].weight_kg


def week_start(when: datetime, tz) -> datetime:
    local = when.astimezone(tz) if when.tzinfo else when.replace(tzinfo=tz)
    monday = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local.weekday())
    return monday


def weekly_miles(activities, tz, unit: str) -> list[dict]:
    from app.units import from_meters

    buckets: dict[datetime, dict] = {}
    for row in activities:
        if row.distance_m is None:
            continue
        key = week_start(row.started_at, tz)
        bucket = buckets.setdefault(key, {"week": key, "meters": 0.0, "count": 0})
        bucket["meters"] += row.distance_m
        bucket["count"] += 1
    rows = []
    for key in sorted(buckets):
        bucket = buckets[key]
        rows.append(
            {
                "week": key,
                "distance": from_meters(bucket["meters"], unit),
                "count": bucket["count"],
            }
        )
    return rows


def average_sleep(checkins) -> float | None:
    values = [row.sleep_h for row in checkins if row.sleep_h is not None]
    if len(values) < 2:
        return None
    return sum(values) / len(values)


def meal_size_counts(meals) -> dict[str, int]:
    counts = {"light": 0, "normal": 0, "heavy": 0}
    for row in meals:
        if row.size in counts:
            counts[row.size] += 1
    return counts


def last_sets_by_exercise(workouts) -> list[tuple[str, object, object]]:
    latest: dict[str, tuple] = {}
    for workout in workouts:
        for item in workout.sets:
            name = (item.name or "").strip()
            if not name:
                continue
            current = latest.get(name)
            if current is None or workout.started_at > current[1].started_at:
                latest[name] = (name, workout, item)
    return sorted(latest.values(), key=lambda row: row[0].lower())


def rolling_weight_average(points: list[tuple[datetime, float]], days: int = 7) -> list[float | None]:
    """For each point, mean of weights in the previous `days` days (inclusive)."""
    window = timedelta(days=days)
    out: list[float | None] = []
    for index, (when, _weight) in enumerate(points):
        start = when - window
        bucket = [w for t, w in points[: index + 1] if t >= start]
        out.append(sum(bucket) / len(bucket) if bucket else None)
    return out
