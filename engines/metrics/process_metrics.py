"""Deterministic process-health metrics computed from the canonical event log."""
import numpy as np
import pandas as pd

from models.mapping import EventLog
from models.metrics import ProcessMetrics

H = pd.Timedelta(hours=1)
ARROW = " \u2192 "


def _case_table(df: pd.DataFrame, has_end: bool) -> pd.DataFrame:
    g = df.groupby("case_id", sort=False)
    out = pd.DataFrame({
        "start": g["timestamp"].min(),
        "end": g["end_timestamp"].max() if has_end else g["timestamp"].max(),
        "events": g.size(),
        "distinct_steps": g["activity"].nunique(),
        "path": g["activity"].agg(ARROW.join),
    })
    out["rework"] = out["events"] > out["distinct_steps"]
    for col in ("department", "priority", "sla", "amount", "customer", "resource"):
        if col in df:
            out[col] = g[col].first()
    out["valid"] = g["valid_duration"].all() if "valid_duration" in df else True
    out["cycle_h"] = (out["end"] - out["start"]) / H
    return out


def _step_table(df: pd.DataFrame, has_end: bool) -> pd.DataFrame:
    d = df.copy()
    g = d.groupby("case_id", sort=False)
    if has_end:
        d["processing_h"] = np.where(d["valid_duration"], (d["end_timestamp"] - d["timestamp"]) / H, np.nan)
        prev_point = g["end_timestamp"].shift()
        prev_ok = g["valid_duration"].shift().fillna(True).astype(bool)
    else:
        d["processing_h"] = np.nan
        prev_point = g["timestamp"].shift()
        prev_ok = pd.Series(True, index=d.index)
    wait = (d["timestamp"] - prev_point) / H
    d["wait_h"] = wait.where(prev_ok & (wait >= 0))

    s = d.groupby("activity").agg(
        occurrences=("activity", "size"),
        avg_processing_h=("processing_h", "mean"),
        avg_wait_h=("wait_h", "mean"),
        sum_processing_h=("processing_h", "sum"),
        sum_wait_h=("wait_h", "sum"),
    )
    s["total_h"] = s["sum_processing_h"] + s["sum_wait_h"]
    s["share_of_time"] = s["total_h"] / s["total_h"].sum()
    s["share_processing"] = s["sum_processing_h"] / s["total_h"].sum()
    s["share_wait"] = s["sum_wait_h"] / s["total_h"].sum()
    s["avg_elapsed_h"] = s["avg_processing_h"].fillna(0) + s["avg_wait_h"].fillna(0)
    return s.sort_values("total_h", ascending=False).reset_index()


def _variants(cases: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    v = cases.groupby("path").agg(cases=("path", "size"), avg_cycle_h=("cycle_h", "mean"))
    v["share"] = v["cases"] / len(cases)
    return v.sort_values("cases", ascending=False).head(top).reset_index()


def compute_metrics(log: EventLog) -> ProcessMetrics:
    df = log.df
    has_end = "end_timestamp" in df
    notes: list[str] = []

    cases = _case_table(df, has_end)
    usable = cases[cases["valid"]]
    excluded = len(cases) - len(usable)
    if excluded:
        notes.append(f"{excluded:,} of {len(cases):,} cases have at least one step that ends before it starts. "
                     f"They are excluded from duration metrics (cycle time, SLA, step delay) but kept in "
                     f"rework and variant counts.")
    if not has_end:
        notes.append("No end time is mapped, so cycle time ends at the start of the last step and waiting time "
                     "is the gap between step starts. These are approximations.")

    cyc = usable["cycle_h"]
    k: dict[str, float | None] = {
        "cases_total": float(len(cases)),
        "cases_analysed": float(len(usable)),
        "avg_cycle_h": float(cyc.mean()),
        "median_cycle_h": float(cyc.median()),
        "p90_cycle_h": float(cyc.quantile(0.9)),
        "variation_ratio": float(cyc.quantile(0.9) / cyc.median()) if cyc.median() > 0 else None,
        "rework_rate": float(cases["rework"].mean()),
        "first_time_right": float(1 - cases["rework"].mean()),
    }

    if "sla" in cases and usable["sla"].notna().any():
        with_sla = usable[usable["sla"].notna()]
        ok = with_sla["cycle_h"] <= with_sla["sla"]
        k["sla_compliance"] = float(ok.mean())
        k["sla_breach_rate"] = float(1 - ok.mean())
        k["sla_hours"] = float(with_sla["sla"].median())
    else:
        k["sla_compliance"] = k["sla_breach_rate"] = k["sla_hours"] = None

    span_weeks = (cases["end"].max() - cases["start"].min()) / pd.Timedelta(weeks=1)
    k["throughput_per_week"] = float(len(cases) / span_weeks) if span_weeks > 0 else None

    methods = [
        ("Cycle time (average, median, slowest 10%)",
         "For each case: end of its last step minus start of its first step. Average, median and the 90th percentile "
         "are taken across cases.", "Case ID, Start time, End time"),
        ("SLA compliance / breach rate",
         "Share of cases whose cycle time is at or below their SLA target. Breach rate = 1 minus compliance.",
         "Case ID, Start/End time, SLA target"),
        ("Rework rate / first-time-right",
         "A case has rework if any step appears more than once in it. First-time-right = cases without rework "
         "divided by all cases.", "Case ID, Step"),
        ("Throughput",
         "Number of cases divided by the number of weeks between the earliest start and the latest end.",
         "Case ID, Start/End time"),
        ("Variation (slowest 10% vs median)",
         "90th-percentile cycle time divided by median cycle time. Higher means less predictable.",
         "Case ID, Start/End time"),
        ("Working vs waiting time per step",
         "Working = step end minus step start. Waiting = step start minus the previous step's end within the same "
         "case. Each step's share is its total hours divided by the total hours of all steps.",
         "Case ID, Step, Start time, End time"),
        ("Process variants",
         "Each case's ordered list of steps is its path. Cases with identical paths are grouped.",
         "Case ID, Step, Start time"),
    ]
    return ProcessMetrics(k, cases, _step_table(df, has_end), _variants(cases), notes, methods, not has_end)