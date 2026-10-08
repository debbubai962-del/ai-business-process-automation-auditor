from pathlib import Path

import pandas as pd
import pytest

from engines.mapping.detector import detect_mapping
from engines.mapping.event_log import build_event_log
from engines.metrics.process_metrics import compute_metrics
from engines.quality.engine import clean_dataset

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


def test_exact_values_on_hand_checked_example():
    k = compute_metrics(_tiny_log()).kpis
    assert k["avg_cycle_h"] == pytest.approx(5.5)       # A = 4h, B = 7h
    assert k["median_cycle_h"] == pytest.approx(5.5)
    assert k["sla_compliance"] == pytest.approx(0.5)     # A passes, B breaches
    assert k["rework_rate"] == pytest.approx(0.5)        # B repeats S2
    assert k["first_time_right"] == pytest.approx(0.5)


def test_step_waiting_and_working_times():
    s = compute_metrics(_tiny_log()).steps.set_index("activity")
    assert s.loc["S2", "avg_processing_h"] == pytest.approx(1.0)
    assert s.loc["S2", "avg_wait_h"] == pytest.approx(2.0)   # waits 2h, 1h and 3h
    assert s.loc["S2", "occurrences"] == 3


@pytest.fixture(scope="module")
def demo():
    if not MESSY.exists():
        pytest.skip("Run sample_data/generate_demo_data.py first")
    c = clean_dataset(pd.read_csv(MESSY)).cleaned
    return compute_metrics(build_event_log(c, detect_mapping(c).assignments))


def test_demo_finds_planted_bottleneck(demo):
    assert demo.steps.iloc[0]["activity"] == "Manager Approval"
    assert demo.steps.iloc[0]["share_of_time"] > 0.7


def test_demo_rework_matches_ground_truth(demo):
    assert demo.kpis["rework_rate"] == pytest.approx(663 / 5000)


def test_demo_excludes_impossible_cases_and_says_so(demo):
    assert demo.kpis["cases_analysed"] < demo.kpis["cases_total"]
    assert any("excluded from duration metrics" in n for n in demo.notes)


def test_demo_main_path(demo):
    assert 0.75 < demo.variants.iloc[0]["share"] < 0.82