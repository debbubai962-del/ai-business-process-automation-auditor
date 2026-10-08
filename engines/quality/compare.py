"""Original-vs-cleaned comparison for a single column."""
import re

import pandas as pd

_EMPTY = ["Original", "Cleaned", "Records"]


def _as_text(s: pd.Series) -> pd.Series:
    return s.astype("object").where(s.notna(), "").astype(str)


def changed_values(original: pd.DataFrame, cleaned: pd.DataFrame, column: str) -> tuple[int, pd.DataFrame]:
    """Return (number of values changed, table of Original -> Cleaned with counts)."""
    lookup = {re.sub(r"\s+", " ", str(c)).strip(): c for c in original.columns}
    raw_col = lookup.get(column, column)

    before = _as_text(original.loc[cleaned.index, raw_col])
    after = _as_text(cleaned[column])
    changed = before != after
    n = int(changed.sum())
    if n == 0:
        return 0, pd.DataFrame(columns=_EMPTY)

    pairs = pd.DataFrame({"Original": before[changed], "Cleaned": after[changed]})
    if len(pairs.drop_duplicates()) <= 60:
        table = (pairs.groupby(["Original", "Cleaned"]).size().reset_index(name="Records")
                 .sort_values("Records", ascending=False))
    else:
        table = pairs.head(25).assign(Records=1)
    return n, table.reset_index(drop=True)