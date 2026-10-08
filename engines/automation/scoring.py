"""Transparent prioritisation of automation opportunities.

    Priority = w1*Impact + w2*Suitability + w3*Frequency + w4*TimeSaving - w5*Complexity - w6*Risk

Every criterion is scaled 0..1. The weighted result is then rescaled to 0..100 so that 0 is the worst
possible opportunity and 100 the best. Weights are visible and editable in the app.
"""
import numpy as np
import pandas as pd

from config.automation import (DEFAULT_WEIGHTS, IMPLEMENTATION_COST, NEGATIVE, NO_AUTOMATION, POSITIVE,
                               WEIGHT_LABELS)


def _scaled(series: pd.Series) -> pd.Series:
    top = series.max()
    return series / top if pd.notna(top) and top > 0 else series * 0.0


def complexity_band(c: float) -> str:
    return "Low" if c < 0.35 else "Medium" if c < 0.55 else "High"


def score_opportunities(signals: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)
    if sum(w.values()) <= 0:
        w = dict(DEFAULT_WEIGHTS)
    s = signals.copy()

    parts = [_scaled(s["share_of_time"])]
    if s["sla_attribution"].notna().any():
        parts.append(_scaled(s["sla_attribution"].fillna(0)))
    crit = pd.DataFrame({
        "impact": pd.concat(parts, axis=1).mean(axis=1),
        "suitability": s["suitability"] / 100,
        "frequency": s["volume_score"],
        "time_saving": _scaled(s["hours_saved_month"]),
        "complexity": s["complexity"],
        "risk": s["risk"],
    })
    for k in crit:
        s[f"c_{k}"] = crit[k]

    wpos = sum(w[k] for k in POSITIVE)
    wneg = sum(w[k] for k in NEGATIVE)
    pos = sum(w[k] * crit[k] for k in POSITIVE)
    neg = sum(w[k] * crit[k] for k in NEGATIVE)
    s["priority"] = 100 * (pos - neg + wneg) / (wpos + wneg)
    s["value"] = 100 * pos / wpos if wpos > 0 else 0.0
    s["difficulty"] = 100 * neg / wneg if wneg > 0 else 0.0

    s["quadrant"] = np.select(
        [s["recommended"] == NO_AUTOMATION,
         (s["value"] >= 50) & (s["difficulty"] < 50), (s["value"] >= 50) & (s["difficulty"] >= 50),
         (s["value"] < 50) & (s["difficulty"] < 50)],
        ["Not recommended", "Quick win", "Strategic project", "Fill-in"], default="Reconsider")
    s["complexity_band"] = s["complexity"].map(complexity_band)
    s["impl_cost_default"] = s["complexity_band"].map(IMPLEMENTATION_COST)

    ranked = s[s["recommended"] != NO_AUTOMATION].sort_values("priority", ascending=False)
    s["rank"] = np.nan
    s.loc[ranked.index, "rank"] = np.arange(1, len(ranked) + 1)
    return s.sort_values(["rank", "priority"], ascending=[True, False], na_position="last").reset_index(drop=True)


def breakdown(row: pd.Series, weights: dict[str, float] | None = None) -> tuple[pd.DataFrame, float]:
    """Shows exactly how one opportunity's priority score was built. Returns (table, baseline).

    priority = baseline + sum of the contributions in the table.
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)
    if sum(w.values()) <= 0:
        w = dict(DEFAULT_WEIGHTS)
    total = sum(w.values())
    rows = []
    for k in POSITIVE + NEGATIVE:
        sign = 1 if k in POSITIVE else -1
        value = float(row[f"c_{k}"])
        rows.append({"Criterion": WEIGHT_LABELS[k], "Weight": w[k] / total * 100,
                     "Score (0-100)": value * 100, "Contribution": sign * 100 * w[k] * value / total})
    baseline = 100 * sum(w[k] for k in NEGATIVE) / total
    return pd.DataFrame(rows), baseline