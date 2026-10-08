from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engines.bottlenecks.detector import NONE, OCCASIONAL, PRIMARY, detect_bottlenecks
from engines.mapping.detector import detect_mapping
from engines.mapping.event_log import build_event_log
from engines.quality.engine import clean_dataset
from engines.root_cause.analysis import analyse, analyse_factors, heatmap_table

MESSY = Path(__file__).resolve().parents[1] / "sample_data" / "invoice_process_messy.csv"


def _tiny_log():
    t = pd.Timestamp
    df = pd.DataFrame({
        "id":   ["A", "A", "B", "B", "B"],
        "step": ["S1", "S2", "S1", "S2", "S2"],
        "s": [t("2025-01-01 00:00"), t("2025-01-01 03:00"), t("2025-01-01 00:00"),
              t("2025-01-01 02:00"), t("2025-01-01 06:00")],
        "e": [t("2025-01-01 01:00"), t("2025-01-01 04:00"), t("2025-01-01 01:00"),
              t("2025-01-01 03:00"), t("2025-01-01 07:00")],
        "sla": [5, 5, 5, 5, 5],
    })
    m = {"case_id": "id", "activity": "step", "timestamp": "s", "end_timestamp": "e", "sla": "sla"}
    return build_event_log(df, m)


def test_hand_checked_bottleneck_values():
    t = detect_bottlenecks(_tiny_log()).table.set_index("activity")
    # time at step: A: S1=1, S2=2 wait+1 work=3. B: S1=1, S2 = (1+1) + (3+1) = 6
    assert t.loc["S2", "avg_elapsed_h"] == pytest.approx(3.0)   # (3 + 2 + 4) / 3 occurrences
    assert t.loc["S1", "avg_elapsed_h"] == pytest.approx(1.0)
    assert t.loc["S2", "dominant_pct"] == pytest.approx(1.0)    # longest step in both cases
    assert t.loc["S1", "dominant_pct"] == pytest.approx(0.0)
    assert t.loc["S2", "sla_attribution"] == pytest.approx(1.0)  # only B breaches, and S2 dominates it


@pytest.fixture(scope="module")
def log():
    if not MESSY.exists():
        pytest.skip("Run sample_data/generate_demo_data.py first")
    c = clean_dataset(pd.read_csv(MESSY)).cleaned
    return build_event_log(c, detect_mapping(c).assignments)


def test_demo_bottleneck_classification(log):
    t = detect_bottlenecks(log).table.set_index("activity")
    assert t.loc["Manager Approval", "classification"] == PRIMARY
    assert t.loc["Exception Review", "classification"] == OCCASIONAL   # rare but severe: not "primary"
    assert t.loc["Data Entry", "classification"] == NONE               # busy but quick
    assert t.loc["Manager Approval", "dominant_pct"] > 0.9
    assert t.loc["Manager Approval", "sla_attribution"] > 0.9


def test_demo_root_causes_found_and_controls_clean(log):
    r = {f.key: f for f in analyse(log).results}
    assert r["department"].significant and r["department"].worst == "Finance Ops"
    assert r["priority"].significant and r["priority"].best == "High"
    assert r["weekday"].significant and r["weekday"].worst in ("Monday", "Friday")
    for control in ("amount_band", "customer", "hour_band"):          # nothing was planted here
        assert not r[control].significant


def test_step_level_root_cause(log):
    r = {f.key: f for f in analyse(log, "Manager Approval").results}
    assert r["department"].worst == "Finance Ops" and r["department"].ratio > 1.5
    assert r["department"].hypothesis is not None


def test_pure_noise_is_not_flagged():
    rng = np.random.default_rng(7)
    frame = pd.DataFrame({"department": rng.choice(["A", "B", "C"], 900),
                          "outcome_h": rng.lognormal(3, 0.6, 900)})
    rep = analyse_factors(frame, "noise", [])
    assert rep.results and not rep.results[0].significant
    assert rep.results[0].hypothesis is None


def test_heatmap_hides_small_cells(log):
    rep = analyse(log)
    mean, count = heatmap_table(rep.frame, "department", "weekday", min_n=15)
    assert mean.shape == count.shape
    assert mean.isna().equals(count < 15)