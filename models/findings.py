"""Typed results for bottleneck detection and root-cause analysis."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class BottleneckReport:
    table: pd.DataFrame
    notes: list[str]
    approximate: bool
    n_cases: int
    severity_threshold_h: float = 0.0


@dataclass
class FactorResult:
    key: str
    label: str
    effect: float            # epsilon-squared from a Kruskal-Wallis test, 0..1
    strength: str            # negligible | small | moderate | strong
    p_value: float
    significant: bool
    n: int
    groups: pd.DataFrame     # segment, cases, mean_h, median_h
    worst: str
    best: str
    worst_mean_h: float
    rest_mean_h: float
    ratio: float
    statement: str           # observed fact
    hypothesis: str | None   # rule-based possible explanation (not proven)


@dataclass
class RootCauseReport:
    outcome_label: str
    n: int
    mean_h: float
    results: list[FactorResult]
    notes: list[str]
    alpha: float
    frame: pd.DataFrame = field(repr=False, default=None)