"""Per-value date parsing for columns that mix several date layouts."""
import re

import numpy as np
import pandas as pd

_SLASHED = re.compile(
    r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$"
)


def parse_mixed_dates(series: pd.Series) -> tuple[pd.Series, dict]:
    """Convert a text column to real timestamps without guessing silently.

    ISO values (2025-03-15 09:30:00) are unambiguous. Values like 04/05/2025 can be read two ways,
    so each one is resolved on its own evidence: a part greater than 12 must be the day. Only values
    where both parts are 12 or less are truly ambiguous; those follow the column's majority layout.
    """
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    present = series.notna()
    text = series[present].astype(str).str.strip()

    iso_mask = text.str.match(r"^\d{4}-\d{2}-\d{2}")
    iso = pd.to_datetime(text[iso_mask], format="ISO8601", errors="coerce")
    out.loc[iso.index] = iso

    rest = text[~iso_mask]
    parts = rest.str.extract(_SLASHED)
    ok = parts[0].notna()
    nums = parts[ok].apply(pd.to_numeric)

    info = {"total": int(present.sum()), "iso": int(iso_mask.sum()), "other_layout": int(ok.sum()),
            "rule": None, "ambiguous": 0, "unreadable": 0}

    if ok.any():
        a, b = nums[0], nums[1]
        day_evidence = int((a > 12).sum())
        month_evidence = int((b > 12).sum())
        if day_evidence > month_evidence:
            rule = "day first"
        elif month_evidence > day_evidence:
            rule = "month first"
        else:
            rule = None
        info["rule"] = rule

        ambiguous = (a <= 12) & (b <= 12) & (a != b)
        info["ambiguous"] = int(ambiguous.sum())

        if rule == "day first":
            amb_day, amb_month = a, b
        elif rule == "month first":
            amb_day, amb_month = b, a
        else:
            amb_day = amb_month = pd.Series(np.nan, index=nums.index)

        day = np.where(a > 12, a, np.where(b > 12, b, amb_day))
        month = np.where(a > 12, b, np.where(b > 12, a, amb_month))
        built = pd.to_datetime(
            pd.DataFrame({"year": nums[2], "month": month, "day": day,
                          "hour": nums[3].fillna(0), "minute": nums[4].fillna(0),
                          "second": nums[5].fillna(0)}, index=nums.index),
            errors="coerce",
        )
        out.loc[built.index] = built

    info["unreadable"] = int(present.sum() - out[present].notna().sum())
    return out, info