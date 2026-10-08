"""Workspace 2: Process Health. Baseline performance computed from the event log."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engines.metrics.process_metrics import compute_metrics
from models.mapping import EventLog
from models.metrics import ProcessMetrics
from services.session import get_event_log
from ui.components.cards import callout, kpi_row
from ui.theme import palette as p
from ui.theme.charts import style


@st.cache_data(show_spinner="Calculating process metrics...")
def _metrics(_log: EventLog, key: tuple) -> ProcessMetrics:
    return compute_metrics(_log)


def _key(log: EventLog) -> tuple:
    return (log.cases, log.events, tuple(sorted(log.mapping.items())),
            str(log.df["timestamp"].min()), str(log.df["timestamp"].max()))


def _dur(hours: float | None) -> str:
    if hours is None:
        return "n/a"
    return f"{hours:.1f} h" if hours < 48 else f"{hours / 24:.1f} d"


def _tone(value: float | None, good: float, warn: float, higher_is_better: bool) -> str:
    if value is None:
        return ""
    if higher_is_better:
        return "good" if value >= good else "warn" if value >= warn else "bad"
    return "good" if value <= good else "warn" if value <= warn else "bad"


def _kpis(k: dict) -> None:
    sla = k["sla_compliance"]
    kpi_row([
        {"label": "Average cycle time", "value": _dur(k["avg_cycle_h"]), "badge": "metric",
         "caption": f"Across {int(k['cases_analysed']):,} cases with valid timestamps"},
        {"label": "Median cycle time", "value": _dur(k["median_cycle_h"]), "badge": "metric",
         "caption": "A typical case. Half are faster, half slower"},
        {"label": "Slowest 10% take at least", "value": _dur(k["p90_cycle_h"]), "badge": "metric",
         "caption": f"{k['variation_ratio']:.1f}x the median" if k["variation_ratio"] else ""},
        {"label": "SLA compliance",
         "value": f"{sla:.1%}" if sla is not None else "Not available", "badge": "metric",
         "caption": f"Target: {_dur(k['sla_hours'])} end to end" if sla is not None else "No SLA column mapped",
         "tone": _tone(sla, 0.95, 0.85, True)},
    ])
    rw = k["rework_rate"]
    kpi_row([
        {"label": "Rework rate", "value": f"{rw:.1%}", "badge": "metric",
         "caption": "Cases that repeat at least one step", "tone": _tone(rw, 0.05, 0.15, False)},
        {"label": "First-time-right", "value": f"{k['first_time_right']:.1%}", "badge": "metric",
         "caption": "Cases completed without repeating a step",
         "tone": _tone(k["first_time_right"], 0.95, 0.85, True)},
        {"label": "Throughput", "value": f"{k['throughput_per_week']:,.0f} / wk" if k["throughput_per_week"] else "n/a",
         "badge": "metric", "caption": "Cases per week over the period"},
        {"label": "SLA breach rate",
         "value": f"{k['sla_breach_rate']:.1%}" if k["sla_breach_rate"] is not None else "Not available",
         "badge": "metric", "caption": "Cases slower than their target",
         "tone": _tone(k["sla_breach_rate"], 0.05, 0.15, False)},
    ])


def _time_tab(m: ProcessMetrics) -> None:
    s = m.steps
    top = s.iloc[0]
    wait_part = top["share_wait"] / top["share_of_time"] if top["share_of_time"] else 0
    callout("info", "Where the time goes",
            f"<b>{top['activity']}</b> accounts for <b>{top['share_of_time']:.0%}</b> of all elapsed step time"
            + (f", of which about {wait_part:.0%} is waiting." if not m.approximate else ".")
            + " This is a calculated finding. The Findings page examines why.")
    st.caption("Share of total elapsed time across all cases, split into time spent working and time spent waiting.")
    fig = go.Figure()
    fig.add_bar(y=s["activity"], x=s["share_processing"] * 100, name="Working", orientation="h",
                marker_color=p.INDIGO)
    fig.add_bar(y=s["activity"], x=s["share_wait"] * 100, name="Waiting for the step to start", orientation="h",
                marker_color=p.CYAN)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="% of total elapsed time", ticksuffix="%")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 320), width="stretch")

    table = pd.DataFrame({
        "Step": s["activity"], "Times performed": s["occurrences"],
        "Avg working (h)": s["avg_processing_h"].round(1), "Avg waiting (h)": s["avg_wait_h"].round(1),
        "Share of total time": s["share_of_time"] * 100,
    })
    st.dataframe(table, width="stretch", hide_index=True, column_config={
        "Share of total time": st.column_config.ProgressColumn(
            "Share of total time", min_value=0, max_value=100, format="%.1f%%")})
    if m.approximate:
        st.warning("Approximate: without an end time, working time cannot be measured separately.")


def _duration_tab(m: ProcessMetrics) -> None:
    c = m.cases[m.cases["valid"]]
    st.caption("How long cases take from first step to last. Cases to the right of the dashed line breached the SLA.")
    fig = go.Figure(go.Histogram(x=c["cycle_h"] / 24, nbinsx=40, marker_color=p.INDIGO,
                                 hovertemplate="%{x:.1f} days: %{y} cases<extra></extra>"))
    sla_h = m.kpis.get("sla_hours")
    if sla_h:
        fig.add_vline(x=sla_h / 24, line_dash="dash", line_color=p.CORAL,
                      annotation_text="SLA target", annotation_position="top")
    fig.update_xaxes(title="Cycle time (days)")
    fig.update_yaxes(title="Number of cases")
    st.plotly_chart(style(fig, 340), width="stretch")


def _variants_tab(m: ProcessMetrics) -> None:
    st.caption("Different cases follow different paths. Each row is one distinct sequence of steps.")
    v = m.variants
    table = pd.DataFrame({"Path": v["path"], "Cases": v["cases"], "Share of cases": v["share"] * 100,
                          "Avg cycle time (days)": (v["avg_cycle_h"] / 24).round(1)})
    st.dataframe(table, width="stretch", hide_index=True, column_config={
        "Share of cases": st.column_config.ProgressColumn("Share of cases", min_value=0, max_value=100,
                                                          format="%.1f%%")})


def render_process_health() -> None:
    log = get_event_log()
    if log is None:
        callout("warning", "Complete Data Intake first",
                "Process health is calculated from the event log. Upload data, approve the cleaned version, "
                "and confirm the process mapping to continue.")
        return

    m = _metrics(log, _key(log))
    for note in m.notes:
        callout("warning", "Data note", note)
    _kpis(m.kpis)

    t1, t2, t3 = st.tabs(["Where time goes", "Case duration", "Process paths"])
    with t1:
        _time_tab(m)
    with t2:
        _duration_tab(m)
    with t3:
        _variants_tab(m)

    with st.expander("How was this calculated?"):
        st.caption("Every number on this page is computed directly from your event log. No AI is involved.")
        for name, formula, cols in m.methods:
            st.markdown(f"**{name}**  \n{formula}  \n*Columns used: {cols}*")