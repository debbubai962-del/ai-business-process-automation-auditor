"""Times each stage of the pipeline on the demo data (and a larger synthetic copy). Run: python tools\\benchmark.py"""
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.evidence import build_evidence                      # noqa: E402
from engines.mapping.detector import detect_mapping         # noqa: E402
from engines.mapping.event_log import build_event_log       # noqa: E402
from engines.quality.engine import clean_dataset            # noqa: E402
from services.bundle import assemble, compute_static        # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "sample_data" / "invoice_process_messy.csv"


def timed(label, fn):
    t = time.perf_counter()
    out = fn()
    print(f"  {label:<28}{time.perf_counter() - t:6.2f} s")
    return out


def run(df: pd.DataFrame, name: str) -> None:
    print(f"\n{name}: {len(df):,} rows")
    q = timed("data quality engine", lambda: clean_dataset(df))
    a = {k: v for k, v in detect_mapping(q.cleaned).assignments.items() if v}
    log = timed("mapping + event log", lambda: build_event_log(q.cleaned, a))
    st = timed("all analysis engines", lambda: compute_static(log))
    timed("scenario + evidence pack", lambda: build_evidence(assemble(st, name, q, log)))


if __name__ == "__main__":
    base = pd.read_csv(SRC)
    run(base, "Demo data")
    big = []
    for i in range(5):
        c = base.copy()
        c["invoice_id"] = c["invoice_id"].astype(str) + f"-{i}"
        big.append(c)
    run(pd.concat(big, ignore_index=True), "5x larger synthetic copy")