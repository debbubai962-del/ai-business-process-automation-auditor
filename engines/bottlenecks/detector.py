"""Bottleneck detection: separates frequent delays from severe ones."""
import numpy as np
import pandas as pd

from engines.metrics.process_metrics import _case_table as build_case_table
from engines.metrics.timings import add_timings
from models.findings import BottleneckReport
from models.mapping import EventLog

FREQUENT_SHARE = 0.20      # step is the longest in at least 20% of cases
SEVERITY_MULT = 3.0        # average time at step >= 3x the typical step
MIN_SEVERE_H = 1.0
SPIKE_MULT = 2.0           # an occurrence is a spike if > 2x that step's median

PRIMARY = "Primary bottleneck"
FREQUENT = "Frequent delay"
OCCASIONAL = "Occasional severe delay"
NONE = "No bottleneck"


def _classify(frequent: bool, severe: bool) -> str:
    if frequent and severe:
        return PRIMARY
    if frequent:
        return FREQUENT
    if severe:
        return OCCASIONAL
    return NONE


def _cause(wait_share: float | None, cv: float | None, approximate: bool) -> str:
    if approximate:
        return ("Time between the previous step starting and this step starting is long. Without an end time, "
                "waiting cannot be told apart from working.")
    if wait_share is not None and wait_share >= 0.5:
        return "Cases mostly wait for this step to start (queueing or hand-off delay) rather than being slow once started."
    if cv is not None and cv >= 1.0:
        return "Time at this step varies widely between cases, which suggests case-dependent complexity or exceptions."
    return "The step itself takes long once started, which suggests effort, complexity or manual checking."


def _confidence(n: int, approximate: bool) -> str:
    level = "High" if n >= 100 else "Medium" if n >= 30 else "Low"
    return "Medium" if approximate and level == "High" else level


def detect_bottlenecks(log: EventLog) -> BottleneckReport:
    df = log.df
    has_end = "end_timestamp" in df
    ev = add_timings(df, has_end)
    cases = build_case_table(df, has_end)
    notes: list[str] = []
    if not has_end:
        notes.append("No end time is mapped. Delays are measured between step starts and are approximate.")

    timed = ev[ev["elapsed_h"].notna()]
    g = timed.groupby("activity")
    step = pd.DataFrame({
        "occurrences": ev.groupby("activity").size(),
        "timed": g.size(),
        "avg_elapsed_h": g["elapsed_h"].mean(),
        "avg_wait_h": g["wait_h"].mean(),
        "avg_processing_h": g["processing_h"].mean(),
        "total_h": g["elapsed_h"].sum(),
        "sd": g["elapsed_h"].std(),
        "median_h": g["elapsed_h"].median(),
        "reach": ev.groupby("activity")["case_id"].nunique() / len(cases),
    })
    step[["timed", "total_h"]] = step[["timed", "total_h"]].fillna(0)   # steps with no measurable time
    step["share_of_time"] = step["total_h"] / step["total_h"].sum()
    step["cv"] = step["sd"] / step["avg_elapsed_h"]
    sum_wait = g["wait_h"].sum()
    sum_proc = g["processing_h"].sum()
    step["wait_share"] = (sum_wait / (sum_wait + sum_proc)) if has_end else np.nan

    med = timed["activity"].map(step["median_h"])
    step["spike_pct"] = (timed["elapsed_h"] > SPIKE_MULT * med).groupby(timed["activity"]).mean()

    # Which step is the longest in each valid case?
    valid_ids = cases.index[cases["valid"]]
    tv = timed[timed["case_id"].isin(valid_ids)]
    per_case = tv.groupby(["case_id", "activity"])["elapsed_h"].sum()
    top = per_case.groupby(level=0).idxmax()
    dominant = pd.Series([t[1] for t in top], index=top.index)
    step["dominant_pct"] = (dominant.value_counts() / len(dominant)).reindex(step.index).fillna(0.0)

    if "sla" in cases and cases["sla"].notna().any():
        breached = cases[cases["valid"] & cases["sla"].notna() & (cases["cycle_h"] > cases["sla"])].index
        d_b = dominant[dominant.index.isin(breached)]
        step["sla_attribution"] = (d_b.value_counts() / len(d_b)).reindex(step.index).fillna(0.0) if len(d_b) else np.nan
        n_breached = int(len(d_b))
    else:
        step["sla_attribution"] = np.nan
        n_breached = 0

    typical = float(step["avg_elapsed_h"].median())
    threshold = max(SEVERITY_MULT * typical, MIN_SEVERE_H)
    step["severe"] = step["avg_elapsed_h"] >= threshold
    step["frequent"] = step["dominant_pct"] >= FREQUENT_SHARE
    step["classification"] = [_classify(f, s) for f, s in zip(step["frequent"], step["severe"])]
    step["likely_cause"] = [_cause(w, c, not has_end) for w, c in zip(step["wait_share"], step["cv"])]
    step["confidence"] = [_confidence(int(n), not has_end) for n in step["timed"]]

    notes.append(f"A step counts as severe when cases spend on average at least {threshold:.1f} h at it "
                 f"({SEVERITY_MULT:.0f}x the typical step), and as frequent when it is the longest step in at "
                 f"least {FREQUENT_SHARE:.0%} of cases.")
    if n_breached:
        notes.append(f"SLA impact is measured over the {n_breached:,} cases that breached their SLA.")

    table = step.sort_values("total_h", ascending=False).reset_index()
    return BottleneckReport(table, notes, not has_end, len(cases), float(threshold))