from pathlib import Path

import pandas as pd
import pytest

from engines.mapping.capabilities import assess_capabilities
from engines.mapping.detector import detect_mapping
from engines.mapping.event_log import build_event_log, validate_mapping
from engines.quality.engine import clean_dataset

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
MESSY = SAMPLE / "invoice_process_messy.csv"
CLEAN = SAMPLE / "invoice_process_clean.csv"

EXPECTED = {
    "case_id": "invoice_id", "activity": "Activity", "timestamp": "Start time",
    "end_timestamp": "End Time", "department": "Department", "resource": "Team",
    "priority": "Priority", "status": "Status", "sla": "SLA_hours",
    "amount": "Invoice Amount", "customer": "Vendor Type",
}


@pytest.fixture(scope="module")
def cleaned():
    if not MESSY.exists():
        pytest.skip("Run sample_data/generate_demo_data.py first")
    return clean_dataset(pd.read_csv(MESSY)).cleaned


def test_detects_every_role_on_cleaned_messy_data(cleaned):
    got = detect_mapping(cleaned).assignments
    assert got == EXPECTED


def test_detects_roles_on_clean_file_with_different_names():
    if not CLEAN.exists():
        pytest.skip("clean file missing")
    df = pd.read_csv(CLEAN, parse_dates=["Start Time", "End Time"])
    got = detect_mapping(df).assignments
    assert got["case_id"] == "Invoice ID" and got["timestamp"] == "Start Time"
    assert got["end_timestamp"] == "End Time" and got["sla"] == "SLA Hours"


def test_event_log_matches_ground_truth(cleaned):
    m = detect_mapping(cleaned).assignments
    errors, warnings = validate_mapping(cleaned, m)
    assert errors == [] and warnings == []
    log = build_event_log(cleaned, m)
    assert log.cases == 5000 and log.events == 26837 and log.activities == 6
    assert log.df["case_id"].is_monotonic_increasing
    assert any("end before they start" in n for n in log.notes)


def test_missing_case_id_is_not_guessed():
    df = pd.DataFrame({"Step": ["a", "b"] * 5, "When": pd.date_range("2025-01-01", periods=10),
                       "Dept": ["x", "y"] * 5})
    m = detect_mapping(df).assignments
    assert m["case_id"] is None
    errors, _ = validate_mapping(df, m)
    assert any("Case / transaction ID" in e for e in errors)


def test_duplicate_column_use_is_rejected(cleaned):
    m = detect_mapping(cleaned).assignments
    m["resource"] = m["department"]
    errors, _ = validate_mapping(cleaned, m)
    assert any("more than one role" in e for e in errors)


def test_capabilities_reflect_missing_end_time(cleaned):
    m = {k: v for k, v in detect_mapping(cleaned).assignments.items() if v and k != "end_timestamp"}
    caps = {c.name: c.status for c in assess_capabilities(m)}
    assert caps["Processing vs waiting time"] == "limited"
    assert caps["Case cycle time"] == "available"