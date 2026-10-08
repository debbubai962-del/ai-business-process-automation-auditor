"""Workspace 4: Automation. Opportunity engine (what to automate) and impact simulator (what it is worth)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.automation import (AUTOMATION_TYPES, DEFAULT_HOURLY_COST, DEFAULT_WEIGHTS, NO_AUTOMATION,
                               RUNNING_COST_PCT, WEIGHT_LABELS)
from engines.automation.scoring import breakdown, score_opportunities
from engines.impact.simulator import sensitivity, simulate
from engines.root_cause.analysis import fmt_hours
from models.automation import Globals, StepInput
from models.mapping import EventLog
from services.analysis import get_automation, get_prep
from services.session import get_event_log
from ui.components.badges import badge_html
from ui.components.cards import callout, kpi_row
from ui.components.html import render
from ui.theme import palette as p
from ui.theme.charts import style

_QUAD_COLOR = {"Quick win": p.EMERALD, "Strategic project": p.INDIGO, "Fill-in": p.CYAN,
               "Reconsider": p.AMBER, "Not recommended": "#94A3B8"}


# ---------------------------------------------------------------- weights
def _reset_weights() -> None:
    for k, v in DEFAULT_WEIGHTS.items():
        st.session_state[f"w_{k}"] = int(round(v * 100))


def _weights() -> dict[str, float]:
    for k, v in DEFAULT_WEIGHTS.items():
        st.session_state.setdefault(f"w_{k}", int(round(v * 100)))
    with st.expander("Adjust the scoring weights"):
        st.caption("Priority = weighted benefits minus weighted costs. Change what matters most to your "
                   "organisation and the ranking updates immediately.")
        cols = st.columns(3)
        for i, k in enumerate(DEFAULT_WEIGHTS):
            cols[i % 3].slider(WEIGHT_LABELS[k], 0, 100, key=f"w_{k}")
        st.button("Reset to defaults", on_click=_reset_weights)
    return {k: st.session_state[f"w_{k}"] / 100 for k in DEFAULT_WEIGHTS}


# ---------------------------------------------------------------- opportunities
def _summary(t: pd.DataFrame) -> None:
    ranked = t[t["rank"].notna()].head(3)
    if ranked.empty:
        callout("info", "No automation candidates", "No step looks suitable for automation on this data.")
        return
    lines = "".join(f"<li><b>{r['activity']}</b>: {r['recommended']} ({r['quadrant'].lower()}, "
                    f"priority {r['priority']:.0f}/100)</li>" for _, r in ranked.iterrows())
    callout("info", "Highest-priority opportunities", f"<ul style='margin:6px 0 0 18px'>{lines}</ul>")
    for _, r in t[t["recommended"] == NO_AUTOMATION].iterrows():
        callout("warning", f"Not recommended for automation: {r['activity']}", r["rec_reason"])


def _matrix(t: pd.DataFrame) -> None:
    st.caption("Right = harder and riskier to implement. Higher = more valuable. Bubble size = estimated hours "
               "saved per month. The best opportunities sit top-left.")
    fig = go.Figure()
    for quad, g in t.groupby("quadrant"):
        size = np.sqrt(g["hours_saved_month"].clip(lower=0)) * 1.6 + 16
        fig.add_trace(go.Scatter(
            x=g["difficulty"], y=g["value"], mode="markers+text", name=quad, text=g["activity"],
            textposition="top center",
            marker=dict(size=size, color=_QUAD_COLOR.get(quad, "#94A3B8"), opacity=0.85,
                        line=dict(color="white", width=1)),
            customdata=np.stack([g["recommended"], g["priority"], g["hours_saved_month"]], axis=1),
            hovertemplate="<b>%{text}</b><br>%{customdata[0]}<br>Priority %{customdata[1]:.0f}/100<br>"
                          "About %{customdata[2]:,.0f} h saved / month<extra></extra>"))
    fig.add_vline(x=50, line_dash="dot", line_color=p.MUTED)
    fig.add_hline(y=50, line_dash="dot", line_color=p.MUTED)
    for x, y, text in [(2, 98, "QUICK WINS"), (98, 98, "STRATEGIC PROJECTS"), (2, 2, "FILL-INS"), (98, 2, "RECONSIDER")]:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, font=dict(size=11, color=p.MUTED),
                           xanchor="left" if x < 50 else "right", yanchor="top" if y > 50 else "bottom")
    fig.update_xaxes(title="Difficulty: implementation complexity and risk", range=[0, 100])
    fig.update_yaxes(title="Value: impact, suitability, frequency, time saved", range=[0, 100])
    st.plotly_chart(style(fig, 440), width="stretch")


def _register(t: pd.DataFrame) -> None:
    table = pd.DataFrame({
        "Rank": t["rank"].map(lambda r: "-" if pd.isna(r) else f"{int(r)}"),
        "Step": t["activity"], "Recommended": t["recommended"], "Priority": t["priority"],
        "Quadrant": t["quadrant"], "Complexity": t["complexity_band"],
        "Per month": t["monthly_volume"].round(0), "Exception rate": t["exception_rate"] * 100,
        "Rule-based": t["rule_based"] * 100, "Est. hours saved / month": t["hours_saved_month"].round(0),
        "Confidence": t["confidence"],
    })
    pct = lambda label: st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.0f%%")
    st.dataframe(table, width="stretch", hide_index=True, column_config={
        "Priority": st.column_config.ProgressColumn("Priority (0-100)", min_value=0, max_value=100, format="%.0f"),
        "Exception rate": pct("Exception rate"), "Rule-based": pct("Rule-based"),
        "Per month": st.column_config.NumberColumn("Times / month", format="%d")})


def _details(t: pd.DataFrame, weights: dict[str, float]) -> None:
    st.markdown("#### Why each recommendation, and how the score was built")
    for _, r in t.iterrows():
        label = f"{r['activity']}   |   {r['recommended']}   |   priority {r['priority']:.0f}/100"
        with st.expander(label):
            st.markdown("**Recommendation**")
            render(badge_html("inference"))
            st.write(f"{r['rec_reason']} {AUTOMATION_TYPES[r['recommended']][3]}")

            st.markdown("**What the data shows**")
            render(badge_html("metric"))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Times per month", f"{r['monthly_volume']:,.0f}")
            c2.metric("Same next step", f"{r['predictability']:.0%}")
            c3.metric("Duration variation", f"{r['cv_proc']:.0%}")
            c4.metric("Exception rate", f"{r['exception_rate']:.0%}")
            flags = []
            if r["control"]:
                flags.append("The step name suggests a control or judgement activity (approval, review).")
            if r["conditional"]:
                flags.append(f"Only {r['reach']:.0%} of cases reach this step, so it is conditional.")
            if r["judgment_likely"]:
                flags.append("Duration varies a lot between cases, which suggests human judgement.")
            for f in flags:
                st.caption(f)

            st.markdown("**How the priority score was calculated**")
            bd, baseline = breakdown(r, weights)
            st.dataframe(bd.round(1), width="stretch", hide_index=True, column_config={
                "Weight": st.column_config.NumberColumn("Weight (%)", format="%.0f"),
                "Contribution": st.column_config.NumberColumn("Points added / removed", format="%+.1f")})
            st.caption(f"Priority {r['priority']:.1f} = starting point {baseline:.1f} (so the worst possible "
                       f"opportunity scores 0) + the contributions above.")
            if r["hours_saved_month"] > 0:
                render(badge_html("estimate"))
                st.caption(f"Estimated saving: about {r['hours_saved_month']:,.0f} hours per month using default "
                           f"assumptions ({AUTOMATION_TYPES[r['recommended']][0]:.0%} reduction of "
                           f"{r['handson_min']:.0f} hands-on minutes per occurrence). Adjust them in the simulator.")


def _opportunities_tab(log: EventLog) -> None:
    rep = get_automation(log)
    weights = _weights()
    t = score_opportunities(rep.signals, weights)
    if rep.approximate:
        callout("warning", "Limited measurements", rep.notes[0])
    _summary(t)
    _matrix(t)
    st.markdown("#### Opportunity register")
    _register(t)
    _details(t, weights)
    with st.expander("How was this calculated?"):
        st.markdown(
            "**Priority** = weighted sum of Business impact + Automation suitability + Frequency + Potential time "
            "saving, minus weighted Implementation complexity and Risk, rescaled so 0 is the worst possible "
            "opportunity and 100 the best. Weights are editable above.  \n"
            "**Suitability** blends standardisation (is the next step predictable and the duration consistent), "
            "volume, low exception rate, and low case-by-case variability.  \n"
            "**Exception rate** = share of occurrences that repeat a step already done in that case, or take over "
            "twice the step's typical time.  \n"
            "**Risk** rises for control steps (approval, review), highly variable steps, and frequent exceptions.  \n"
            "**Complexity** combines the difficulty of the recommended automation type with how unpredictable "
            "the step is.  \n"
            "**Recommended type** comes from a fixed decision table. It never recommends automation simply "
            "because a step is slow: judgement-heavy, low-volume and non-standard steps are screened out.  \n"
            "**Limits:** these are measurements from timestamps, not a process walkthrough. Confirm with the "
            "people who do the work before committing budget.")
        for n in rep.notes:
            st.caption(n)


# ---------------------------------------------------------------- simulator
def _money(v: float, cur: str) -> str:
    return f"{cur}{v:,.0f}"


def _defaults(t: pd.DataFrame) -> pd.DataFrame:
    top = set(t[t["rank"].notna() & (t["rank"] <= 3)]["activity"])
    return pd.DataFrame({
        "Include": t["activity"].isin(top),
        "Step": t["activity"],
        "Automation type": t["recommended"],
        "Hands-on min per item": t["handson_min"].fillna(0.0).round(1),
        "Time reduction %": (t["reduction"] * 100).round(0),
        "Implementation cost": t["impl_cost_default"].astype(float),
    })


def _simulator_tab(log: EventLog) -> None:
    rep = get_automation(log)
    prep = get_prep(log)
    t = score_opportunities(rep.signals)   # default weights: the starting scenario

    callout("warning", "Estimates, not forecasts",
            "Everything on this tab is a <b>business estimate</b> driven by the assumptions below, which you can "
            "change. Savings are only realised if the automation performs as assumed. Validate with the process "
            "owner and finance before committing budget.")

    st.markdown("#### 1. Your assumptions")
    c1, c2, c3, c4 = st.columns(4)
    cur = c1.text_input("Currency symbol", "$", max_chars=3)
    hourly = c2.number_input("Employee hourly cost", min_value=0.0, value=float(DEFAULT_HOURLY_COST), step=1.0,
                             help="Fully loaded cost of one working hour.")
    volume = c3.number_input("Cases per month", min_value=1.0, value=float(round(rep.monthly_cases)), step=10.0,
                             help="Defaults to the monthly average in your data. Change it to model growth.")
    running = c4.number_input("Yearly running cost (% of build)", min_value=0.0, max_value=100.0,
                              value=RUNNING_COST_PCT * 100, step=1.0,
                              help="Licences, maintenance and support, as a share of the one-off cost.")

    st.markdown("#### 2. Choose and tune the opportunities")
    st.caption("Tick the opportunities to include and edit the numbers. Defaults are conservative: hands-on time "
               "is 25% of the recorded step duration (maximum 30 minutes).")
    if rep.approximate:
        st.warning("No end time is mapped, so hands-on minutes could not be measured. Enter them yourself.")
    edited = st.data_editor(
        _defaults(t), key=f"sim_editor_{hash(rep.signals['activity'].tolist().__str__())}", hide_index=True,
        width="stretch", disabled=["Step", "Automation type"],
        column_config={
            "Include": st.column_config.CheckboxColumn("Include"),
            "Hands-on min per item": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f"),
            "Time reduction %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=5.0, format="%.0f"),
            "Implementation cost": st.column_config.NumberColumn(min_value=0.0, step=1000.0, format="%.0f"),
        })

    waiting = dict(zip(t["activity"], t["waiting"]))
    steps = [StepInput(r["Step"], bool(r["Include"]), float(r["Hands-on min per item"]),
                       float(r["Time reduction %"]) / 100, float(r["Implementation cost"]), bool(waiting[r["Step"]]))
             for _, r in edited.iterrows()]
    if not any(s.include for s in steps):
        st.info("Tick at least one opportunity to see the estimated impact.")
        return

    g = Globals(hourly, volume, running / 100, cur)
    res = simulate(prep, steps, g)
    st.session_state.scenario_inputs = (g, steps)

    st.markdown("#### 3. Estimated impact")
    kpi_row([
        {"label": "Hours saved per month", "value": f"{res.hours_saved_month:,.0f}", "badge": "estimate",
         "caption": f"About {res.hours_saved_month / 160:.1f} full-time equivalents"},
        {"label": "Net saving per year", "value": _money(res.net_year, cur), "badge": "estimate",
         "caption": f"After {_money(res.running_year, cur)} yearly running cost", "tone": "good" if res.net_year > 0 else "bad"},
        {"label": "Payback period",
         "value": f"{res.payback_months:.1f} months" if res.payback_months is not None else "Never",
         "badge": "estimate", "caption": f"One-off cost {_money(res.impl_cost, cur)}",
         "tone": "good" if res.payback_months is not None and res.payback_months <= 12 else "warn"},
        {"label": "3-year net value", "value": _money(res.net_3y, cur), "badge": "estimate",
         "caption": "Three years of net saving minus build cost", "tone": "good" if res.net_3y > 0 else "bad"},
    ])

    st.markdown("#### Current state vs improved state")
    cu, im = res.current, res.improved
    rows = [
        ("Average cycle time", fmt_hours(cu["avg_cycle_h"]), fmt_hours(im["avg_cycle_h"]),
         f"{(im['avg_cycle_h'] / cu['avg_cycle_h'] - 1):+.0%}"),
        ("Slowest 10% of cases", fmt_hours(cu["p90_cycle_h"]), fmt_hours(im["p90_cycle_h"]),
         f"{(im['p90_cycle_h'] / cu['p90_cycle_h'] - 1):+.0%}"),
    ]
    if "sla_compliance" in cu:
        rows.append(("SLA compliance", f"{cu['sla_compliance']:.1%}", f"{im['sla_compliance']:.1%}",
                     f"{(im['sla_compliance'] - cu['sla_compliance']) * 100:+.1f} pts"))
    rows += [
        ("Hands-on hours per month (selected steps)", f"{cu['handson_h_month']:,.0f}", f"{im['handson_h_month']:,.0f}",
         f"{(im['handson_h_month'] / cu['handson_h_month'] - 1):+.0%}" if cu["handson_h_month"] else "n/a"),
        ("Labour cost per month (selected steps)", _money(cu["labour_cost_month"], cur),
         _money(im["labour_cost_month"], cur), _money(im["labour_cost_month"] - cu["labour_cost_month"], cur)),
    ]
    left, right = st.columns([3, 2], gap="large")
    left.dataframe(pd.DataFrame(rows, columns=["Measure", "Current", "Improved", "Change"]),
                   width="stretch", hide_index=True)
    fig = go.Figure()
    fig.add_bar(name="Current", x=["Average", "Slowest 10%"], y=[cu["avg_cycle_h"] / 24, cu["p90_cycle_h"] / 24],
                marker_color="#94A3B8")
    fig.add_bar(name="Improved", x=["Average", "Slowest 10%"], y=[im["avg_cycle_h"] / 24, im["p90_cycle_h"] / 24],
                marker_color=p.EMERALD)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Cycle time (days)")
    right.plotly_chart(style(fig, 260), width="stretch")
    st.caption("Cycle-time and SLA figures re-run your real cases with the selected improvements applied to each "
               "one. They are estimates: they assume the assumed reductions are achieved.")

    st.markdown("#### How sensitive is this?")
    st.caption("What happens if the automation delivers less (or more) than assumed.")
    sens = sensitivity(prep, steps, g)
    st.dataframe(pd.DataFrame({
        "Reduction achieved vs assumed": sens["Achieved vs assumed"],
        "Hours saved / month": sens["Hours saved / month"].round(0),
        "Net saving / year": sens["Net saving / year"].map(lambda v: _money(v, cur)),
        "Payback (months)": sens["Payback (months)"].map(lambda v: "Never" if pd.isna(v) else f"{v:.1f}"),
    }), width="stretch", hide_index=True)

    with st.expander("Per-step results and method"):
        per = res.per_step
        st.dataframe(per.round(1), width="stretch", hide_index=True)
        st.download_button("Download scenario (CSV)", per.round(2).to_csv(index=False).encode("utf-8"),
                           file_name="automation_scenario.csv", mime="text/csv")
        st.markdown(
            "**Hours saved** = occurrences per month x hands-on minutes per item / 60 x time reduction.  \n"
            "**Saving** = hours saved x hourly cost.  **Net yearly saving** = 12 x monthly saving minus yearly "
            "running cost.  \n**Payback** = one-off cost / (monthly saving minus monthly running cost).  \n"
            "**Cycle time and SLA** are recalculated per case: each included step's working time (or working plus "
            "waiting time for workflow and redesign changes) is reduced by the assumed percentage.  \n"
            "Occurrences scale with the cases per month you enter.")


def render_automation() -> None:
    log = get_event_log()
    if log is None:
        callout("warning", "Complete Data Intake first",
                "Automation analysis is calculated from the event log. Upload data, approve the cleaned "
                "version, and confirm the process mapping to continue.")
        return
    t1, t2 = st.tabs(["Opportunities: what to automate", "Impact simulator: what it is worth"])
    with t1:
        _opportunities_tab(log)
    with t2:
        _simulator_tab(log)