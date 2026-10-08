"""Infers which column plays which role, with a confidence score and a reason."""
import re

import pandas as pd

from engines.mapping.roles import END_PATTERN, ROLES, Role
from models.mapping import ColumnMapping

MIN_SCORE = 0.40


def _kinds(s: pd.Series) -> tuple[bool, bool, bool]:
    dt = pd.api.types.is_datetime64_any_dtype(s)
    num = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
    return dt, num, not dt and not num


def _score(role: Role, name: str, s: pd.Series) -> tuple[float, str]:
    n = int(s.notna().sum())
    if n == 0:
        return 0.0, ""
    dt, num, _ = _kinds(s)
    nun = int(s.nunique())
    hit = bool(role.pattern) and bool(re.search(role.pattern, name, re.I))
    why: list[str] = []

    if role.key == "case_id":
        if dt or (num and not pd.api.types.is_integer_dtype(s)):
            return 0.0, ""
        fits = nun > 1 and 0.001 <= nun / n <= 0.8 and n / nun >= 2
        if hit:
            why.append("the column name looks like an identifier")
        if fits:
            why.append(f"{nun:,} distinct values repeating about {n / nun:.1f} times each, as expected for a case ID")
        if hit:
            score = 0.5 + (0.5 if fits else 0.0)
        else:
            score = 0.35 if fits else 0.0   # below the threshold: the system asks instead of guessing
        return score, "; ".join(why)

    if role.key == "timestamp":
        if not dt or re.search(END_PATTERN, name, re.I):
            return 0.0, ""
        if hit:
            return 1.0, "date/time column whose name suggests the start of a step"
        return 0.45, "the only kind of column that holds dates, but its name is not specific"

    if role.key == "end_timestamp":
        if dt and re.search(END_PATTERN, name, re.I):
            return 1.0, "date/time column whose name suggests the end of a step"
        return 0.0, ""

    if role.kind == "numeric":
        if not num:
            return 0.0, ""
        return (1.0, "numeric column whose name matches") if hit else (0.0, "")

    # text-like roles: activity, department, resource, priority, status, customer
    if dt:
        return 0.0, ""
    if role.key not in ("priority", "status") and num:
        return 0.0, ""
    fits = 2 <= nun <= role.max_distinct
    if role.key == "activity":
        if hit and fits:
            return 1.0, f"name matches and {nun} distinct step names were found"
        return (0.35, "") if fits else (0.0, "")
    if hit and fits:
        return 1.0, f"name matches and {nun} distinct values were found"
    if hit:
        if nun < 2:
            return 0.6, "name matches, but every record has the same value, so it carries little information"
        return 0.6, f"name matches, but {nun} distinct values is unusual for this field"
    return 0.0, ""


def detect_mapping(df: pd.DataFrame) -> ColumnMapping:
    candidates = []
    for order, role in enumerate(ROLES):
        for col in df.columns:
            score, why = _score(role, str(col), df[col])
            if score >= MIN_SCORE:
                candidates.append((-score, order, role.key, str(col), why))
    candidates.sort()

    assignments: dict[str, str | None] = {r.key: None for r in ROLES}
    confidence: dict[str, float] = {r.key: 0.0 for r in ROLES}
    reasons: dict[str, str] = {r.key: "" for r in ROLES}
    used: set[str] = set()
    for neg, _, key, col, why in candidates:
        if assignments[key] is None and col not in used:
            assignments[key] = col
            confidence[key] = -neg
            reasons[key] = why
            used.add(col)
    return ColumnMapping(assignments, confidence, reasons)


def confidence_label(score: float) -> str:
    return "High" if score >= 0.85 else "Medium" if score >= 0.6 else "Low"