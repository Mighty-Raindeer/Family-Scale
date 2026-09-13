"""Resting-metabolism estimate from a fasting weigh-in pair.

If two weigh-ins have no food, drink, or bathroom in between, the scale
change is mostly insensible water (breath + skin) plus the carbon you
exhale while oxidizing fat. We subtract a typical indoor water-loss rate
and treat the remainder as fasted fat oxidation.

This is a household estimate, not a lab measurement. Best with an evening
weigh-in and a next-morning weigh-in on the same scale, similar clothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Measurement, Person

# Typical indoor insensible loss (skin + lungs), ~6.7 g/kg/day.
INSENSIBLE_G_PER_KG_PER_HOUR = 0.28
KCAL_PER_G_FAT = 9.0
MIN_HOURS = 4.0
MAX_HOURS = 48.0
MIN_LOSS_KG = 0.05  # ~0.1 lb — below typical bathroom-scale noise
PLAUSIBLE_KCAL = (800.0, 4500.0)


@dataclass(frozen=True)
class MetabolismEstimate:
    hours: float
    loss_g: float
    insensible_g: float
    metabolic_g: float
    kcal_interval: float
    kcal_per_day: float
    g_per_hour: float
    previous_at: datetime
    current_at: datetime
    reliable: bool
    reason: str | None = None
    mifflin_kcal: float | None = None


def _age_years(birth_year: int | None, when: datetime) -> int | None:
    if birth_year is None:
        return None
    age = when.year - birth_year
    if age < 5 or age > 120:
        return None
    return age


def mifflin_st_jeor(weight_kg: float, height_cm: float | None, birth_year: int | None, sex: str, when: datetime) -> float | None:
    if height_cm is None or height_cm < 50:
        return None
    age = _age_years(birth_year, when)
    if age is None:
        return None
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age
    if sex == "male":
        return base + 5.0
    if sex == "female":
        return base - 161.0
    return None


def estimate_from_pair(
    previous: Measurement,
    current: Measurement,
    person: Person,
) -> MetabolismEstimate | None:
    if not current.is_fasting_interval:
        return None
    if previous.weight_kg is None or current.weight_kg is None:
        return None

    prev_at = previous.recorded_at
    curr_at = current.recorded_at
    if prev_at.tzinfo is None:
        from datetime import timezone

        prev_at = prev_at.replace(tzinfo=timezone.utc)
        curr_at = curr_at.replace(tzinfo=timezone.utc)

    hours = (curr_at - prev_at).total_seconds() / 3600.0
    if hours < MIN_HOURS:
        return MetabolismEstimate(
            hours=hours,
            loss_g=0,
            insensible_g=0,
            metabolic_g=0,
            kcal_interval=0,
            kcal_per_day=0,
            g_per_hour=0,
            previous_at=prev_at,
            current_at=curr_at,
            reliable=False,
            reason=f"Need at least {MIN_HOURS:.0f} hours between fasting weigh-ins.",
        )
    if hours > MAX_HOURS:
        return MetabolismEstimate(
            hours=hours,
            loss_g=0,
            insensible_g=0,
            metabolic_g=0,
            kcal_interval=0,
            kcal_per_day=0,
            g_per_hour=0,
            previous_at=prev_at,
            current_at=curr_at,
            reliable=False,
            reason=f"Interval is over {MAX_HOURS:.0f} hours — too long to treat as a single fasting stretch.",
        )

    loss_kg = previous.weight_kg - current.weight_kg
    if loss_kg < MIN_LOSS_KG:
        if loss_kg < 0:
            reason = "Weight went up during the fasting interval (scale, clothing, or retained water)."
        else:
            reason = "Weight change is smaller than typical scale precision."
        return MetabolismEstimate(
            hours=hours,
            loss_g=loss_kg * 1000.0,
            insensible_g=0,
            metabolic_g=0,
            kcal_interval=0,
            kcal_per_day=0,
            g_per_hour=loss_kg * 1000.0 / hours,
            previous_at=prev_at,
            current_at=curr_at,
            reliable=False,
            reason=reason,
        )

    loss_g = loss_kg * 1000.0
    body_kg = previous.weight_kg
    insensible_g = INSENSIBLE_G_PER_KG_PER_HOUR * body_kg * hours
    metabolic_g = loss_g - insensible_g
    if metabolic_g <= 0:
        return MetabolismEstimate(
            hours=hours,
            loss_g=loss_g,
            insensible_g=insensible_g,
            metabolic_g=metabolic_g,
            kcal_interval=0,
            kcal_per_day=0,
            g_per_hour=loss_g / hours,
            previous_at=prev_at,
            current_at=curr_at,
            reliable=False,
            reason="Loss is fully explained by typical water vapor — not enough leftover to estimate energy.",
        )

    kcal_interval = metabolic_g * KCAL_PER_G_FAT
    kcal_per_day = kcal_interval / hours * 24.0
    formula = mifflin_st_jeor(
        current.weight_kg,
        person.height_cm,
        person.birth_year,
        person.sex,
        curr_at,
    )
    low, high = PLAUSIBLE_KCAL
    if kcal_per_day < low or kcal_per_day > high:
        return MetabolismEstimate(
            hours=hours,
            loss_g=loss_g,
            insensible_g=insensible_g,
            metabolic_g=metabolic_g,
            kcal_interval=kcal_interval,
            kcal_per_day=kcal_per_day,
            g_per_hour=loss_g / hours,
            previous_at=prev_at,
            current_at=curr_at,
            reliable=False,
            reason=(
                f"Estimate came out around {kcal_per_day:.0f} kcal/day, outside a "
                "plausible resting range. Same clothes and a 6–12 hour overnight pair work best."
            ),
            mifflin_kcal=formula,
        )
    return MetabolismEstimate(
        hours=hours,
        loss_g=loss_g,
        insensible_g=insensible_g,
        metabolic_g=metabolic_g,
        kcal_interval=kcal_interval,
        kcal_per_day=kcal_per_day,
        g_per_hour=loss_g / hours,
        previous_at=prev_at,
        current_at=curr_at,
        reliable=True,
        mifflin_kcal=formula,
    )
