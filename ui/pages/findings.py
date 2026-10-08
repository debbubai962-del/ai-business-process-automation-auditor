"""Workspace 3: Findings. Bottlenecks (where) and root causes (why)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engines.bottlenecks.detector import (FREQUENT_SHARE, NONE, OCCASIONAL, PRIMARY,
                                          detect_bottlenecks)
from engines.root_cause.analysis import FACTOR_LABELS, analyse, fmt_hours, heatmap_table
from models.findings import BottleneckReport, RootCauseReport
from models.mapping import EventLog
from services.keys import log_key
from services.session import get_event_log
from ui.components.badges import badge_html
from ui.components.cards import callout
from ui.components.html import render
from ui.theme import palette as p
from ui.theme.charts import style

WHOLE_CASE = "Whole-case cycle time"
_CLASS_COLOR = {PRIMARY: p.CORAL, OCCASIONAL: p.AMBER, "Frequent delay": p.INDIGO, NONE: "#94A3B8"}
_STRENGTH_COLOR = {"strong": p.INDIGO, "moderate": p.BLUE, "small": p.CYAN, "negligible": "#CBD5E1"}


@st.cache_data(show_spinner="Detecting bottlenecks...")
def _bottlenecks(_log: EventLog, key: tuple) -> BottleneckReport:
    return detect_bottlenecks(_log)


@st.cache_data(show_spinner="Analysing root causes...")
def _root_causes(_log: EventLog, key: tuple, step: str | None) -> RootCauseReport:
    return analyse(_log, step)


def _pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x:.0%}"


# ---------------------------------------------------------------- bottlenecks
def _summary(t: pd.DataFrame) -> None:
    prim = t[t["classification"] == PRIMARY]
    for _, r in prim.iterrows():
        sla = f" It is the longest step in {_pct(r['sla_attribution'])} of the cases that breached their SLA." \
            if pd.notna(r["sla_attribution"]) else ""
        callout("critical", f"Primary bottleneck: {r['activity']}",
                f"It is the longest step in <b>{_pct(r['dominant_pct'])}</b> of cases, takes "
                f"<b>{fmt_hours(r['avg_elapsed_h'])}</b> on average, and makes up <b>{_pct(r['share_of_time'])}</b> "
                f"of all elapsed step time.{sla}")
    for _, r in t[t["classification"] == OCCASIONAL].iterrows():
        callout("warning", f"Occasional severe delay: {r['activity']}",
                f"Only <b>{_pct(r['reach'])}</b> of cases reach this step, but each occurrence takes "
                f"<b>{fmt_hours(r['avg_elapsed_h'])}</b> on average. Rare, but costly when it happens.")
    for _, r in t[t["classification"] == "Frequent delay"].iterrows():
        callout("info", f"Frequent delay: {r['activity']}",
                f"It is the longest step in {_pct(r['dominant_pct'])} of cases, although each delay is moderate "
                f"({fmt_hours(r['avg_elapsed_h'])} on average).")
    if prim.empty and t[t["classification"] != NONE].empty:
        callout("success", "No clear bottleneck", "No step stands out as unusually slow or frequently the longest step.")


def _matrix(rep: BottleneckReport) -> None:
    t = rep.table
    st.caption("Each bubble is a step. Right = it is the longest step in more cases (frequency). Higher = each "
               "occurrence takes longer (severity). Bubble size = share of all time spent.")
    fig = go.Figure()
    for cls, grp in t.groupby("classification"):
        fig.add_trace(go.Scatter(
            x=grp["dominant_pct"] * 100, y=grp["avg_elapsed_h"], mode="markers+text", name=cls,
            text=grp["activity"], textposition="top center",
            marker=dict(size=(grp["share_of_time"] ** 0.5) * 70 + 14, color=_CLASS_COLOR.get(cls, "#94A3B8"),
                        opacity=0.85, line=dict(color="white", width=1)),
            hovertemplate="<b>%{text}</b><br>Longest step in %{x:.0f}% of cases<br>"
                          "Avg time at step %{y:.1f} h<extra></extra>"))
    fig.add_vline(x=FREQUENT_SHARE * 100, line_dash="dot", line_color=p.MUTED)
    fig.add_hline(y=rep.severity_threshold_h, line_dash="dot", line_color=p.MUTED,
                  annotation_text="severity threshold", annotation_position="bottom right")
    fig.update_xaxes(title="Frequency: % of cases where this is the longest step", range=[-8, 112], ticksuffix="%")
    fig.update_yaxes(title="Severity: avg hours at step (log scale)", type="log")
    st.plotly_chart(style(fig, 400), width="stretch")


def _register(t: pd.DataFrame) -> None:
    table = pd.DataFrame({
        "Step": t["activity"], "Classification": t["classification"],
        "Avg time at step": t["avg_elapsed_h"].map(fmt_hours),
        "Cases reaching step": t["reach"] * 100,
        "Longest step in": t["dominant_pct"] * 100,
        "Share of SLA breaches": t["sla_attribution"] * 100,
        "Share of total time": t["share_of_time"] * 100,
        "Confidence": t["confidence"],
    })
    bar = lambda label: st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.0f%%")
    st.dataframe(table, width="stretch", hide_index=True, column_config={
        "Cases reaching step": bar("Cases reaching step"), "Longest step in": bar("Longest step in"),
        "Share of SLA breaches": bar("Share of SLA breaches"), "Share of total time": bar("Share of total time")})


def _details(t: pd.DataFrame) -> None:
    flagged = t[t["classification"] != NONE]
    if flagged.empty:
        return
    st.markdown("#### Evidence for each bottleneck")
    for _, r in flagged.iterrows():
        with st.expander(f"{r['activity']}   |   {r['classification']}   |   confidence: {r['confidence']}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Average time at step", fmt_hours(r["avg_elapsed_h"]))
            c2.metric("Cases reaching step", _pct(r["reach"]))
            c3.metric("Share of SLA breaches", _pct(r["sla_attribution"]))
            c1.metric("Times performed", f"{int(r['occurrences']):,}")
            c2.metric("Occurrences over 2x typical", _pct(r["spike_pct"]))
            c3.metric("Share of total time", _pct(r["share_of_time"]))
            render(badge_html("metric"))
            st.markdown("**Likely cause**")
            render(badge_html("inference"))
            st.write(r["likely_cause"])
            st.caption("This explanation comes from transparent rules applied to the measurements above. "
                       "It is not proven. Confirm it with the process owner. The Root causes tab tests which "
                       "factors actually explain the delay.")


def _bottleneck_tab(log: EventLog) -> None:
    rep = _bottlenecks(log, log_key(log))
    t = rep.table
    if rep.approximate:
        callout("warning", "Approximate delays", rep.notes[0])
    _summary(t)
    _matrix(rep)
    st.markdown("#### Bottleneck register")
    _register(t)
    _details(t)
    with st.expander("How was this calculated?"):
        for n in rep.notes:
            st.write(n)
        st.markdown(
            "**Time at step** = waiting before the step starts + working time at the step.  \n"
            "**Longest step in** = share of cases in which this step has the largest time at step.  \n"
            "**Share of SLA breaches** = among cases that breached their SLA, the share where this step was the longest.  \n"
            "**Classification** = frequency (longest step in at least 20% of cases) combined with severity "
            "(average time at least 3x the typical step).  \n"
            "**Confidence** = High with 100 or more measured occurrences, Medium with 30 or more, otherwise Low.")


# ---------------------------------------------------------------- root causes
def _factor_chart(rep: RootCauseReport) -> None:
    rs = rep.results
    fig = go.Figure(go.Bar(
        y=[r.label for r in rs], x=[r.effect * 100 for r in rs], orientation="h",
        marker_color=[_STRENGTH_COLOR[r.strength] for r in rs],
        text=[f"{r.strength}" + ("" if r.significant else ", not significant") for r in rs],
        textposition="outside",
        hovertemplate="%{y}: explains %{x:.1f}% of the variation<extra></extra>"))
    fig.update_xaxes(title="Share of the variation in delay that this factor explains", ticksuffix="%")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 60 + 38 * len(rs)), width="stretch")


def _factor_cards(rep: RootCauseReport) -> None:
    meaningful = [r for r in rep.results if r.significant and r.strength != "negligible"]
    quiet = [r for r in rep.results if r not in meaningful]
    st.markdown("#### What the evidence shows")
    if not meaningful:
        callout("info", "No factor stands out", "None of the tested factors explains a meaningful share of the delay.")
    for r in meaningful:
        with st.expander(f"{r.label}   |   {r.strength} effect   |   explains {r.effect:.0%} of the variation"):
            st.markdown("**Observed**")
            render(badge_html("metric"))
            st.write(r.statement)
            g = r.groups.assign(mean=lambda d: d["mean_h"].round(1), median=lambda d: d["median_h"].round(1))
            st.dataframe(g[["segment", "cases", "mean", "median"]].rename(columns={
                "segment": "Group", "cases": "Cases", "mean": "Average (h)", "median": "Median (h)"}),
                width="stretch", hide_index=True)
            if r.hypothesis:
                st.markdown("**Possible explanation**")
                render(badge_html("inference"))
                st.write(r.hypothesis)
                st.caption("Not proven. A statistical difference shows that groups differ, not why.")
    if quiet:
        with st.expander(f"Factors with no meaningful effect ({len(quiet)})"):
            st.caption("Ruling factors out is a finding too. These do not explain the delay.")
            st.dataframe(pd.DataFrame({
                "Factor": [r.label for r in quiet], "Effect": [f"{r.effect:.1%}" for r in quiet],
                "Verdict": [("Not significant" if not r.significant else "Negligible") for r in quiet],
            }), width="stretch", hide_index=True)


def _drilldown(rep: RootCauseReport) -> None:
    keys = [r.key for r in rep.results]
    if len(keys) < 2:
        return
    st.markdown("#### Drill down: where do two factors combine?")
    st.caption("Average hours for every combination. Combinations with fewer than 15 cases are left blank.")
    default_a = keys[0] if keys[0] != "resource" else keys[1]
    a_idx = keys.index("department") if "department" in keys else keys.index(default_a)
    b_idx = keys.index("weekday") if "weekday" in keys else (1 if a_idx == 0 else 0)
    c1, c2 = st.columns(2)
    a = c1.selectbox("Rows", keys, index=a_idx, format_func=FACTOR_LABELS.get, key="rc_row")
    b = c2.selectbox("Columns", keys, index=b_idx, format_func=FACTOR_LABELS.get, key="rc_col")
    if a == b:
        st.info("Choose two different factors.")
        return
    mean, count = heatmap_table(rep.frame, a, b)
    fig = go.Figure(go.Heatmap(
        z=mean.values, x=[str(c) for c in mean.columns], y=[str(i) for i in mean.index],
        colorscale=[[0, "#FFFFFF"], [1, p.INDIGO]], colorbar=dict(title="Avg hours"),
        text=[[("" if pd.isna(v) else f"{v:.0f}") for v in row] for row in mean.values],
        texttemplate="%{text}", customdata=count.values,
        hovertemplate="%{y} / %{x}<br>Avg %{z:.1f} h<br>%{customdata:.0f} cases<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 120 + 48 * len(mean.index)), width="stretch")


def _root_cause_tab(log: EventLog) -> None:
    bn = _bottlenecks(log, log_key(log)).table
    steps = list(bn["activity"])
    options = [WHOLE_CASE] + steps
    prim = bn[bn["classification"] == PRIMARY]["activity"]
    default = options.index(prim.iloc[0]) if len(prim) else 0
    pick = st.selectbox("What do you want to explain?", options, index=default, key="rc_outcome",
                        help="Choose the whole case, or the time cases spend at one step.")
    rep = _root_causes(log, log_key(log), None if pick == WHOLE_CASE else pick)

    st.caption(f"Explaining: **{rep.outcome_label}**. Average {fmt_hours(rep.mean_h)} across {rep.n:,} cases "
               f"with valid timestamps.")
    for n in rep.notes:
        callout("info", "Note", n)
    if not rep.results:
        callout("warning", "Not enough data", "No factor had enough cases in at least two groups to be compared.")
        return

    top = rep.results[0]
    if top.significant and top.strength != "negligible":
        callout("info", f"Strongest factor: {top.label}",
                f"It explains about <b>{top.effect:.0%}</b> of the differences in delay ({top.strength} effect). "
                f"{top.statement}")
    _factor_chart(rep)
    _factor_cards(rep)
    _drilldown(rep)

    with st.expander("How was this calculated?"):
        st.markdown(
            f"Each factor is tested on its own against the outcome using a **Kruskal-Wallis test**, which does not "
            f"assume delay times follow a bell curve.  \n"
            f"**Effect size** (epsilon-squared) is the share of the variation in delay that the factor accounts for: "
            f"under 1% negligible, under 6% small, under 14% moderate, above that strong.  \n"
            f"**Significance** uses a stricter threshold (p < {rep.alpha:.4f}) because several factors are tested at "
            f"once, which prevents false alarms.  \n"
            f"Groups with fewer than 20 cases are ignored. Only cases with valid timestamps are used.  \n"
            f"**Limits:** factors are tested one at a time and can overlap. Statistics show that groups differ, "
            f"not why. Possible explanations are rule-based hypotheses to be confirmed with the process owner.")


def render_findings() -> None:
    log = get_event_log()
    if log is None:
        callout("warning", "Complete Data Intake first",
                "Findings are calculated from the event log. Upload data, approve the cleaned version, and "
                "confirm the process mapping to continue.")
        return
    t1, t2 = st.tabs(["Bottlenecks: where", "Root causes: why"])
    with t1:
        _bottleneck_tab(log)
    with t2:
        _root_cause_tab(log)