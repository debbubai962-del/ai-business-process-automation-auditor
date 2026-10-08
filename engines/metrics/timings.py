"""Per-event working, waiting and elapsed time."""
import numpy as np
import pandas as pd

H = pd.Timedelta(hours=1)


def add_timings(df: pd.DataFrame, has_end: bool) -> pd.DataFrame:
    """Adds processing_h, wait_h and elapsed_h (time a case spent at this step) to each event.

    wait_h   = start of this step minus end of the previous step in the same case
    elapsed_h = processing_h + wait_h (first step of a case: processing only)
    Values are blank (NaN) whenever a timestamp involved is invalid, never guessed.
    """
    d = df.copy()
    g = d.groupby("case_id", sort=False)
    first = g.cumcount() == 0
    if has_end:
        d["processing_h"] = np.where(d["valid_duration"], (d["end_timestamp"] - d["timestamp"]) / H, np.nan)
        prev_point = g["end_timestamp"].shift()
        prev_ok = g["valid_duration"].shift().fillna(True).astype(bool)
    else:
        d["processing_h"] = np.nan
        prev_point = g["timestamp"].shift()
        prev_ok = pd.Series(True, index=d.index)
    wait = (d["timestamp"] - prev_point) / H
    d["wait_h"] = wait.where(prev_ok & (wait >= 0))
    if has_end:
        ok = d["processing_h"].notna() & (first | d["wait_h"].notna())
        d["elapsed_h"] = (d["processing_h"] + d["wait_h"].fillna(0)).where(ok)
    else:
        d["elapsed_h"] = d["wait_h"]
    return d