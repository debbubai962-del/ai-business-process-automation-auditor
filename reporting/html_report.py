"""Self-contained, print-friendly HTML report. Every value is HTML-escaped. No scripts, no external resources."""
from html import escape as e

import pandas as pd

from ai.brief import BriefResult

_CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;color:#0B1B3F;background:#F4F6FB;margin:0;line-height:1.5}
.wrap{max-width:980px;margin:0 auto;padding:32px 28px}
h1{font-size:28px;margin:4px 0}h2{font-size:20px;margin:34px 0 10px;border-bottom:2px solid #E3E8F2;padding-bottom:6px}
h3{font-size:15px;margin:18px 0 6px}.eyebrow{color:#4F46E5;font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.sub{color:#5B6785}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}
.kpi{background:#fff;border:1px solid #E3E8F2;border-radius:10px;padding:12px 14px}.kpi b{display:block;font-size:22px}
.kpi span{font-size:12px;color:#5B6785}table{width:100%;border-collapse:collapse;background:#fff;font-size:13px;margin:8px 0}
th{background:#0B1B3F;color:#fff;text-align:left;padding:7px 9px}td{border-bottom:1px solid #E3E8F2;padding:7px 9px;vertical-align:top}
.tag{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;padding:2px 7px;border-radius:5px;margin-right:6px}
.t-ai{background:#E8E7FD;color:#4338CA}.t-metric{background:#DDF5F2;color:#0F766E}.t-est{background:#FEF3C7;color:#92400E}
.t-hyp{background:#F5F0FF;color:#6D28D9;border:1px dashed #B79CF0}.t-fact{background:#E8EEFB;color:#1E40AF}
.box{background:#fff;border:1px solid #E3E8F2;border-left:4px solid #4F46E5;border-radius:8px;padding:12px 16px;margin:10px 0}
.warn{border-left-color:#D97706;background:#FFFBEB}.crit{border-left-color:#DC2626;background:#FEF2F2}
ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}.foot{color:#5B6785;font-size:12px;margin-top:30px}
@media print{body{background:#fff}.wrap{padding:0}h2{break-after:avoid}table,.box{break-inside:avoid}}
"""


def _tag(kind: str) -> str:
    text, css = {"ai": ("AI INTERPRETATION", "t-ai"), "metric": ("CALCULATED METRIC", "t-metric"),
                 "est": ("BUSINESS ESTIMATE", "t-est"), "hyp": ("HYPOTHESIS", "t-hyp"), "fact": ("DATA FACT", "t-fact"),
                 "rules": ("RULE-BASED, NO AI", "t-metric")}[kind]
    return f'<span class="tag {css}">{text}</span>'


def _table(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{e(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{e('' if c is None else str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def _ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else "<p class='sub'>None.</p>"


def _kpi(label: str, value, note: str = "") -> str:
    return f'<div class="kpi"><span>{e(label)}</span><b>{e(str(value))}</b><span>{e(note)}</span></div>'


def _fmt(v, suffix="") -> str:
    return "n/a" if v is None else f"{v}{suffix}"


def _brief_section(r: BriefResult) -> str:
    b = r.brief
    src = _tag("ai") if r.source == "ai" else _tag("rules")
    who = f"Written by {e(r.model or '')}" if r.source == "ai" else "Generated from rules, without AI"
    v = r.validation
    trace = (f"All {v.total} figures in this brief were traced to the analysis." if v.ok else
             f"{v.supported} of {v.total} figures were traced to the analysis. Not traced: {', '.join(v.unsupported)}. "
             f"Verify these before use.")
    out = [f"<h2>Executive brief</h2><p>{src}<span class='sub'>{who}, {e(r.generated_at)}</span></p>",
           f"<div class='box'><b>{e(b.headline)}</b><p>{e(b.executive_summary)}</p></div>",
           "<h3>Top operational issues</h3><ul>" + "".join(f"<li><b>{e(i.title)}.</b> {e(i.detail)}</li>" for i in b.top_issues) + "</ul>",
           f"<h3>Root-cause hypotheses {_tag('hyp')}</h3><ul>" +
           "".join(f"<li>{e(h.hypothesis)} <i>Evidence: {e(h.evidence)}</i></li>" for h in b.root_cause_hypotheses) + "</ul>",
           "<h3>Automation opportunities</h3><ul>" + "".join(f"<li><b>{e(i.title)}.</b> {e(i.detail)}</li>" for i in b.automation_opportunities) + "</ul>",
           f"<h3>Business impact {_tag('est')}</h3><p>{e(b.business_impact)}</p>",
           "<h3>Recommended actions</h3><ul>" + "".join(f"<li><b>{e(a.action)}.</b> {e(a.rationale)}</li>" for a in b.recommended_actions) + "</ul>",
           "<h2>Improvement plan</h2><h3>First 30 days</h3>" + _ul(b.plan_30_days) +
           "<h3>Days 31 to 60</h3>" + _ul(b.plan_60_days) + "<h3>Days 61 to 90</h3>" + _ul(b.plan_90_days),
           f"<div class='box {'warn' if not v.ok else ''}'>{e(trace)}</div>"]
    if b.data_caveats:
        out.append("<h3>Data caveats</h3>" + _ul(b.data_caveats))
    return "".join(out)


def build_html_report(ev: dict, brief: BriefResult | None, audit: pd.DataFrame, generated_at: str) -> str:
    sc, ph, dq, sim = ev["scope"], ev["process_health"], ev["data_quality"], ev["scenario_estimate"]
    cur = sim["assumptions"]["currency"]
    parts = [
        f"<div class='eyebrow'>Process audit report</div><h1>{e(sc['dataset'])}</h1>"
        f"<p class='sub'>{e(sc['period'])} &middot; {sc['cases']:,} cases &middot; {sc['events']:,} events &middot; generated {e(generated_at)}</p>",
        "<div class='box warn'><b>Decision-support output.</b> This report combines calculated metrics, business estimates and "
        "hypotheses. Each section is labelled. Findings and recommendations should be validated by the business owners before "
        "implementation.</div>",
    ]
    if brief is not None:
        parts.append(_brief_section(brief))

    parts.append(f"<h2>Process health {_tag('metric')}</h2><div class='grid'>"
                 + _kpi("Average cycle time", f"{ph['average_cycle_days']} days")
                 + _kpi("Median cycle time", f"{ph['median_cycle_hours']} h")
                 + _kpi("Slowest 10% take at least", f"{ph['slowest_10_percent_take_at_least_days']} days")
                 + _kpi("SLA compliance", _fmt(ph["sla_compliance_percent"], "%"),
                        f"target {_fmt(ph['sla_target_days'])} days")
                 + _kpi("Rework rate", f"{ph['rework_percent']}%") + _kpi("First-time-right", f"{ph['first_time_right_percent']}%")
                 + _kpi("Throughput", f"{ph['throughput_cases_per_week']:,.0f} / week")
                 + _kpi("SLA breach rate", _fmt(ph["sla_breach_percent"], "%")) + "</div>")

    parts.append(f"<h2>Bottlenecks {_tag('metric')}</h2>" + _table(
        ["Step", "Classification", "Avg time at step (h)", "Longest step in (% cases)", "Share of SLA breaches (%)",
         "Share of total time (%)", "Confidence", "Likely cause (hypothesis)"],
        [[b["step"], b["classification"], b["average_time_at_step_hours"], b["longest_step_in_percent_of_cases"],
          _fmt(b["share_of_sla_breaches_percent"]), b["share_of_total_time_percent"], b["confidence"],
          b["likely_cause_hypothesis"]] for b in ev["bottlenecks"]]))

    rc = ev["root_causes"]["at_primary_step"]
    parts.append(f"<h2>Root causes: {e(rc['outcome'])}</h2>" + _table(
        ["Factor", "Explains (% of variation)", "Strength", "Observed " + "(metric)", "Possible explanation (hypothesis)"],
        [[f["factor"], f["share_of_variation_percent"], f["strength"], f["observed"],
          f["possible_explanation_hypothesis"]] for f in rc["factors"]]))
    if rc["ruled_out"]:
        parts.append(f"<p class='sub'>Factors tested with no meaningful effect: {e(', '.join(rc['ruled_out']))}.</p>")

    au = ev["automation"]
    parts.append(f"<h2>Automation opportunities {_tag('est')}</h2>" + _table(
        ["Rank", "Step", "Recommended", "Quadrant", "Priority (0-100)", "Est. hours saved / month", "Reasoning"],
        [[r["rank"], r["step"], r["type"], r["quadrant"], r["priority_score"], r["estimated_hours_saved_per_month"], r["why"]]
         for r in au["recommended"]]))
    if au["not_recommended"]:
        parts.append("<h3>Not recommended for automation</h3>" + _ul([f"{n['step']}: {n['reason']}" for n in au["not_recommended"]]))

    a = sim["assumptions"]
    parts.append(f"<h2>Impact scenario {_tag('est')}</h2><p class='sub'>Estimates based on the assumptions below. "
                 f"Not a forecast.</p>" + _table(["Assumption", "Value"], [
                     ["Employee hourly cost", f"{cur}{a['hourly_cost']:,.0f}"], ["Cases per month", f"{a['cases_per_month']:,.0f}"],
                     ["Yearly running cost (% of build)", f"{a['yearly_running_cost_percent_of_build']}%"],
                     ["Opportunities included", ", ".join(sim["included_steps"]) or "None"]]) + _table(["Result", "Estimate"], [
                     ["Hours saved per month", f"{sim['hours_saved_per_month']:,.0f}"],
                     ["Net saving per year", f"{cur}{sim['net_saving_per_year']:,.0f}"],
                     ["One-off cost", f"{cur}{sim['one_off_cost']:,.0f}"],
                     ["Payback", _fmt(sim["payback_months"], " months")],
                     ["3-year net value", f"{cur}{sim['three_year_net_value']:,.0f}"],
                     ["Average cycle time", f"{sim['average_cycle_days_now']} to {sim['average_cycle_days_improved']} days"],
                     ["SLA compliance", f"{_fmt(sim['sla_compliance_percent_now'], '%')} to {_fmt(sim['sla_compliance_percent_improved'], '%')}"]]))

    parts.append(f"<h2>Data quality and audit trail {_tag('fact')}</h2><p>{dq['records_uploaded']:,} records uploaded, "
                 f"{dq['records_analysed']:,} analysed after cleaning. {dq['automatic_fixes_applied']} safe fixes were applied "
                 f"and {dq['items_left_for_review']} items were left for human review. The original upload was never modified.</p>"
                 + _table(list(audit.columns), audit.astype(str).values.tolist()))
    parts.append("<h2>How to read the labels</h2>" + _ul([
        "DATA FACT: observed directly in the uploaded data.", "CALCULATED METRIC: computed deterministically by the analysis engine.",
        "BUSINESS ESTIMATE: a scenario result driven by stated, editable assumptions.",
        "AI INTERPRETATION: narrative written by an AI model using only the calculated findings.",
        "HYPOTHESIS: a possible explanation, not proven."]))
    parts.append("<p class='foot'>Generated by the AI Business Process Automation Auditor. Only aggregated findings are "
                 "included; no raw records are in this report.</p>")
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{e(sc['dataset'])} - process audit</title>"
            f"<style>{_CSS}</style></head><body><div class='wrap'>{''.join(parts)}</div></body></html>")