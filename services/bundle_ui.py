"""Streamlit-side access to the analysis bundle and the generated brief."""
import hashlib
import json

import streamlit as st

from ai.brief import BriefResult
from ai.evidence import build_evidence
from services.bundle import AnalysisBundle, StaticParts, assemble, compute_static
from services.keys import log_key
from services.session import get_dataset, get_event_log, get_quality


@st.cache_data(show_spinner="Gathering all findings...")
def _static(_log, key: tuple) -> StaticParts:
    return compute_static(_log)


def get_bundle() -> AnalysisBundle | None:
    ds, q, log = get_dataset(), get_quality(), get_event_log()
    if ds is None or q is None or log is None:
        return None
    return assemble(_static(log, log_key(log)), ds.name, q, log, st.session_state.get("scenario_inputs"))


def evidence_hash(evidence: dict) -> str:
    return hashlib.sha1(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()[:12]


def get_brief(ev_hash: str) -> BriefResult | None:
    stored = st.session_state.get("brief")
    return stored["result"] if stored and stored["hash"] == ev_hash else None


def has_stale_brief(ev_hash: str) -> bool:
    stored = st.session_state.get("brief")
    return bool(stored) and stored["hash"] != ev_hash


def set_brief(ev_hash: str, result: BriefResult) -> None:
    st.session_state["brief"] = {"hash": ev_hash, "result": result}


def evidence_for(bundle: AnalysisBundle) -> dict:
    return build_evidence(bundle)