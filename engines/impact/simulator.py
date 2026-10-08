"""Business impact simulator. Every output is an estimate driven by the user's assumptions."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engines.metrics.process_metrics import _case_table as build_case_table
from engines.metrics.timings import add_timings
from models.automation import Globals, ScenarioResult, StepInput
from models.mapping import EventLog


@dataclass
class Prep:
    cycle_h: pd.Series          # valid cases only
    sla: pd.Series | None
    proc: pd.DataFrame          # case x step: working hours
    elapsed: pd.DataFrame       # case x step: working + waiting hours
    monthly_occ: pd.Series      # historical occurrences per month, by step
    monthly_cases: float


def prepare(log: EventLog) -> Prep:
    df = log.df
    has_end = "end_timestamp" in df
    ev = add_timings(df, has_end)
    cases = build_case_table(df, has_end)
    valid = cases[cases["valid"]]
    last = ev["end_timestamp"].max() if has_end else ev["timestamp"].max()
    months = max((last - ev["timestamp"].min()) / pd.Timedelta(days=30.44), 0.1)

    def matrix(col: str) -> pd.DataFrame:
        m = ev.groupby(["case_id", "activity"])[col].sum().unstack(fill_value=0.0)
        return m.reindex(valid.index).fillna(0.0)

    sla = valid["sla"] if "sla" in valid and valid["sla"].notna().any() else None
    return Prep(valid["cycle_h"], sla, matrix("processing_h"), matrix("elapsed_h"),
                ev.groupby("activity").size() / months, log.cases / months)


def _stats(cycle: pd.Series, sla: pd.Series | None) -> dict:
    out = {"avg_cycle_h": float(cycle.mean()), "p90_cycle_h": float(cycle.quantile(0.9))}
    if sla is not None:
        ok = (cycle <= sla)[sla.notna()]
        out["sla_compliance"] = float(ok.mean())
    return out


def simulate(prep: Prep, steps: list[StepInput], g: Globals) -> ScenarioResult:
    scale = g.monthly_volume / prep.monthly_cases if prep.monthly_cases > 0 else 1.0
    rows = []
    saved_case = pd.Series(0.0, index=prep.cycle_h.index)
    for s in steps:
        occ = float(prep.monthly_occ.get(s.step, 0.0)) * scale
        current_h = occ * s.handson_min / 60
        saved_h = current_h * s.reduction if s.include else 0.0
        if s.include and s.step in prep.proc.columns:
            base = prep.elapsed[s.step] if s.waiting else prep.proc[s.step]
            saved_case = saved_case + s.reduction * base
        rows.append({
            "Step": s.step, "Included": s.include, "Occurrences / month": occ,
            "Hands-on hours now / month": current_h if s.include else 0.0,
            "Hours saved / month": saved_h, "Saving / month": saved_h * g.hourly_cost,
            "Implementation cost": s.impl_cost if s.include else 0.0,
        })
    per_step = pd.DataFrame(rows)

    hours = float(per_step["Hours saved / month"].sum())
    month = hours * g.hourly_cost
    impl = float(per_step["Implementation cost"].sum())
    running = impl * g.running_cost_pct
    net_year = month * 12 - running
    monthly_net = month - running / 12
    payback = impl / monthly_net if impl > 0 and monthly_net > 0 else None

    improved_cycle = (prep.cycle_h - saved_case).clip(lower=0)
    now_h = float(per_step["Hands-on hours now / month"].sum())
    current = _stats(prep.cycle_h, prep.sla) | {"handson_h_month": now_h, "labour_cost_month": now_h * g.hourly_cost}
    improved = _stats(improved_cycle, prep.sla) | {"handson_h_month": now_h - hours,
                                                   "labour_cost_month": (now_h - hours) * g.hourly_cost}
    return ScenarioResult(per_step, hours, month, month * 12, running, net_year, impl, payback,
                          net_year * 3 - impl, current, improved)


def sensitivity(prep: Prep, steps: list[StepInput], g: Globals,
                factors: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25)) -> pd.DataFrame:
    rows = []
    for f in factors:
        scaled = [StepInput(s.step, s.include, s.handson_min, min(1.0, s.reduction * f), s.impl_cost, s.waiting)
                  for s in steps]
        r = simulate(prep, scaled, g)
        rows.append({"Achieved vs assumed": f"{f:.0%}", "Hours saved / month": r.hours_saved_month,
                     "Net saving / year": r.net_year,
                     "Payback (months)": r.payback_months if r.payback_months is not None else np.nan})
    return pd.DataFrame(rows)