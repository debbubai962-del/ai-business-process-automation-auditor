"""End-to-end smoke test: the real app.py renders every workspace, with and without data."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from engines.mapping.detector import detect_mapping
from engines.mapping.event_log import build_event_log
from engines.quality.engine import clean_dataset
from models.dataset import LoadedDataset

ROOT = Path(__file__).resolve().parents[1]
MESSY = ROOT / "sample_data" / "invoice_process_messy.csv"


@pytest.fixture(scope="module")
def state():
    if not MESSY.exists():
        pytest.skip("Run sample_data/generate_demo_data.py first")
    raw = pd.read_csv(MESSY)
    q = clean_dataset(raw)
    assignments = {k: v for k, v in detect_mapping(q.cleaned).assignments.items() if v}
    return {"dataset": LoadedDataset("invoice_process_messy.csv", raw, "demo"), "quality": q,
            "quality_approved": True, "event_log": build_event_log(q.cleaned, assignments),
            "mapping_confirmed": assignments}


def _run(page: int, state: dict | None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    at.session_state["nav_index"] = page
    for k, v in (state or {}).items():
        at.session_state[k] = v
    return at.run()


@pytest.mark.parametrize("page", range(6))
def test_every_workspace_renders_with_data(state, page):
    at = _run(page, state)
    assert not at.exception, at.exception


@pytest.mark.parametrize("page", range(6))
def test_every_workspace_renders_without_data(page):
    at = _run(page, None)
    assert not at.exception, at.exception


def test_no_api_key_text_ever_rendered(state, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-TOPSECRET-999")
    for page in (4, 5):
        at = _run(page, state)
        shown = " ".join(m.value for m in at.markdown) + " ".join(str(c.value) for c in at.caption)
        assert "TOPSECRET" not in shown