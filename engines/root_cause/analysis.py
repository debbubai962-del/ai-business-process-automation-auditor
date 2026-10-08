"""Root-cause analysis: which factors explain differences in delay, and by how much.

Each factor is tested on its own with a Kruskal-Wallis test (robust to the skewed shape of duration data).
Effect size is epsilon-squared: the share of the variation in delay that the factor accounts for.
Significance uses a Bonferroni-adjusted threshold so that testing many factors does not create false alarms.
"""
import numpy as np
import pandas as pd
from scipy import stats

from engines.metrics.process_metrics import _case_table as build_case_table
from engines.metrics.timings import add_timings
from models.findings import FactorResult, RootCauseReport
from models.mapping import EventLog

MIN_GROUP = 20
BASE_ALPHA = 0.01
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

FACTOR_LABELS = {
    "department": "Department",
    "resource": "Team / employee",
    "priority": "Priority",
    "customer": "Customer / vendor",
    "amount_band": "Case value",
    "weekday": "Day of week (case start)",
    "hour_band": "Time of day (case start)",
    "volume_band": "Daily workload",
    "rework": "Rework",
}

_HYPOTHESES = {
    "department": "Differences between departments may reflect staffing levels, approval authority, or local procedures in '{seg}'.",
    "resource": "Differences between teams may reflect workload allocation, experience, or different working practices in '{seg}'.",
    "priority": "If '{seg}' cases are slower, priority rules may not be applied consistently when work is picked up.",
    "customer": "'{seg}' cases may need extra checks or arrive with incomplete information.",
    "amount_band": "Higher-value cases may trigger additional review or approval levels.",
    "weekday": "Slower work on '{seg}' may point to workload peaks or approver availability on that day.",
    "hour_band": "Cases started '{seg}' may be affected by shift coverage or end-of-day hand-offs.",
    "volume_band": "Slower performance on '{seg}' suggests capacity limits when volume rises.",
    "rework": "Cases with repeated steps take longer simply because work is done twice. Reducing the causes of rework would remove that time.",
}


def _strength(effect: float) -> str:
    return "negligible" if effect < 0.01 else "small" if effect < 0.06 else "moderate" if effect < 0.14 else "strong"


def fmt_hours(h: float) -> str:
    if h is None or pd.isna(h):
        return "n/a"
    return f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} d"


def _bands(series: pd.Series, labels: list[str]) -> pd.Series:
    codes = pd.qcut(series, len(labels), labels=False, duplicates="drop")
    top = int(codes.max()) + 1 if codes.notna().any() else 0
    names = labels if top == len(labels) else [f"Band {i + 1}" for i in range(top)]
    return codes.map(lambda c: names[int(c)] if pd.notna(c) else np.nan)


def build_frame(log: EventLog, step: str | None = None) -> tuple[pd.DataFrame, list[str], str]:
    """One row per valid case with an outcome (hours) and the candidate factors."""
    df = log.df
    has_end = "end_timestamp" in df
    cases = build_case_table(df, has_end)
    notes: list[str] = []

    frame = cases[cases["valid"]].copy()
    if step is None:
        frame["outcome_h"] = frame["cycle_h"]
        label = "Whole-case cycle time"
    else:
        ev = add_timings(df, has_end)
        at_step = ev[(ev["activity"] == step) & ev["elapsed_h"].notna()].groupby("case_id")["elapsed_h"].sum()
        frame = frame.join(at_step.rename("outcome_h"), how="inner")
        label = f"Time spent at '{step}'"
    frame = frame[frame["outcome_h"].notna()]

    if "amount" in frame and frame["amount"].notna().sum() > 40:
        frame["amount_band"] = _bands(frame["amount"], ["Lowest 25%", "Lower-middle", "Upper-middle", "Highest 25%"])
    frame["weekday"] = pd.Categorical(frame["start"].dt.day_name(), categories=WEEKDAYS, ordered=True)
    hour = frame["start"].dt.hour
    frame["hour_band"] = pd.cut(hour, [-1, 11, 16, 23],
                                labels=["Morning (before 12:00)", "Afternoon (12:00-16:59)", "Evening (17:00 or later)"])
    daily = cases.groupby(cases["start"].dt.normalize()).size()
    frame["daily_cases"] = frame["start"].dt.normalize().map(daily)
    frame["volume_band"] = _bands(frame["daily_cases"], ["Quiet days", "Typical days", "Busy days"])
    frame["rework"] = np.where(frame["rework"], "With rework", "No rework")

    if "resource" in frame and "department" in frame:
        if frame.groupby("resource")["department"].nunique().max() == 1:
            notes.append("Each team belongs to exactly one department, so team and department results overlap. "
                         "Treat the department result as the broader explanation.")
    return frame, notes, label


