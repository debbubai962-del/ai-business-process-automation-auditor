from pathlib import Path

import pandas as pd
import pytest

from engines.quality.engine import clean_dataset

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
MESSY = SAMPLE / "invoice_process_messy.csv"
CLEAN = SAMPLE / "invoice_process_clean.csv"


@pytest.fixture(scope="module")
def result():
    if not MESSY.exists():
        pytest.skip("Run sample_data/generate_demo_data.py first")
    return clean_dataset(pd.read_csv(MESSY))


def test_rows_match_ground_truth(result):
    assert result.rows_before == 27374
    assert result.rows_after == 26837


def test_headers_trimmed(result):
    assert "Start time" in result.cleaned.columns


def test_departments_merged(result):
    assert set(result.cleaned["Department"].dropna()) == {"Finance Ops", "Procurement", "Logistics", "Operations"}


def test_activities_merged(result):
    assert result.cleaned["Activity"].nunique() == 6


def test_status_typo_fixed(result):
    assert set(result.cleaned["Status"]) == {"Completed"}


def test_dates_are_real_and_in_range(result):
    s = result.cleaned["Start time"]
    assert pd.api.types.is_datetime64_any_dtype(s)
    assert s.isna().sum() == 0
    assert s.min() >= pd.Timestamp("2025-01-06")
    assert s.max() < pd.Timestamp("2025-09-01")


def test_dates_match_clean_file(result):
    if not CLEAN.exists():
        pytest.skip("clean file missing")
    truth = pd.read_csv(CLEAN, parse_dates=["Start Time"])
    got = result.cleaned.sort_values(["invoice_id", "Start time"]).reset_index(drop=True)
    truth = truth.sort_values(["Invoice ID", "Start Time"]).reset_index(drop=True)
    assert (got["Start time"].dt.floor("min") == truth["Start Time"].dt.floor("min")).mean() > 0.999


def test_review_items_are_flagged_not_fixed(result):
    cats = {a.category for a in result.review}
    assert {"Missing", "Validity", "Outliers"} <= cats
    impossible = next(a for a in result.review if a.category == "Validity")
    assert 200 < impossible.records < 350


def test_every_entry_has_status(result):
    assert all(a.status in {"applied", "review"} for a in result.audit)   


def test_compare_shows_department_merges():
    from engines.quality.compare import changed_values
    raw = pd.read_csv(MESSY)
    res = clean_dataset(raw)
    n, table = changed_values(raw, res.cleaned, "Department")
    assert n > 1500
    assert "Finance Ops" in set(table["Cleaned"])
    n_blank, _ = changed_values(raw, res.cleaned, "Priority")
    assert n_blank == 0