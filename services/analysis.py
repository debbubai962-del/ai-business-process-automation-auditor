"""Cached analysis results shared by several pages."""
import streamlit as st

from engines.automation.signals import compute_signals
from engines.bottlenecks.detector import detect_bottlenecks
from engines.impact.simulator import Prep, prepare
from models.automation import AutomationReport
from models.mapping import EventLog
from services.keys import log_key


@st.cache_data(show_spinner="Measuring automation potential...")
def _automation(_log: EventLog, key: tuple) -> AutomationReport:
    return compute_signals(_log, detect_bottlenecks(_log).table)


@st.cache_data(show_spinner=False)
def _prep(_log: EventLog, key: tuple) -> Prep:
    return prepare(_log)


def get_automation(log: EventLog) -> AutomationReport:
    return _automation(log, log_key(log))


def get_prep(log: EventLog) -> Prep:
    return _prep(log, log_key(log))