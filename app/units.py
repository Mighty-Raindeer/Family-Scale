"""Weight and height conversion helpers."""

from __future__ import annotations

LB_PER_KG = 2.2046226218
IN_PER_CM = 0.3937007874


def to_kg(value: float, unit: str) -> float:
    if unit == "lb":
        return value / LB_PER_KG
    return value


def from_kg(kg: float, unit: str) -> float:
    if unit == "lb":
        return kg * LB_PER_KG
    return kg


def format_weight(kg: float | None, unit: str) -> str:
    if kg is None:
        return "—"
    value = from_kg(kg, unit)
    if unit == "lb":
        return f"{value:.1f} lb"
    return f"{value:.2f} kg"


def format_weight_short(kg: float | None, unit: str) -> str:
    if kg is None:
        return "—"
    value = from_kg(kg, unit)
    if unit == "lb":
        return f"{value:.1f}"
    return f"{value:.2f}"


def to_cm(value: float, unit: str) -> float:
    if unit == "lb":
        return value / IN_PER_CM
    return value


def from_cm(cm: float, unit: str) -> float:
    if unit == "lb":
        return cm * IN_PER_CM
    return cm


def format_waist(cm: float | None, unit: str) -> str:
    if cm is None:
        return "—"
    value = from_cm(cm, unit)
    if unit == "lb":
        return f"{value:.1f} in"
    return f"{value:.1f} cm"


def format_waist_short(cm: float | None, unit: str) -> str:
    if cm is None:
        return "—"
    value = from_cm(cm, unit)
    return f"{value:.1f}"


def waist_unit_label(unit: str) -> str:
    return "in" if unit == "lb" else "cm"


def height_to_cm(value: float, unit: str) -> float:
    if unit == "lb":
        return value / IN_PER_CM
    return value


def height_from_cm(cm: float, unit: str) -> float:
    if unit == "lb":
        return cm * IN_PER_CM
    return cm


def format_height(cm: float | None, unit: str) -> str:
    if cm is None:
        return ""
    if unit == "lb":
        total_inches = cm * IN_PER_CM
        feet = int(total_inches // 12)
        inches = total_inches - feet * 12
        return f"{feet}' {inches:.0f}\""
    return f"{cm:.0f} cm"


def unit_label(unit: str) -> str:
    return "lb" if unit == "lb" else "kg"


def height_unit_label(unit: str) -> str:
    return "in" if unit == "lb" else "cm"


M_PER_MILE = 1609.344
M_PER_KM = 1000.0


def distance_unit_label(unit: str) -> str:
    return "mi" if unit == "lb" else "km"


def to_meters(value: float, unit: str) -> float:
    if unit == "lb":
        return value * M_PER_MILE
    return value * M_PER_KM


def from_meters(meters: float, unit: str) -> float:
    if unit == "lb":
        return meters / M_PER_MILE
    return meters / M_PER_KM


def format_distance(meters: float | None, unit: str) -> str:
    if meters is None:
        return "—"
    value = from_meters(meters, unit)
    label = distance_unit_label(unit)
    if value >= 10:
        return f"{value:.1f} {label}"
    return f"{value:.2f} {label}"


def parse_duration(raw: str | None) -> int | None:
    """Accept minutes (`32`), `mm:ss`, or `h:mm:ss`. Returns seconds."""
    text = (raw or "").strip()
    if not text:
        return None
    if ":" not in text:
        try:
            minutes = float(text)
        except ValueError:
            return None
        if minutes <= 0 or minutes > 24 * 60:
            return None
        return int(round(minutes * 60))
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        minutes, seconds = nums
        hours = 0.0
    elif len(nums) == 3:
        hours, minutes, seconds = nums
    else:
        return None
    total = int(round(hours * 3600 + minutes * 60 + seconds))
    if total <= 0 or total > 24 * 3600:
        return None
    return total


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_pace(meters: float | None, seconds: int | None, unit: str) -> str:
    if meters is None or seconds is None or meters <= 0 or seconds <= 0:
        return "—"
    dist = from_meters(meters, unit)
    if dist <= 0:
        return "—"
    sec_per = seconds / dist
    minutes, secs = divmod(int(round(sec_per)), 60)
    label = "/mi" if unit == "lb" else "/km"
    return f"{minutes}:{secs:02d}{label}"


def duration_input_value(seconds: int | None) -> str:
    if seconds is None:
        return ""
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    if secs:
        return f"{minutes}:{secs:02d}"
    return str(minutes)
