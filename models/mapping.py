"""Typed results of process mapping."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ColumnMapping:
    assignments: dict[str, str | None]   # role key -> column name (or None)
    confidence: dict[str, float]         # role key -> 0..1
    reasons: dict[str, str]              # role key -> why the system chose it


@dataclass
class EventLog:
    df: pd.DataFrame
    cases: int
    events: int
    activities: int
    dropped: dict[str, int]
    notes: list[str]
    mapping: dict[str, str]


@dataclass
class Capability:
    name: str
    question: str
    status: str   # available | limited | unavailable
    note: str