def analyse_factors(frame: pd.DataFrame, outcome_label: str, notes: list[str]) -> RootCauseReport:
    keys = [k for k in FACTOR_LABELS if k in frame and frame[k].nunique() >= 2]
    alpha = BASE_ALPHA / max(len(keys), 1)
    results: list[FactorResult] = []

    for k in keys:
        sub = frame[[k, "outcome_h"]].dropna()
        grouped = sub.groupby(k, observed=True)["outcome_h"]
        stats_df = grouped.agg(cases="size", mean_h="mean", median_h="median").reset_index()
        stats_df = stats_df[stats_df["cases"] >= MIN_GROUP]
        if len(stats_df) < 2:
            continue
        keep = set(stats_df[k])
        sub = sub[sub[k].isin(keep)]
        arrays = [g["outcome_h"].to_numpy() for _, g in sub.groupby(k, observed=True)]
        H, p = stats.kruskal(*arrays)
        n, kk = len(sub), len(arrays)
        effect = float(max(0.0, (H - kk + 1) / (n - kk))) if n > kk else 0.0

        worst_row = stats_df.loc[stats_df["mean_h"].idxmax()]
        best_row = stats_df.loc[stats_df["mean_h"].idxmin()]
        worst = str(worst_row[k])
        rest = sub[sub[k].astype(str) != worst]["outcome_h"]
        rest_mean = float(rest.mean())
        ratio = float(worst_row["mean_h"] / rest_mean) if rest_mean > 0 else float("nan")
        significant = bool(p < alpha)
        strength = _strength(effect)

        statement = (f"Cases in '{worst}' average {fmt_hours(worst_row['mean_h'])} versus "
                     f"{fmt_hours(rest_mean)} for all other cases ({ratio:.2f}x). "
                     f"The fastest group is '{best_row[k]}' at {fmt_hours(best_row['mean_h'])}.")
        hyp = None
        if significant and strength != "negligible":
            hyp = _HYPOTHESES[k].format(seg=worst)
        results.append(FactorResult(
            k, FACTOR_LABELS[k], effect, strength, float(p), significant, n,
            stats_df.rename(columns={k: "segment"}).assign(segment=lambda d: d["segment"].astype(str)),
            worst, str(best_row[k]), float(worst_row["mean_h"]), rest_mean, ratio, statement, hyp))

    results.sort(key=lambda r: r.effect, reverse=True)
    return RootCauseReport(outcome_label, len(frame), float(frame["outcome_h"].mean()), results, notes, alpha, frame)


def analyse(log: EventLog, step: str | None = None) -> RootCauseReport:
    frame, notes, label = build_frame(log, step)
    return analyse_factors(frame, label, notes)


def heatmap_table(frame: pd.DataFrame, row: str, col: str, min_n: int = 15) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Average outcome and case counts for every combination of two factors."""
    g = frame.groupby([row, col], observed=True)["outcome_h"]
    mean = g.mean().unstack(col)
    count = g.size().unstack(col).fillna(0)
    return mean.where(count >= min_n), count