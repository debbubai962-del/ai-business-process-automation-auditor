"""Gathers every analysis result into one object used by the AI layer and the report builders. No Streamlit here."""
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from config.automation import DEFAULT_HOURLY_COST, RUNNING_COST_PCT
from engines.automation.scoring import score_opportunities
from engines.automation.signals import compute_signals
from engines.bottlenecks.detector import PRIMARY, detect_bottlenecks
from engines.impact.simulator import Prep, prepare, simulate
from engines.metrics.process_metrics import compute_metrics
from engines.root_cause.analysis import analyse
from models.automation import AutomationReport, Globals, ScenarioResult, StepInput
from models.findings import BottleneckReport, RootCauseReport
from models.mapping import EventLog
from models.metrics import ProcessMetrics
from models.quality import QualityResult


@dataclass
class StaticParts:
    metrics: ProcessMetrics
    bottlenecks: BottleneckReport
    rc_case: RootCauseReport
    rc_step: RootCauseReport
    step_name: str
    automation: AutomationReport
    scored: pd.DataFrame
    prep: Prep


@dataclass
class AnalysisBundle:
    dataset_name: str
    quality: QualityResult
    log: EventLog
    static: StaticParts
    scenario: ScenarioResult
    globals: Globals
    steps: list[StepInput]
    generated_at: str


def compute_static(log: EventLog) -> StaticParts:
    metrics = compute_metrics(log)
    bn = detect_bottlenecks(log)
    prim = bn.table[bn.table["classification"] == PRIMARY]["activity"]
    step = str(prim.iloc[0]) if len(prim) else str(bn.table["activity"].iloc[0])
    automation = compute_signals(log, bn.table)
    return StaticParts(metrics, bn, analyse(log, None), analyse(log, step), step, automation,
                       score_opportunities(automation.signals), prepare(log))


def default_inputs(static: StaticParts) -> tuple[Globals, list[StepInput]]:
    t = static.scored
    top = set(t[t["rank"].notna() & (t["rank"] <= 3)]["activity"])
    steps = [StepInput(r["activity"], r["activity"] in top, float(r["handson_min"]) if pd.notna(r["handson_min"]) else 0.0,
                       float(r["reduction"]), float(r["impl_cost_default"]), bool(r["waiting"]))
             for _, r in t.iterrows()]
    return Globals(DEFAULT_HOURLY_COST, static.automation.monthly_cases, RUNNING_COST_PCT, "$"), steps


def assemble(static: StaticParts, dataset_name: str, quality: QualityResult, log: EventLog,
             inputs: tuple[Globals, list[StepInput]] | None = None) -> AnalysisBundle:
    g, steps = default_inputs(static)
    if inputs is not None:
        ig, isteps = inputs
        if {s.step for s in isteps} == {s.step for s in steps}:
            g, steps = ig, isteps          # use the user's simulator settings when they still match the data
    scenario = simulate(static.prep, steps, g)
    return AnalysisBundle(dataset_name, quality, log, static, scenario, g, steps,
                          datetime.now().strftime("%d %b %Y %H:%M"))