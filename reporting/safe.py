"""Protects exported spreadsheets from formula injection.

A cell that starts with = + - @ (or a tab/carriage return) can be executed as a formula when a file is opened in
Excel. Because category labels come from uploaded data, every text cell is neutralised before export.
"""
import pandas as pd

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    if isinstance(value, str) and value.startswith(_DANGEROUS):
        return "'" + value
    return value


def sanitize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(safe_cell)
    return out