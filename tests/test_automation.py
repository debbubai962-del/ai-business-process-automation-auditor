from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config.automation import NO_AUTOMATION
from engines.automation.scoring import breakdown, score_opportunities
from engines.automation.signals import compute_signals
from engines.bottlenecks.detector import detect_bottlenecks
from engines.impact.simulator import Prep, prepare, sensitivity, simulate
from engines.mapping.detector import detect_mapping
from engines.mapping.event_log import build_event_log
from engines.quality.engine import clean_dataset
from models.automation import Globals, StepInput

MESSY = Path(__file__).resolve().parents[1] / "sample_data" / "invoice_process_messy.csv"


@pytest.fixture(scope="module")
def cleaned():
    if not MESSY.exists():
        pytest.skip("Run sample_data/generate_demo_data.py first")
    return clean_dataset(pd.read_csv(MESSY)).cleaned


@pytest.fixture(scope="module")
def log(cleaned):
    return build_event_log(cleaned, detect_mapping(cleaned).assignments)


@pytest.fixture(scope="module")
def report(log):
    return compute_signals(log, detect_bottlenecks(log).table)


def test_recommendations_match_planted_truth(report):
    rec = dict(zip(report.signals["activity"], report.signals["recommended"]))
    assert rec["Data Entry"] == "RPA"
    assert rec["Three-Way Match"] == "Rule-based automation"
    assert rec["Manager Approval"] == "Process redesign"
    assert rec["Exception Review"] == NO_AUTOMATION      # slow, but judgement-heavy: must NOT be automated


def test_slow_step_is_not_automated_just_because_it_is_slow(report):
    s = report.signals.set_index("activity")
    assert s.loc["Exception Review", "avg_elapsed_h"] > s.loc["Data Entry", "avg_elapsed_h"] * 5
    assert s.loc["Exception Review", "recommended"] == NO_AUTOMATION


def test_ranking_and_exclusion(report):
    t = score_opportunities(report.signals).set_index("activity")
    assert set(t[t["rank"] <= 3].index) == {"Data Entry", "Three-Way Match", "Manager Approval"}
    assert pd.isna(t.loc["Exception Review", "rank"])
    assert t.loc["Data Entry", "quadrant"] == "Quick win"
    assert t.loc["Manager Approval", "quadrant"] == "Strategic project"


def test_breakdown_adds_up_to_priority(report):
    t = score_opportunities(report.signals)
    for _, row in t.iterrows():
        bd, baseline = breakdown(row)
        assert baseline + bd["Contribution"].sum() == pytest.approx(row["priority"])


def test_weights_change_the_ranking(report):
    only_impact = {"impact": 1.0, "suitability": 0, "frequency": 0, "time_saving": 0, "complexity": 0, "risk": 0}
    assert score_opportunities(report.signals, only_impact).iloc[0]["activity"] == "Manager Approval"
    only_saving = {"impact": 0, "suitability": 0, "frequency": 0, "time_saving": 1.0, "complexity": 0, "risk": 0}
    assert score_opportunities(report.signals, only_saving).iloc[0]["activity"] in ("Three-Way Match", "Data Entry")
    zeros = {k: 0 for k in only_impact}
    assert len(score_opportunities(report.signals, zeros)) == len(report.signals)   # falls back to defaults


def _tiny_prep():
    idx = ["a", "b"]
    return Prep(cycle_h=pd.Series([10.0, 20.0], index=idx), sla=pd.Series([16.0, 16.0], index=idx),
                proc=pd.DataFrame({"X": [2.0, 4.0]}, index=idx), elapsed=pd.DataFrame({"X": [5.0, 9.0]}, index=idx),
                monthly_occ=pd.Series({"X": 100.0}), monthly_cases=100.0)


def test_simulator_hand_checked():
    g = Globals(hourly_cost=40, monthly_volume=100, running_cost_pct=0.25)
    r = simulate(_tiny_prep(), [StepInput("X", True, 30, 0.5, 12000, False)], g)
    assert r.hours_saved_month == pytest.approx(25)          # 100 x 30min = 50h, half saved
    assert r.saving_month == pytest.approx(1000)
    assert r.running_year == pytest.approx(3000)
    assert r.net_year == pytest.approx(9000)
    assert r.payback_months == pytest.approx(16)             # 12000 / (1000 - 250)
    assert r.net_3y == pytest.approx(15000)
    assert r.improved["avg_cycle_h"] == pytest.approx(13.5)  # cycles 10,20 minus 1,2 hours
    assert r.current["sla_compliance"] == pytest.approx(0.5)
    assert r.improved["sla_compliance"] == pytest.approx(0.5)   # 9 ok, 18 still late


def test_simulator_waiting_changes_help_sla():
    g = Globals(40, 100, 0.25)
    r = simulate(_tiny_prep(), [StepInput("X", True, 30, 0.5, 12000, True)], g)
    assert r.improved["sla_compliance"] == pytest.approx(1.0)    # 7.5 and 15.5 are both within 16


def test_simulator_scales_with_volume_and_handles_never_paying_back():
    r = simulate(_tiny_prep(), [StepInput("X", True, 30, 0.5, 12000, False)], Globals(40, 200, 0.25))
    assert r.hours_saved_month == pytest.approx(50)
    bad = simulate(_tiny_prep(), [StepInput("X", True, 1, 0.1, 10_000_000, False)], Globals(40, 100, 0.25))
    assert bad.payback_months is None


def test_sensitivity_is_monotonic():
    s = sensitivity(_tiny_prep(), [StepInput("X", True, 30, 0.4, 12000, False)], Globals(40, 100, 0.25))
    assert s["Net saving / year"].is_monotonic_increasing
    assert s["Hours saved / month"].iloc[0] == pytest.approx(s["Hours saved / month"].iloc[2] / 2)


def test_demo_scenario_is_credible(log, report):
    t = score_opportunities(report.signals)
    steps = [StepInput(r["activity"], r["rank"] <= 3, r["handson_min"], r["reduction"],
                       r["impl_cost_default"], bool(r["waiting"])) for _, r in t.iterrows()]
    res = simulate(prepare(log), steps, Globals(30, report.monthly_cases, 0.2))
    assert res.hours_saved_month > 0
    assert res.payback_months is not None and 1 < res.payback_months < 12   # not an absurd claim
    assert res.improved["avg_cycle_h"] < res.current["avg_cycle_h"]
    assert res.improved["sla_compliance"] > res.current["sla_compliance"]


def test_dataset_without_end_time_degrades_instead_of_crashing(cleaned):
    c = cleaned.drop(columns=["End Time"])
    a = {k: v for k, v in detect_mapping(c).assignments.items() if v}
    log = build_event_log(c, a)
    bn = detect_bottlenecks(log)
    assert bn.approximate
    rep = compute_signals(log, bn.table)
    assert rep.approximate and rep.signals["handson_min"].isna().all()
    assert (rep.signals["confidence"] == "Low").all()
    assert len(score_opportunities(rep.signals)) == 6