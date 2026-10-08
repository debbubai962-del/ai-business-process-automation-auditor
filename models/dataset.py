"""Typed containers shared across the app."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class LoadedDataset:
    name: str
    df: pd.DataFrame
    source: str = "upload"  # "upload" or "demo"
    sheet_names: list[str] = field(default_factory=list)


@dataclass
class ColumnProfile:
    name: str
    detected_type: str  # identifier, datetime, numeric, categorical, text, empty
    missing: int
    missing_pct: float
    unique: int
    sample_values: list[str]


@dataclass
class DatasetProfile:
    rows: int
    columns: int
    memory_mb: float
    duplicate_rows: int
    total_missing_cells: int
    date_min: str | None
    date_max: str | None
    column_profiles: list[ColumnProfile]