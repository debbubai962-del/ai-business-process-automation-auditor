"""Single place for reading and writing the app's session state."""
import streamlit as st

from models.dataset import LoadedDataset
from models.mapping import EventLog
from models.quality import QualityResult


def _reset_mapping() -> None:
    for key in ("event_log", "mapping_confirmed"):
        st.session_state.pop(key, None)
    for key in [k for k in st.session_state if str(k).startswith("map_")]:
        st.session_state.pop(key, None)


def _reset_quality() -> None:
    for key in ("quality", "quality_approved"):
        st.session_state.pop(key, None)
    for key in [k for k in st.session_state if str(k).startswith("ack_")]:
        st.session_state.pop(key, None)
    _reset_mapping()


def get_dataset() -> LoadedDataset | None:
    return st.session_state.get("dataset")


def set_dataset(ds: LoadedDataset) -> None:
    st.session_state["dataset"] = ds
    _reset_quality()


def clear_dataset() -> None:
    st.session_state.pop("dataset", None)
    _reset_quality()


def get_quality() -> QualityResult | None:
    return st.session_state.get("quality")


def set_quality(result: QualityResult) -> None:
    _reset_mapping()
    st.session_state["quality"] = result
    st.session_state["quality_approved"] = False


def is_quality_approved() -> bool:
    return bool(st.session_state.get("quality_approved"))


def set_quality_approved(value: bool) -> None:
    st.session_state["quality_approved"] = value


def get_working_dataframe():
    """The cleaned data, available only after the user approves it."""
    result = get_quality()
    if result is not None and is_quality_approved():
        return result.cleaned
    return None


def get_event_log() -> EventLog | None:
    return st.session_state.get("event_log")


def set_event_log(log: EventLog, assignments: dict) -> None:
    st.session_state["event_log"] = log
    st.session_state["mapping_confirmed"] = dict(assignments)


def get_confirmed_mapping() -> dict | None:
    return st.session_state.get("mapping_confirmed")