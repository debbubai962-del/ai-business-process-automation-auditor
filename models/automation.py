"""Typed results for the automation engine and the impact simulator."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class AutomationReport:
    signals: pd.DataFrame       # one row per step: measurements, recommendation, reasons
    notes: list[str]
    approximate: bool
    monthly_cases: float
    months: float


@dataclass
class StepInput:
    step: str
    include: bool
    handson_min: float          # hands-on minutes per occurrence (assumption)
    reduction: float            # 0..1 share of that effort removed (assumption)
    impl_cost: float            # one-off cost (assumption)
    waiting: bool               # does the change also shorten queue time?


@dataclass
class Globals:
    hourly_cost: float
    monthly_volume: float       # cases per month
    running_cost_pct: float
    currency: str = "$"


@dataclass
class ScenarioResult:
    per_step: pd.DataFrame
    hours_saved_month: float
    saving_month: float
    saving_year: float
    running_year: float
    net_year: float
    impl_cost: float
    payback_months: float | None
    net_3y: float
    current: dict
    improved: dict