"""Process Mapping tab: confirm which column plays which role, then build the event log."""
import pandas as pd
import streamlit as st

from engines.mapping.capabilities import assess_capabilities
from engines.mapping.detector import confidence_label, detect_mapping
from engines.mapping.event_log import build_event_log, validate_mapping
from engines.mapping.roles import ROLES
from services.session import (get_confirmed_mapping, get_event_log, get_working_dataframe,
                              set_event_log)
from ui.components.cards import callout, kpi_row

NONE = "(not mapped)"
_CONF_CSS = {"High": "b-metric", "Medium": "b-estimate", "Low": "b-hypo"}
_STATUS_TEXT = {"available": "Available", "limited": "Limited", "unavailable": "Not available"}


def _chip(text: str, css: str) -> str:
    return f'<span class="badge {css}">{text}</span>'


def _mapping_form(df, detected) -> dict[str, str | None]:
    st.caption("The system proposed these matches from column names and data patterns. "
               "Change any dropdown if a guess is wrong.")
    options = [NONE] + [str(c) for c in df.columns]
    head = st.columns([3, 3, 2, 5])
    for h, label in zip(head, ["Role", "Column", "Confidence", "Why"]):
        h.markdown(f"**{label}**")

    chosen: dict[str, str | None] = {}
    for role in ROLES:
        auto = detected.assignments[role.key]
        c1, c2, c3, c4 = st.columns([3, 3, 2, 5])
        c1.markdown(f"{role.label}{' *' if role.required else ''}", help=role.help)
        pick = c2.selectbox(role.label, options, key=f"map_{role.key}",
                            index=options.index(auto) if auto else 0, label_visibility="collapsed")
        value = None if pick == NONE else pick
        chosen[role.key] = value
        if value is None:
            c3.markdown(_chip("NOT MAPPED", "b-fact"), unsafe_allow_html=True)
            c4.caption("Required." if role.required else "Optional. Some analyses will be unavailable.")
        elif value == auto:
            level = confidence_label(detected.confidence[role.key])
            c3.markdown(_chip(f"{level.upper()} CONFIDENCE", _CONF_CSS[level]), unsafe_allow_html=True)
            c4.caption(detected.reasons[role.key].capitalize() + ".")
        else:
            c3.markdown(_chip("SET BY YOU", "b-ai"), unsafe_allow_html=True)
            c4.caption("Your selection overrides the automatic suggestion.")
    st.caption("* required")
    return chosen


def _results(log) -> None:
    span = f"{log.df['timestamp'].min():%d %b %Y} to {log.df['timestamp'].max():%d %b %Y}"
    kpi_row([
        {"label": "Cases", "value": f"{log.cases:,}", "badge": "fact", "caption": "Distinct process instances"},
        {"label": "Events", "value": f"{log.events:,}", "badge": "fact", "caption": "Rows in the event log"},
        {"label": "Distinct steps", "value": f"{log.activities}", "badge": "fact", "caption": "Different activities"},
        {"label": "Steps per case", "value": f"{log.events / log.cases:.1f}", "badge": "metric",
         "caption": f"Average. Period: {span}"},
    ])
    for label, n in log.dropped.items():
        callout("warning", "Rows excluded", f"{n:,} rows had no '{label}' and could not be used.")
    for note in log.notes:
        callout("warning", "Note", note)

    st.markdown("#### What this data can support")
    caps = assess_capabilities(log.mapping)
    rows = [{"Analysis": c.name, "Business question": c.question,
             "Status": _STATUS_TEXT[c.status], "Note": c.note} for c in caps]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption("Analyses marked Limited or Not available will say so on their own pages. "
               "Nothing is estimated from data that is not there.")

    with st.expander("Preview the event log"):
        st.dataframe(log.df.head(100), width="stretch", hide_index=True)
    st.download_button("Download event log (CSV)", log.df.to_csv(index=False).encode("utf-8"),
                       file_name="event_log.csv", mime="text/csv")


def render_process_mapping() -> None:
    df = get_working_dataframe()
    if df is None:
        callout("warning", "Approve the cleaned data first",
                "Process mapping runs on the cleaned data. Open the Data quality tab, review the results, "
                "and click Approve cleaned data and continue.")
        return

    detected = detect_mapping(df)
    chosen = _mapping_form(df, detected)
    errors, warnings = validate_mapping(df, chosen)
    for e in errors:
        st.error(e)
    for w in warnings:
        st.warning(w)

    confirmed = get_confirmed_mapping()
    current = {k: v for k, v in chosen.items() if v}
    if confirmed is not None and confirmed != current:
        callout("info", "Mapping changed", "Rebuild the event log to apply your changes.")

    label = "Rebuild event log" if confirmed is not None else "Confirm mapping and build event log"
    if st.button(label, type="primary", disabled=bool(errors)):
        set_event_log(build_event_log(df, chosen), current)
        st.rerun()

    log = get_event_log()
    if log is not None and confirmed == current:
        st.markdown("---")
        callout("success", "Event log ready",
                "The data is now in a standard structure. Every analysis in the next steps reads from it.")
        _results(log)