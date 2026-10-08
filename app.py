import streamlit as st

from config.settings import get_settings
from services.session import get_event_log
from ui.components.cards import sidebar_brand, status_chip
from ui.components.stepper import render_stepper
from ui.pages.workspaces import WORKSPACES, render_workspace
from ui.theme.styles import inject_css

settings = get_settings()

st.set_page_config(
    page_title=settings.app_name,
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

NAV_LABELS = [f"{i + 1}   {w['title']}" for i, w in enumerate(WORKSPACES)]

if "nav_index" not in st.session_state:
    st.session_state.nav_index = 0


def nav_button(i: int, label: str) -> None:
    active = st.session_state.nav_index == i
    if st.button(label, key=f"nav_{i}", type="primary" if active else "secondary", width="stretch"):
        st.session_state.nav_index = i
        st.rerun()


event_log = get_event_log()

with st.sidebar:
    sidebar_brand()
    st.markdown('<div class="nav-caption">WORKFLOW</div>', unsafe_allow_html=True)
    for i, label in enumerate(NAV_LABELS):
        nav_button(i, label)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="nav-caption">SYSTEM</div>', unsafe_allow_html=True)
    if settings.ai_enabled:
        status_chip("AI layer connected", ok=True)
    else:
        status_chip("No-AI mode", ok=False)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    if event_log is not None:
        status_chip(f"Event log ready: {event_log.cases:,} cases", ok=True)
    else:
        status_chip("No event log yet", ok=False)

index = min(st.session_state.nav_index, len(WORKSPACES) - 1)
render_stepper([w["title"] for w in WORKSPACES], current=index,
               completed={0} if event_log is not None else set())
render_workspace(WORKSPACES[index])