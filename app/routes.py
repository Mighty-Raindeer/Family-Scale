"""HTTP routes for logging measurements, progress, and people."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.metabolism import estimate_from_pair
from app.models import (
    ACTIVITY_TYPES,
    DEFAULT_EXERCISES,
    MEAL_SIZES,
    MEAL_SLOTS,
    PERSON_COLORS,
    Activity,
    Checkin,
    Meal,
    Measurement,
    Person,
    Set,
    Workout,
)
from app.stats import (
    average_sleep,
    delta_kg,
    last_sets_by_exercise,
    meal_size_counts,
    rolling_weight_average,
    trailing_average,
    weekly_miles,
    with_waist,
    with_weight,
)
from app.units import (
    distance_unit_label,
    duration_input_value,
    format_distance,
    format_duration,
    format_pace,
    format_waist,
    format_weight,
    from_cm,
    from_kg,
    from_meters,
    height_to_cm,
    parse_duration,
    to_cm,
    to_kg,
    to_meters,
    unit_label,
    waist_unit_label,
)

bp = Blueprint("main", __name__)


def _tz() -> ZoneInfo:
    return ZoneInfo(current_app.config.get("TIMEZONE", "America/New_York"))


def _people():
    session = get_session()
    return list(session.scalars(select(Person).order_by(Person.name)))


def _parse_float(name: str) -> float | None:
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_int(name: str) -> int | None:
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_recorded_at() -> datetime:
    raw = (request.form.get("recorded_at") or "").strip()
    if not raw:
        return datetime.now(timezone.utc)
    try:
        local = datetime.fromisoformat(raw)
    except ValueError:
        return datetime.now(timezone.utc)
    if local.tzinfo is None:
        local = local.replace(tzinfo=_tz())
    return local.astimezone(timezone.utc)


def _local_input_value(value: datetime | None = None) -> str:
    when = value or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(_tz()).strftime("%Y-%m-%dT%H:%M")


def _interval_from_form() -> tuple[bool, bool, bool, bool]:
    """Returns interval_known, had_food, had_water, used_bathroom."""
    choice = (request.form.get("interval") or "").strip()
    if choice == "fasting":
        return True, False, False, False
    if choice == "some":
        return True, bool(request.form.get("had_food")), bool(request.form.get("had_water")), bool(
            request.form.get("used_bathroom")
        )
    return False, False, False, False


def _measurement_from_form(person: Person) -> tuple[Measurement | None, str | None]:
    weight_value = _parse_float("weight")
    waist_value = _parse_float("waist")
    notes = (request.form.get("notes") or "").strip() or None
    if weight_value is not None and (weight_value <= 0 or weight_value > 800):
        return None, "Enter a realistic weight, or leave it blank."
    if waist_value is not None and (waist_value <= 0 or waist_value > 200):
        return None, "Enter a realistic waist, or leave it blank."
    if weight_value is None and waist_value is None and notes is None:
        return None, "Add a weight, a waist, or a note — anything else can stay blank."

    interval_known, had_food, had_water, used_bathroom = _interval_from_form()
    if choice := (request.form.get("interval") or "").strip():
        if choice == "some" and not (had_food or had_water or used_bathroom):
            interval_known = False

    return (
        Measurement(
            person_id=person.id,
            weight_kg=to_kg(weight_value, person.unit) if weight_value is not None else None,
            waist_cm=to_cm(waist_value, person.unit) if waist_value is not None else None,
            recorded_at=_parse_recorded_at(),
            had_food=had_food,
            had_water=had_water,
            used_bathroom=used_bathroom,
            interval_known=interval_known,
            notes=notes,
        ),
        None,
    )


def _apply_form_to_measurement(measurement: Measurement, person: Person) -> str | None:
    draft, error = _measurement_from_form(person)
    if error or draft is None:
        return error
    measurement.weight_kg = draft.weight_kg
    measurement.waist_cm = draft.waist_cm
    measurement.recorded_at = draft.recorded_at
    measurement.had_food = draft.had_food
    measurement.had_water = draft.had_water
    measurement.used_bathroom = draft.used_bathroom
    measurement.interval_known = draft.interval_known
    measurement.notes = draft.notes
    return None


def _latest_weight(person: Person) -> Measurement | None:
    session = get_session()
    return session.scalars(
        select(Measurement)
        .where(Measurement.person_id == person.id, Measurement.weight_kg.is_not(None))
        .order_by(Measurement.recorded_at.desc())
        .limit(1)
    ).first()


def _latest_waist(person: Person) -> Measurement | None:
    session = get_session()
    return session.scalars(
        select(Measurement)
        .where(Measurement.person_id == person.id, Measurement.waist_cm.is_not(None))
        .order_by(Measurement.recorded_at.desc())
        .limit(1)
    ).first()


def _previous_weight_before(measurement: Measurement) -> Measurement | None:
    session = get_session()
    return session.scalars(
        select(Measurement)
        .where(
            Measurement.person_id == measurement.person_id,
            Measurement.recorded_at < measurement.recorded_at,
            Measurement.weight_kg.is_not(None),
        )
        .order_by(Measurement.recorded_at.desc())
        .limit(1)
    ).first()


def _metabolism_for(measurement: Measurement, person: Person):
    if measurement.weight_kg is None or not measurement.is_fasting_interval:
        return None
    previous = _previous_weight_before(measurement)
    if previous is None:
        return None
    return estimate_from_pair(previous, measurement, person)


def _day_start_utc() -> datetime:
    return datetime.now(_tz()).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _today_entries(person: Person) -> list[Measurement]:
    session = get_session()
    return list(
        session.scalars(
            select(Measurement)
            .where(Measurement.person_id == person.id, Measurement.recorded_at >= _day_start_utc())
            .order_by(Measurement.recorded_at.desc())
        )
    )


def _today_activities(person: Person) -> list[Activity]:
    session = get_session()
    return list(
        session.scalars(
            select(Activity)
            .where(Activity.person_id == person.id, Activity.started_at >= _day_start_utc())
            .order_by(Activity.started_at.desc())
        )
    )


def _today_workouts(person: Person) -> list[Workout]:
    session = get_session()
    return list(
        session.scalars(
            select(Workout)
            .options(selectinload(Workout.sets))
            .where(Workout.person_id == person.id, Workout.started_at >= _day_start_utc())
            .order_by(Workout.started_at.desc())
        )
    )


def _kind() -> str:
    kind = (request.args.get("kind") or request.form.get("kind") or "body").strip()
    if kind not in {"body", "move", "lift", "day", "eat"}:
        return "body"
    return kind


def _local_date(when: datetime | None = None):
    moment = when or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_tz()).date()


def _scale(name: str) -> int | None:
    value = _parse_int(name)
    if value is None:
        return None
    if 1 <= value <= 5:
        return value
    return None


def _merge_optional(current, incoming):
    return incoming if incoming is not None else current


def _today_checkin(person: Person) -> Checkin | None:
    session = get_session()
    return session.scalars(
        select(Checkin).where(Checkin.person_id == person.id, Checkin.on_date == _local_date())
    ).first()


def _today_meals(person: Person) -> list[Meal]:
    session = get_session()
    return list(
        session.scalars(
            select(Meal)
            .where(Meal.person_id == person.id, Meal.eaten_at >= _day_start_utc())
            .order_by(Meal.eaten_at.desc())
        )
    )


def _checkin_from_form(person: Person, existing: Checkin | None) -> tuple[Checkin | None, str | None]:
    sleep_h = _parse_float("sleep_h")
    if sleep_h is not None and (sleep_h < 0 or sleep_h > 24):
        return None, "Enter a realistic sleep time, or leave it blank."
    steps = _parse_int("steps")
    if steps is not None and (steps < 0 or steps > 200000):
        return None, "Enter a realistic step count, or leave it blank."
    notes = (request.form.get("notes") or "").strip() or None
    quality = _scale("sleep_quality")
    energy = _scale("energy")
    soreness = _scale("soreness")
    mood = _scale("mood")
    if existing is None and all(v is None for v in (sleep_h, steps, notes, quality, energy, soreness, mood)):
        return None, "Add sleep, how you feel, steps, or a note — anything else can stay blank."

    row = existing or Checkin(person_id=person.id, on_date=_local_date())
    row.recorded_at = _parse_recorded_at()
    row.sleep_h = _merge_optional(row.sleep_h, sleep_h)
    row.sleep_quality = _merge_optional(row.sleep_quality, quality)
    row.energy = _merge_optional(row.energy, energy)
    row.soreness = _merge_optional(row.soreness, soreness)
    row.mood = _merge_optional(row.mood, mood)
    row.steps = _merge_optional(row.steps, steps)
    row.notes = _merge_optional(row.notes, notes)
    return row, None


def _meal_from_form(person: Person) -> tuple[Meal | None, str | None]:
    slot = (request.form.get("slot") or "").strip()
    if slot not in MEAL_SLOTS:
        slot = ""
    size = (request.form.get("size") or "").strip() or None
    if size not in MEAL_SIZES:
        size = None
    notes = (request.form.get("notes") or "").strip() or None
    if not slot and notes is None and size is None:
        return None, "Pick a meal, a size, or a note — anything else can stay blank."
    if not slot:
        slot = "snack"
    eaten_at = _parse_recorded_at()
    session = get_session()
    if slot != "snack":
        existing = session.scalars(
            select(Meal).where(
                Meal.person_id == person.id,
                Meal.slot == slot,
                Meal.eaten_at >= _day_start_utc(),
            )
        ).first()
        if existing:
            existing.eaten_at = eaten_at
            existing.size = _merge_optional(existing.size, size)
            existing.notes = _merge_optional(existing.notes, notes)
            return existing, None
    return (
        Meal(person_id=person.id, eaten_at=eaten_at, slot=slot, size=size, notes=notes),
        None,
    )


def _checkin_summary(row: Checkin) -> str:
    bits = []
    if row.sleep_h is not None:
        bits.append(f"{row.sleep_h:g} h sleep")
    if row.energy is not None:
        bits.append(f"energy {row.energy}")
    if row.soreness is not None:
        bits.append(f"sore {row.soreness}")
    if row.steps is not None:
        bits.append(f"{row.steps} steps")
    if not bits and row.notes:
        bits.append("note")
    return f"Saved today's check-in{': ' + ', '.join(bits) if bits else ''}."


def _meal_summary(row: Meal) -> str:
    label = row.slot
    if row.size:
        label = f"{row.size} {row.slot}"
    return f"Saved {label}."


def _checkin_range(person: Person, range_key: str) -> list[Checkin]:
    days = {"7": 7, "30": 30, "90": 90}.get(range_key)
    stmt = select(Checkin).where(Checkin.person_id == person.id).order_by(Checkin.on_date.desc())
    if days:
        since = _local_date() - timedelta(days=days)
        stmt = stmt.where(Checkin.on_date >= since)
    return list(get_session().scalars(stmt))


def _meal_range(person: Person, range_key: str) -> list[Meal]:
    days = {"7": 7, "30": 30, "90": 90}.get(range_key)
    stmt = select(Meal).where(Meal.person_id == person.id).order_by(Meal.eaten_at.desc())
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(Meal.eaten_at >= since)
    return list(get_session().scalars(stmt))


def _activity_from_form(person: Person) -> tuple[Activity | None, str | None]:
    kind = (request.form.get("activity_type") or "run").strip()
    if kind not in ACTIVITY_TYPES:
        kind = "run"
    distance = _parse_float("distance")
    duration = parse_duration(request.form.get("duration"))
    rpe = _parse_int("rpe")
    notes = (request.form.get("notes") or "").strip() or None
    if distance is not None and (distance <= 0 or distance > 200):
        return None, "Enter a realistic distance, or leave it blank."
    if rpe is not None and (rpe < 1 or rpe > 10):
        rpe = None
    if distance is None and duration is None and notes is None:
        return None, "Add a distance, a time, or a note — anything else can stay blank."
    return (
        Activity(
            person_id=person.id,
            kind=kind,
            started_at=_parse_recorded_at(),
            duration_s=duration,
            distance_m=to_meters(distance, person.unit) if distance is not None else None,
            rpe=rpe,
            notes=notes,
        ),
        None,
    )


def _apply_form_to_activity(activity: Activity, person: Person) -> str | None:
    draft, error = _activity_from_form(person)
    if error or draft is None:
        return error
    activity.kind = draft.kind
    activity.started_at = draft.started_at
    activity.duration_s = draft.duration_s
    activity.distance_m = draft.distance_m
    activity.rpe = draft.rpe
    activity.notes = draft.notes
    return None


def _sets_from_form(person: Person) -> list[Set]:
    names = request.form.getlist("set_name")
    reps = request.form.getlist("set_reps")
    weights = request.form.getlist("set_weight")
    sets: list[Set] = []
    position = 0
    for name, rep_raw, weight_raw in zip(names, reps, weights):
        name = name.strip() or None
        try:
            rep_value = int(rep_raw) if rep_raw.strip() else None
        except ValueError:
            rep_value = None
        try:
            weight_value = float(weight_raw) if weight_raw.strip() else None
        except ValueError:
            weight_value = None
        if name is None and rep_value is None and weight_value is None:
            continue
        if weight_value is not None and (weight_value <= 0 or weight_value > 800):
            weight_value = None
        if rep_value is not None and (rep_value <= 0 or rep_value > 200):
            rep_value = None
        sets.append(
            Set(
                position=position,
                name=name,
                reps=rep_value,
                weight_kg=to_kg(weight_value, person.unit) if weight_value is not None else None,
            )
        )
        position += 1
    return sets


def _workout_from_form(person: Person) -> tuple[Workout | None, str | None]:
    title = (request.form.get("title") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None
    sets = _sets_from_form(person)
    if title is None and notes is None and not sets:
        return None, "Add a set, a title, or a note — anything else can stay blank."
    workout = Workout(
        person_id=person.id,
        started_at=_parse_recorded_at(),
        title=title,
        notes=notes,
        sets=sets,
    )
    return workout, None


def _activity_summary(activity: Activity, person: Person) -> str:
    bits = [activity.kind]
    if activity.distance_m is not None:
        bits.append(format_distance(activity.distance_m, person.unit))
    if activity.duration_s is not None:
        bits.append(format_duration(activity.duration_s))
    return f"Saved {' '.join(bits)} for {person.name}."


def _workout_summary(workout: Workout, person: Person) -> str:
    count = len(workout.sets)
    if count:
        return f"Saved {count} set{'s' if count != 1 else ''} for {person.name}."
    return f"Saved a lift for {person.name}."


def _activity_range(person: Person, range_key: str) -> list[Activity]:
    days = {"7": 7, "30": 30, "90": 90}.get(range_key)
    stmt = (
        select(Activity)
        .where(Activity.person_id == person.id)
        .order_by(Activity.started_at.asc())
    )
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(Activity.started_at >= since)
    return list(get_session().scalars(stmt))


def _workout_range(person: Person, range_key: str) -> list[Workout]:
    days = {"7": 7, "30": 30, "90": 90}.get(range_key)
    stmt = (
        select(Workout)
        .options(selectinload(Workout.sets))
        .where(Workout.person_id == person.id)
        .order_by(Workout.started_at.desc())
    )
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(Workout.started_at >= since)
    return list(get_session().scalars(stmt))


def _saved_summary(measurement: Measurement, person: Person) -> str:
    bits = []
    if measurement.has_weight:
        bits.append(format_weight(measurement.weight_kg, person.unit))
    if measurement.has_waist:
        bits.append(format_waist(measurement.waist_cm, person.unit) + " waist")
    if measurement.notes and not bits:
        bits.append("note")
    label = " and ".join(bits) if bits else "entry"
    return f"Saved {label} for {person.name}."


def _create_person_from_form() -> Person | None:
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Name is required.", "error")
        return None
    unit = request.form.get("unit") or "lb"
    if unit not in {"lb", "kg"}:
        unit = "lb"
    sex = request.form.get("sex") or "unspecified"
    if sex not in {"female", "male", "unspecified"}:
        sex = "unspecified"
    color = request.form.get("color") or PERSON_COLORS[0]
    if color not in PERSON_COLORS:
        color = PERSON_COLORS[0]
    height_value = _parse_float("height")
    goal_value = _parse_float("goal_weight")
    session = get_session()
    person = Person(
        name=name,
        unit=unit,
        height_cm=height_to_cm(height_value, unit) if height_value else None,
        birth_year=_parse_int("birth_year"),
        sex=sex,
        color=color,
        goal_weight_kg=to_kg(goal_value, unit) if goal_value else None,
    )
    session.add(person)
    session.commit()
    return person


def _person_range_query(person: Person, range_key: str):
    days = {"7": 7, "30": 30, "90": 90}.get(range_key)
    stmt = (
        select(Measurement)
        .where(Measurement.person_id == person.id)
        .order_by(Measurement.recorded_at.asc())
    )
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(Measurement.recorded_at >= since)
    return list(get_session().scalars(stmt)), days


@bp.get("/healthz")
def healthz():
    return {"ok": True}


@bp.route("/", methods=["GET", "POST"])
def log_weight():
    session = get_session()
    people = _people()

    if request.method == "POST":
        action = request.form.get("action") or "log"
        if action == "add_person":
            person = _create_person_from_form()
            if person:
                flash(f"Added {person.name}.", "ok")
                return redirect(url_for("main.log_weight", person=person.id, kind=_kind()))
            return redirect(url_for("main.log_weight"))

        person_id = _parse_int("person_id")
        if person_id is None:
            flash("Select a person.", "error")
            return redirect(url_for("main.log_weight", kind=_kind()))
        person = session.get(Person, person_id)
        if person is None:
            flash("That person was not found.", "error")
            return redirect(url_for("main.log_weight", kind=_kind()))

        if action == "log_move":
            activity, error = _activity_from_form(person)
            if error or activity is None:
                flash(error or "Could not save.", "error")
                return redirect(url_for("main.log_weight", person=person.id, kind="move"))
            session.add(activity)
            session.commit()
            flash(_activity_summary(activity, person), "ok")
            return redirect(url_for("main.log_weight", person=person.id, kind="move"))

        if action == "log_lift":
            workout, error = _workout_from_form(person)
            if error or workout is None:
                flash(error or "Could not save.", "error")
                return redirect(url_for("main.log_weight", person=person.id, kind="lift"))
            session.add(workout)
            session.commit()
            flash(_workout_summary(workout, person), "ok")
            return redirect(url_for("main.log_weight", person=person.id, kind="lift"))

        if action == "log_day":
            row, error = _checkin_from_form(person, _today_checkin(person))
            if error or row is None:
                flash(error or "Could not save.", "error")
                return redirect(url_for("main.log_weight", person=person.id, kind="day"))
            session.add(row)
            session.commit()
            flash(_checkin_summary(row), "ok")
            return redirect(url_for("main.log_weight", person=person.id, kind="day"))

        if action == "log_eat":
            meal, error = _meal_from_form(person)
            if error or meal is None:
                flash(error or "Could not save.", "error")
                return redirect(url_for("main.log_weight", person=person.id, kind="eat"))
            session.add(meal)
            session.commit()
            flash(_meal_summary(meal), "ok")
            return redirect(url_for("main.log_weight", person=person.id, kind="eat"))

        measurement, error = _measurement_from_form(person)
        if error or measurement is None:
            flash(error or "Could not save.", "error")
            return redirect(url_for("main.log_weight", person=person.id, kind="body"))

        session.add(measurement)
        session.commit()
        flash(_saved_summary(measurement, person), "ok")
        estimate = _metabolism_for(measurement, person)
        return redirect(
            url_for(
                "main.log_weight",
                person=person.id,
                kind="body",
                logged=measurement.id if estimate else None,
            )
        )

    selected_id = request.args.get("person", type=int)
    if selected_id is None and people:
        selected_id = people[0].id
    selected = next((p for p in people if p.id == selected_id), people[0] if people else None)
    latest_weight = _latest_weight(selected) if selected else None
    latest_waist = _latest_waist(selected) if selected else None
    today = _today_entries(selected) if selected else []
    today_activities = _today_activities(selected) if selected else []
    today_workouts = _today_workouts(selected) if selected else []
    today_checkin = _today_checkin(selected) if selected else None
    today_meals = _today_meals(selected) if selected else []
    logged_id = request.args.get("logged", type=int)
    estimate = None
    logged = None
    if logged_id and selected:
        logged = session.get(Measurement, logged_id)
        if logged and logged.person_id == selected.id:
            estimate = _metabolism_for(logged, selected)

    return render_template(
        "log.html",
        people=people,
        selected=selected,
        kind=_kind(),
        latest_weight=latest_weight,
        latest_waist=latest_waist,
        today=today,
        today_activities=today_activities,
        today_workouts=today_workouts,
        today_checkin=today_checkin,
        today_meals=today_meals,
        estimate=estimate,
        logged=logged,
        colors=PERSON_COLORS,
        recorded_at_value=_local_input_value(),
        activity_types=ACTIVITY_TYPES,
        exercises=DEFAULT_EXERCISES,
        empty_sets=3,
        meal_slots=MEAL_SLOTS,
        meal_sizes=MEAL_SIZES,
    )


@bp.route("/progress")
def progress():
    people = _people()
    selected_id = request.args.get("person", type=int)
    if selected_id is None and people:
        selected_id = people[0].id
    selected = next((p for p in people if p.id == selected_id), people[0] if people else None)
    range_key = request.args.get("range", "90")
    measurements: list[Measurement] = []
    estimates = []
    if selected:
        measurements, _days = _person_range_query(selected, range_key)
        for current in measurements:
            if not current.is_fasting_interval or current.weight_kg is None:
                continue
            previous = _previous_weight_before(current)
            if previous is None:
                continue
            estimate = estimate_from_pair(previous, current, selected)
            if estimate and estimate.reliable:
                estimates.append((current, previous, estimate))
        estimates.reverse()

    weights = with_weight(measurements)
    waists = with_waist(measurements)
    latest_weight = weights[-1] if weights else None
    latest_waist = waists[-1] if waists else None
    first_weight = weights[0] if weights else None
    delta = delta_kg(measurements)
    avg7 = trailing_average(measurements, datetime.now(timezone.utc), days=7) if selected else None
    vs_goal = None
    if selected and selected.goal_weight_kg and latest_weight and latest_weight.weight_kg is not None:
        vs_goal = latest_weight.weight_kg - selected.goal_weight_kg

    activities = _activity_range(selected, range_key) if selected else []
    workouts = _workout_range(selected, range_key) if selected else []
    weeks = weekly_miles(activities, _tz(), selected.unit) if selected else []
    week_total = sum(row["distance"] for row in weeks[-1:]) if weeks else 0
    recent_week_distance = weeks[-1]["distance"] if weeks else None
    last_lifts = last_sets_by_exercise(workouts)
    checkins = _checkin_range(selected, range_key) if selected else []
    meals = _meal_range(selected, range_key) if selected else []
    sleep_avg = average_sleep(checkins) if checkins else None
    meal_counts = meal_size_counts(meals)

    return render_template(
        "progress.html",
        people=people,
        selected=selected,
        measurements=list(reversed(measurements)),
        estimates=estimates,
        range_key=range_key if range_key in {"7", "30", "90"} else "all",
        latest_weight=latest_weight,
        latest_waist=latest_waist,
        first_weight=first_weight,
        delta=delta,
        avg7=avg7,
        vs_goal=vs_goal,
        weight_count=len(weights),
        waist_count=len(waists),
        activities=list(reversed(activities)),
        workouts=workouts,
        weeks=weeks,
        recent_week_distance=recent_week_distance,
        last_lifts=last_lifts,
        activity_count=len(activities),
        workout_count=len(workouts),
        week_total=week_total,
        checkins=checkins,
        meals=meals,
        sleep_avg=sleep_avg,
        meal_counts=meal_counts,
    )


@bp.get("/api/progress/<int:person_id>")
def progress_api(person_id: int):
    session = get_session()
    person = session.get(Person, person_id)
    if person is None:
        return jsonify({"error": "not found"}), 404
    range_key = request.args.get("range", "90")
    rows, _days = _person_range_query(person, range_key)
    weight_points = [(row.recorded_at, row.weight_kg) for row in rows if row.weight_kg is not None]
    averages = rolling_weight_average(weight_points) if weight_points else []
    avg_by_time = {when.isoformat(): avg for (when, _w), avg in zip(weight_points, averages)}
    return jsonify(
        {
            "unit": person.unit,
            "unit_label": unit_label(person.unit),
            "waist_unit": waist_unit_label(person.unit),
            "color": person.color,
            "name": person.name,
            "points": [
                {
                    "id": row.id,
                    "at": row.recorded_at.isoformat(),
                    "weight": round(from_kg(row.weight_kg, person.unit), 2) if row.weight_kg is not None else None,
                    "waist": round(from_cm(row.waist_cm, person.unit), 2) if row.waist_cm is not None else None,
                    "average": (
                        round(from_kg(avg_by_time.get(row.recorded_at.isoformat()), person.unit), 2)
                        if row.recorded_at.isoformat() in avg_by_time
                        and avg_by_time[row.recorded_at.isoformat()] is not None
                        else None
                    ),
                    "fasting": row.is_fasting_interval,
                }
                for row in rows
            ],
        }
    )


@bp.get("/api/progress/<int:person_id>/miles")
def miles_api(person_id: int):
    session = get_session()
    person = session.get(Person, person_id)
    if person is None:
        return jsonify({"error": "not found"}), 404
    range_key = request.args.get("range", "90")
    activities = _activity_range(person, range_key)
    weeks = weekly_miles(activities, _tz(), person.unit)
    return jsonify(
        {
            "unit": distance_unit_label(person.unit),
            "color": person.color,
            "name": person.name,
            "weeks": [
                {
                    "week": row["week"].date().isoformat(),
                    "distance": round(row["distance"], 2),
                    "count": row["count"],
                }
                for row in weeks
            ],
        }
    )


@bp.get("/progress/export.csv")
def export_csv():
    people = _people()
    selected_id = request.args.get("person", type=int)
    selected = next((p for p in people if p.id == selected_id), people[0] if people else None)
    if selected is None:
        flash("Add a person first.", "error")
        return redirect(url_for("main.progress"))
    range_key = request.args.get("range", "all")
    rows, _days = _person_range_query(selected, range_key)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "when",
            f"weight_{selected.unit}",
            f"waist_{waist_unit_label(selected.unit)}",
            "interval",
            "food",
            "drink",
            "bathroom",
            "notes",
        ]
    )
    for row in rows:
        if row.is_fasting_interval:
            interval = "fasting"
        elif row.interval_known:
            interval = "noted"
        else:
            interval = ""
        writer.writerow(
            [
                row.recorded_at.astimezone(_tz()).isoformat(timespec="minutes"),
                f"{from_kg(row.weight_kg, selected.unit):.2f}" if row.weight_kg is not None else "",
                f"{from_cm(row.waist_cm, selected.unit):.2f}" if row.waist_cm is not None else "",
                interval,
                "yes" if row.interval_known and row.had_food else "",
                "yes" if row.interval_known and row.had_water else "",
                "yes" if row.interval_known and row.used_bathroom else "",
                row.notes or "",
            ]
        )
    filename = f"family-scale-{selected.name.lower().replace(' ', '-')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/measurements/<int:measurement_id>/edit", methods=["GET", "POST"])
def edit_measurement(measurement_id: int):
    session = get_session()
    measurement = session.get(Measurement, measurement_id)
    if measurement is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person = session.get(Person, measurement.person_id)
    if person is None:
        flash("That person was not found.", "error")
        return redirect(url_for("main.progress"))

    if request.method == "POST":
        error = _apply_form_to_measurement(measurement, person)
        if error:
            flash(error, "error")
            return redirect(url_for("main.edit_measurement", measurement_id=measurement.id))
        session.commit()
        flash("Updated.", "ok")
        return redirect(url_for("main.progress", person=person.id))

    interval = ""
    if measurement.is_fasting_interval:
        interval = "fasting"
    elif measurement.interval_known:
        interval = "some"

    return render_template(
        "edit.html",
        person=person,
        selected=person,
        measurement=measurement,
        interval=interval,
        recorded_at_value=_local_input_value(measurement.recorded_at),
        weight_value=(
            f"{from_kg(measurement.weight_kg, person.unit):.1f}" if measurement.weight_kg is not None else ""
        ),
        waist_value=(
            f"{from_cm(measurement.waist_cm, person.unit):.1f}" if measurement.waist_cm is not None else ""
        ),
    )


@bp.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
def edit_activity(activity_id: int):
    session = get_session()
    activity = session.get(Activity, activity_id)
    if activity is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person = session.get(Person, activity.person_id)
    if person is None:
        flash("That person was not found.", "error")
        return redirect(url_for("main.progress"))
    if request.method == "POST":
        error = _apply_form_to_activity(activity, person)
        if error:
            flash(error, "error")
            return redirect(url_for("main.edit_activity", activity_id=activity.id))
        session.commit()
        flash("Updated.", "ok")
        return redirect(url_for("main.progress", person=person.id))
    return render_template(
        "edit_activity.html",
        person=person,
        selected=person,
        activity=activity,
        activity_types=ACTIVITY_TYPES,
        recorded_at_value=_local_input_value(activity.started_at),
        distance_value=(
            f"{from_meters(activity.distance_m, person.unit):.2f}" if activity.distance_m is not None else ""
        ),
        duration_value=duration_input_value(activity.duration_s),
    )


@bp.post("/activities/<int:activity_id>/delete")
def delete_activity(activity_id: int):
    session = get_session()
    activity = session.get(Activity, activity_id)
    if activity is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person_id = activity.person_id
    session.delete(activity)
    session.commit()
    flash("Entry removed.", "ok")
    return redirect(url_for("main.progress", person=person_id, range=request.args.get("range", "90")))


@bp.route("/workouts/<int:workout_id>/edit", methods=["GET", "POST"])
def edit_workout(workout_id: int):
    session = get_session()
    workout = session.get(Workout, workout_id)
    if workout is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person = session.get(Person, workout.person_id)
    if person is None:
        flash("That person was not found.", "error")
        return redirect(url_for("main.progress"))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None
        sets = _sets_from_form(person)
        if title is None and notes is None and not sets:
            flash("Add a set, a title, or a note — anything else can stay blank.", "error")
            return redirect(url_for("main.edit_workout", workout_id=workout.id))
        workout.started_at = _parse_recorded_at()
        workout.title = title
        workout.notes = notes
        workout.sets.clear()
        session.flush()
        for item in sets:
            workout.sets.append(item)
        session.commit()
        flash("Updated.", "ok")
        return redirect(url_for("main.progress", person=person.id))
    return render_template(
        "edit_workout.html",
        person=person,
        selected=person,
        workout=workout,
        exercises=DEFAULT_EXERCISES,
        recorded_at_value=_local_input_value(workout.started_at),
    )


@bp.post("/workouts/<int:workout_id>/delete")
def delete_workout(workout_id: int):
    session = get_session()
    workout = session.get(Workout, workout_id)
    if workout is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person_id = workout.person_id
    session.delete(workout)
    session.commit()
    flash("Entry removed.", "ok")
    return redirect(url_for("main.progress", person=person_id, range=request.args.get("range", "90")))


@bp.route("/checkins/<int:checkin_id>/edit", methods=["GET", "POST"])
def edit_checkin(checkin_id: int):
    session = get_session()
    row = session.get(Checkin, checkin_id)
    if row is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person = session.get(Person, row.person_id)
    if person is None:
        flash("That person was not found.", "error")
        return redirect(url_for("main.progress"))
    if request.method == "POST":
        updated, error = _checkin_from_form(person, row)
        if error or updated is None:
            flash(error or "Could not save.", "error")
            return redirect(url_for("main.edit_checkin", checkin_id=row.id))
        session.commit()
        flash("Updated.", "ok")
        return redirect(url_for("main.progress", person=person.id))
    return render_template(
        "edit_checkin.html",
        person=person,
        selected=person,
        checkin=row,
        extras_open=True,
        recorded_at_value=_local_input_value(row.recorded_at),
    )


@bp.post("/checkins/<int:checkin_id>/delete")
def delete_checkin(checkin_id: int):
    session = get_session()
    row = session.get(Checkin, checkin_id)
    if row is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person_id = row.person_id
    session.delete(row)
    session.commit()
    flash("Entry removed.", "ok")
    return redirect(url_for("main.progress", person=person_id, range=request.args.get("range", "90")))


@bp.route("/meals/<int:meal_id>/edit", methods=["GET", "POST"])
def edit_meal(meal_id: int):
    session = get_session()
    meal = session.get(Meal, meal_id)
    if meal is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person = session.get(Person, meal.person_id)
    if person is None:
        flash("That person was not found.", "error")
        return redirect(url_for("main.progress"))
    if request.method == "POST":
        slot = (request.form.get("slot") or meal.slot).strip()
        if slot not in MEAL_SLOTS:
            slot = meal.slot
        size = (request.form.get("size") or "").strip() or None
        if size not in MEAL_SIZES:
            size = None
        notes = (request.form.get("notes") or "").strip() or None
        meal.slot = slot
        meal.size = size
        meal.notes = notes
        meal.eaten_at = _parse_recorded_at()
        session.commit()
        flash("Updated.", "ok")
        return redirect(url_for("main.progress", person=person.id))
    return render_template(
        "edit_meal.html",
        person=person,
        selected=person,
        meal=meal,
        meal_slots=MEAL_SLOTS,
        meal_sizes=MEAL_SIZES,
        extras_open=True,
        recorded_at_value=_local_input_value(meal.eaten_at),
    )


@bp.post("/meals/<int:meal_id>/delete")
def delete_meal(meal_id: int):
    session = get_session()
    meal = session.get(Meal, meal_id)
    if meal is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person_id = meal.person_id
    session.delete(meal)
    session.commit()
    flash("Entry removed.", "ok")
    return redirect(url_for("main.progress", person=person_id, range=request.args.get("range", "90")))


@bp.route("/people", methods=["GET", "POST"])
def people():
    session = get_session()
    if request.method == "POST":
        action = request.form.get("action") or "add"
        if action == "add":
            person = _create_person_from_form()
            if person:
                flash(f"Added {person.name}.", "ok")
            return redirect(url_for("main.people"))
        person_id = _parse_int("person_id")
        person = session.get(Person, person_id) if person_id else None
        if person is None:
            flash("That person was not found.", "error")
            return redirect(url_for("main.people"))
        if action == "delete":
            session.delete(person)
            session.commit()
            flash(f"Removed {person.name} and their entries.", "ok")
            return redirect(url_for("main.people"))
        if action == "save":
            name = (request.form.get("name") or "").strip()
            if not name:
                flash("Name is required.", "error")
                return redirect(url_for("main.people"))
            unit = request.form.get("unit") or person.unit
            if unit not in {"lb", "kg"}:
                unit = person.unit
            sex = request.form.get("sex") or person.sex
            if sex not in {"female", "male", "unspecified"}:
                sex = person.sex
            color = request.form.get("color") or person.color
            if color not in PERSON_COLORS:
                color = person.color
            height_value = _parse_float("height")
            goal_value = _parse_float("goal_weight")
            person.name = name
            person.unit = unit
            person.sex = sex
            person.color = color
            person.height_cm = height_to_cm(height_value, unit) if height_value else None
            person.birth_year = _parse_int("birth_year")
            person.goal_weight_kg = to_kg(goal_value, unit) if goal_value else None
            session.commit()
            flash(f"Updated {person.name}.", "ok")
            return redirect(url_for("main.people"))

    rows = list(
        session.scalars(
            select(Person).options(selectinload(Person.measurements)).order_by(Person.name)
        )
    )
    return render_template(
        "people.html",
        people=rows,
        colors=PERSON_COLORS,
    )


@bp.post("/measurements/<int:measurement_id>/delete")
def delete_measurement(measurement_id: int):
    session = get_session()
    measurement = session.get(Measurement, measurement_id)
    if measurement is None:
        flash("Entry not found.", "error")
        return redirect(url_for("main.progress"))
    person_id = measurement.person_id
    session.delete(measurement)
    session.commit()
    flash("Entry removed.", "ok")
    return redirect(url_for("main.progress", person=person_id, range=request.args.get("range", "90")))
