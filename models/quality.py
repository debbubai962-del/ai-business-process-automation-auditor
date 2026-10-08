"""Typed results of the Data Quality Engine."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class AuditEntry:
    category: str          # Structure, Text, Categories, Dates, Duplicates, Missing, Validity, Outliers
    column: str
    issue: str             # original issue, in business language
    action: str            # action taken, or recommended action
    records: int           # records affected
    status: str            # "applied" (safe fix made) or "review" (needs a human decision)
    details: list[str] = field(default_factory=list)
    sample: pd.DataFrame | None = None


@dataclass
class QualityResult:
    cleaned: pd.DataFrame
    quarantined: pd.DataFrame   # rows removed (kept for audit)
    audit: list[AuditEntry]
    rows_before: int
    rows_after: int

    @property
    def applied(self) -> list[AuditEntry]:
        return [a for a in self.audit if a.status == "applied"]

    @property
    def review(self) -> list[AuditEntry]:
        return [a for a in self.audit if a.status == "review"]