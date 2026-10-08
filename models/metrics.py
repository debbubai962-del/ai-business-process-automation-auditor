"""Typed results of the process metrics engine."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ProcessMetrics:
    kpis: dict[str, float | None]
    cases: pd.DataFrame          # one row per case
    steps: pd.DataFrame          # one row per activity
    variants: pd.DataFrame       # most common paths
    notes: list[str]
    methods: list[tuple[str, str, str]]   # (metric, formula, columns used)
    approximate: bool = False