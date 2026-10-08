"""Dataset profiling. Describes the data without changing it."""
import warnings

import pandas as pd

from models.dataset import ColumnProfile, DatasetProfile


def _datetime_share(series: pd.Series) -> float:
    """Share of non-null values that parse as dates (tries both common styles)."""
    sample = series.dropna().astype(str).head(500)
    if sample.empty:
        return 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = pd.to_datetime(sample, errors="coerce", dayfirst=False).notna().mean()
        b = pd.to_datetime(sample, errors="coerce", dayfirst=True).notna().mean()
    return float(max(a, b))


def detect_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        unique_ratio = non_null.nunique() / len(non_null)
        if unique_ratio > 0.95 and non_null.nunique() > 50 and pd.api.types.is_integer_dtype(series):
            return "identifier"
        return "numeric"

    # Text columns: date, identifier, categorical, or free text
    if _datetime_share(series) >= 0.8:
        return "datetime"
    unique_ratio = non_null.nunique() / len(non_null)
    if non_null.nunique() <= 50 or unique_ratio < 0.05:
        return "categorical"
    avg_len = non_null.astype(str).str.len().mean()
    if avg_len > 60:
        return "text"
    return "identifier" if unique_ratio > 0.5 else "categorical"


def profile_dataset(df: pd.DataFrame) -> DatasetProfile:
    rows, cols = df.shape
    column_profiles: list[ColumnProfile] = []
    date_candidates: list[pd.Series] = []

    for name in df.columns:
        s = df[name]
        missing = int(s.isna().sum())
        dtype = detect_type(s)
        samples = [str(v) for v in s.dropna().astype(str).unique()[:3]]
        column_profiles.append(
            ColumnProfile(
                name=str(name),
                detected_type=dtype,
                missing=missing,
                missing_pct=round(missing / rows * 100, 1) if rows else 0.0,
                unique=int(s.nunique(dropna=True)),
                sample_values=samples,
            )
        )
        if dtype == "datetime":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(s, errors="coerce")
            date_candidates.append(parsed)

    date_min = date_max = None
    if date_candidates:
        combined = pd.concat(date_candidates).dropna()
        if not combined.empty:
            date_min = combined.min().strftime("%d %b %Y")
            date_max = combined.max().strftime("%d %b %Y")

    return DatasetProfile(
        rows=rows,
        columns=cols,
        memory_mb=round(df.memory_usage(deep=True).sum() / 1024**2, 2),
        duplicate_rows=int(df.duplicated().sum()),
        total_missing_cells=int(df.isna().sum().sum()),
        date_min=date_min,
        date_max=date_max,
        column_profiles=column_profiles,
    )