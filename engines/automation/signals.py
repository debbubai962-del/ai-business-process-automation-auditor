"""Measures how repetitive, rule-based and exception-prone each step is, and recommends an automation type."""
import re

import numpy as np
import pandas as pd

from config.automation import (AUTOMATION_TYPES, HANDS_ON_CAP_MIN, HANDS_ON_SHARE, JUDGMENT_CV,
                               LOW_VOLUME_PER_MONTH, NO_AUTOMATION)
from engines.metrics.timings import add_timings
from models.automation import AutomationReport
from models.mapping import EventLog

CONTROL_RE = r"approv|authori[sz]|review|audit|sign.?off|decision|exception|escalat|investigat|dispute|complian"
ENTRY_RE = r"entry|enter|key|input|capture|transcri|upload|copy|data"
TRANSFER_RE = r"receiv|intake|import|sync|transfer|release|payment|submit|send|notif|post|dispatch"
CHECK_RE = r"match|validat|check|reconcil|calculat|compar|verif|screen|classif"


def _has(pattern: str, name: str) -> bool:
    return bool(re.search(pattern, name, re.I))


def _recommend(r: pd.Series) -> tuple[str, str]:
    """Decision table, applied top to bottom. Returns (type, one-line reason)."""
    name = r["activity"]
    bottleneck = r["classification"] in ("Primary bottleneck", "Frequent delay")
    if r["monthly_volume"] < LOW_VOLUME_PER_MONTH:
        return NO_AUTOMATION, f"Only about {r['monthly_volume']:.0f} per month. Volume is too low to repay the effort."
    if r["judgment_likely"] and r["conditional"]:
        return NO_AUTOMATION, ("Handled in a minority of cases and highly variable in duration, which points to "
                               "case-by-case human judgement. Automating it would add risk.")
    if r["suitability"] < 40:
        return NO_AUTOMATION, "The step is not standardised enough to automate reliably."
    if bottleneck and r["control"]:
        return "Process redesign", ("It is a control step and a major bottleneck. Redesign the approval path first "
                                    "(limits, delegation, parallel review), then add workflow support.")
    if r["control"]:
        return "Human-in-the-loop automation", "Control step: automate routine cases and keep a person for decisions."
    if r["exception_rate"] >= 0.15 and r["suitability"] >= 50:
        return "Human-in-the-loop automation", "Exceptions are frequent, so route them to a person and automate the rest."
    if _has(ENTRY_RE, name) and r["rule_based"] >= 0.6:
        return "RPA", "Repetitive data handling with a consistent routine."
    if _has(CHECK_RE, name) and r["rule_based"] >= 0.6:
        return "Rule-based automation", "A check or comparison that follows fixed rules."
    if _has(TRANSFER_RE, name):
        return "API integration", "A hand-off between systems that can be connected directly."
    if r["wait_share"] >= 0.5:
        return "Workflow automation", "Most of the time is waiting, so routing and reminders help more than speeding up the work."
    if r["suitability"] >= 70:
        return "Rule-based automation", "Highly standardised and frequent."
    return "AI-assisted automation", "Reasonably frequent but not fully standardised."


def compute_signals(log: EventLog, bn: pd.DataFrame) -> AutomationReport:
    df = log.df
    has_end = "end_timestamp" in df
    ev = add_timings(df, has_end)
    notes: list[str] = []

    last = ev["end_timestamp"].max() if has_end else ev["timestamp"].max()
    months = max((last - ev["timestamp"].min()) / pd.Timedelta(days=30.44), 0.1)
    monthly_cases = log.cases / months

    s = bn.set_index("activity")[[
        "occurrences", "reach", "avg_elapsed_h", "avg_processing_h", "wait_share", "cv", "spike_pct",
        "share_of_time", "sla_attribution", "classification"]].copy()
    g = ev.groupby("activity")
    cv_proc = (g["processing_h"].std() / g["processing_h"].mean()) if has_end else s["cv"]
    s["cv_proc"] = cv_proc.reindex(s.index).fillna(s["cv"]).fillna(0.0)

    ev = ev.assign(_next=ev.groupby("case_id")["activity"].shift(-1),
                   _repeat=ev.groupby(["case_id", "activity"]).cumcount() >= 1)
    pred = {}
    for act, grp in ev.groupby("activity"):
        nxt = grp["_next"].dropna()
        pred[act] = float(nxt.value_counts(normalize=True).iloc[0]) if len(nxt) else 1.0
    s["predictability"] = pd.Series(pred)
    s["repeat_rate"] = ev.groupby("activity")["_repeat"].mean()
    s["monthly_volume"] = s["occurrences"] / months
    s["exception_rate"] = (s["repeat_rate"] + s["spike_pct"].fillna(0)).clip(0, 1)
    s["consistency"] = 1 - s["cv_proc"].clip(0, 1)
    s["rule_based"] = (s["predictability"] + s["consistency"]) / 2
    s["conditional"] = s["reach"] < 0.5
    s["control"] = [_has(CONTROL_RE, a) for a in s.index]
    s["judgment_likely"] = s["cv_proc"] >= JUDGMENT_CV
    s["volume_score"] = (np.log10(s["monthly_volume"].clip(lower=1)) / 3).clip(0, 1)
    judgement_score = 1 - ((s["cv_proc"] - 0.4) / 0.6).clip(0, 1)
    s["suitability"] = 100 * (0.35 * s["rule_based"] + 0.25 * s["volume_score"]
                              + 0.25 * (1 - s["exception_rate"]) + 0.15 * judgement_score)
    s["risk"] = (0.45 * s["control"] + 0.30 * s["judgment_likely"]
                 + 0.25 * (s["exception_rate"] / 0.3).clip(0, 1)).clip(0, 1)

    s = s.reset_index()
    rec = s.apply(_recommend, axis=1, result_type="expand")
    s["recommended"], s["rec_reason"] = rec[0], rec[1]

    if has_end:
        s["handson_min"] = (s["avg_processing_h"] * 60 * HANDS_ON_SHARE).clip(upper=HANDS_ON_CAP_MIN)
    else:
        s["handson_min"] = np.nan
        notes.append("No end time is mapped, so hands-on effort cannot be measured. Enter it in the simulator.")
    s["confidence"] = ["Low" if not has_end else "High" if n >= 100 else "Medium" if n >= 30 else "Low"
                       for n in s["occurrences"]]
    s["effort_h_month"] = s["monthly_volume"] * s["handson_min"].fillna(0) / 60
    s["reduction"] = s["recommended"].map(lambda t: AUTOMATION_TYPES[t][0])
    s["type_complexity"] = s["recommended"].map(lambda t: AUTOMATION_TYPES[t][1])
    s["waiting"] = s["recommended"].map(lambda t: AUTOMATION_TYPES[t][2])
    s["complexity"] = (0.5 * s["type_complexity"] + 0.3 * (1 - s["predictability"])
                       + 0.2 * s["cv_proc"].clip(0, 1)).clip(0, 1)
    s["hours_saved_month"] = s["effort_h_month"] * s["reduction"]
    base = np.where(s["waiting"], s["avg_elapsed_h"], s["avg_processing_h"].fillna(0))
    s["cycle_saved_h"] = s["reduction"] * base * s["reach"]

    notes.append(f"Hands-on effort per occurrence is assumed to be {HANDS_ON_SHARE:.0%} of the recorded step duration, "
                 f"capped at {HANDS_ON_CAP_MIN} minutes, because recorded durations include interruptions and waiting. "
                 f"This is an assumption: edit it in the simulator.")
    return AutomationReport(s, notes, not has_end, float(monthly_cases), float(months))