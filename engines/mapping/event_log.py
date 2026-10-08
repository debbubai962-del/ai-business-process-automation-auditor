"""Validates a column mapping and builds the canonical event log."""
import pandas as pd

from engines.mapping.roles import ROLE_BY_KEY, ROLES
from models.mapping import EventLog

CANONICAL = {r.key: r.key for r in ROLES}


def validate_mapping(df: pd.DataFrame, assignments: dict[str, str | None]) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors block building the event log."""
    errors: list[str] = []
    warnings: list[str] = []

    for role in ROLES:
        if role.required and not assignments.get(role.key):
            errors.append(f"'{role.label}' is required. Choose the column that holds it.")

    chosen = [c for c in assignments.values() if c]
    for col in sorted({c for c in chosen if chosen.count(c) > 1}):
        roles = [ROLE_BY_KEY[k].label for k, c in assignments.items() if c == col]
        errors.append(f"Column '{col}' is used for more than one role: {', '.join(roles)}.")

    for key in ("timestamp", "end_timestamp"):
        col = assignments.get(key)
        if col and not pd.api.types.is_datetime64_any_dtype(df[col]):
            errors.append(f"'{col}' is not recognised as dates. Choose a date column, or fix it in Data quality.")
    for key in ("sla", "amount"):
        col = assignments.get(key)
        if col and not pd.api.types.is_numeric_dtype(df[col]):
            errors.append(f"'{col}' is not numeric, so it cannot be used as {ROLE_BY_KEY[key].label}.")

    if not assignments.get("end_timestamp"):
        warnings.append("No end time mapped. Processing time cannot be separated from waiting time; "
                        "the system will use gaps between steps as an approximation and label it as such.")
    return errors, warnings


def build_event_log(df: pd.DataFrame, assignments: dict[str, str | None]) -> EventLog:
    mapped = {k: c for k, c in assignments.items() if c}
    log = pd.DataFrame({k: df[c] for k, c in mapped.items()})
    log["source_row"] = df.index

    dropped: dict[str, int] = {}
    for key in ("case_id", "activity", "timestamp"):
        missing = log[key].isna()
        if missing.any():
            dropped[ROLE_BY_KEY[key].label] = int(missing.sum())
            log = log[~missing]
    log["case_id"] = log["case_id"].astype(str)
    log["activity"] = log["activity"].astype(str)

    notes: list[str] = []
    if "end_timestamp" in log:
        bad = log["end_timestamp"] < log["timestamp"]
        log["valid_duration"] = ~bad
        if bad.any():
            notes.append(f"{int(bad.sum()):,} events end before they start. They stay in the log but are "
                         f"excluded from duration metrics.")

    log = log.sort_values(["case_id", "timestamp"], kind="stable").reset_index(drop=True)

    per_case = log.groupby("case_id").size()
    single = float((per_case == 1).mean()) if len(per_case) else 0.0
    if single > 0.5:
        notes.append(f"{single:.0%} of cases have only one event. The case ID column may be wrong.")

    return EventLog(log, int(log["case_id"].nunique()), len(log), int(log["activity"].nunique()),
                    dropped, notes, mapped)