"""Audit-trail table shared by the screen, the CSV download, the Excel workbook and the HTML report."""
import pandas as pd

from models.quality import QualityResult
from reporting.safe import sanitize_frame


def audit_dataframe(q: QualityResult) -> pd.DataFrame:
    return sanitize_frame(pd.DataFrame([{
        "Status": "Fixed" if e.status == "applied" else "Needs review", "Category": e.category, "Column": e.column,
        "Original issue": e.issue, "Action": e.action, "Records affected": e.records, "Details": " | ".join(e.details),
    } for e in q.audit]))