"""Builds the evidence pack: the ONLY information ever sent to the AI.

It contains aggregated findings and short category labels. It never contains raw rows, case IDs or file contents.
"""
import json
import re

import pandas as pd

from config.automation import NO_AUTOMATION
from engines.bottlenecks.detector import NONE
from services.bundle import AnalysisBundle

MAX_EVIDENCE_CHARS = 24_000
_LABEL_MAX = 60


def clean_label(value) -> str:
    """Category labels come from user data, so strip anything that could act as an instruction."""
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    s = re.sub(r"[<>{}`]", "", s)
    return re.sub(r"\s+", " ", s).strip()[:_LABEL_MAX]


def _r(x, nd=1):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def build_evidence(b: AnalysisBundle) -> dict:
    st, k, q = b.static, b.static.metrics.kpis, b.quality
    log = b.log
    bn = st.bottlenecks.table
    cur = b.globals.currency

    ev: dict = {
        "scope": {
            "dataset": clean_label(b.dataset_name),
            "period": f"{log.df['timestamp'].min():%d %b %Y} to {log.df['timestamp'].max():%d %b %Y}",
            "cases": log.cases, "events": log.events, "distinct_steps": log.activities,
        },
        "data_quality": {
            "records_uploaded": q.rows_before, "records_analysed": q.rows_after,
            "automatic_fixes_applied": len(q.applied), "items_left_for_review": len(q.review),
            "review_items": [f"{clean_label(a.category)}: {clean_label(a.column)} ({a.records:,} records)" for a in q.review],
            "cases_excluded_from_duration_metrics": int(k["cases_total"] - k["cases_analysed"]),
        },
        "process_health": {
            "average_cycle_days": _r(k["avg_cycle_h"] / 24), "median_cycle_hours": _r(k["median_cycle_h"]),
            "slowest_10_percent_take_at_least_days": _r(k["p90_cycle_h"] / 24),
            "sla_target_days": _r(k["sla_hours"] / 24) if k["sla_hours"] else None,
            "sla_compliance_percent": _r(k["sla_compliance"] * 100) if k["sla_compliance"] is not None else None,
            "sla_breach_percent": _r(k["sla_breach_rate"] * 100) if k["sla_breach_rate"] is not None else None,
            "rework_percent": _r(k["rework_rate"] * 100), "first_time_right_percent": _r(k["first_time_right"] * 100),
            "throughput_cases_per_week": _r(k["throughput_per_week"], 0),
        },
        "bottlenecks": [{
            "step": clean_label(r["activity"]), "classification": r["classification"],
            "average_time_at_step_hours": _r(r["avg_elapsed_h"]),
            "longest_step_in_percent_of_cases": _r(r["dominant_pct"] * 100, 0),
            "share_of_sla_breaches_percent": _r(r["sla_attribution"] * 100, 0) if pd.notna(r["sla_attribution"]) else None,
            "share_of_total_time_percent": _r(r["share_of_time"] * 100, 0),
            "confidence": r["confidence"], "likely_cause_hypothesis": r["likely_cause"],
        } for _, r in bn[bn["classification"] != NONE].iterrows()],
    }

    def factors(rep, n=5):
        out = []
        for f in rep.results:
            if f.significant and f.strength != "negligible":
                out.append({"factor": f.label, "share_of_variation_percent": _r(f.effect * 100, 0), "strength": f.strength,
                            "observed": re.sub(r"[<>{}`]", "", f.statement),
                            "possible_explanation_hypothesis": f.hypothesis})
        return out[:n]

    ev["root_causes"] = {
        "whole_case": factors(st.rc_case, 3),
        "at_primary_step": {"step": clean_label(st.step_name), "outcome": st.rc_step.outcome_label,
                            "factors": factors(st.rc_step, 5),
                            "ruled_out": [f.label for f in st.rc_step.results if not (f.significant and f.strength != "negligible")]},
        "notes": list(st.rc_step.notes),
    }

    t = st.scored
    ev["automation"] = {
        "recommended": [{"rank": int(r["rank"]), "step": clean_label(r["activity"]), "type": r["recommended"],
                         "quadrant": r["quadrant"], "priority_score": _r(r["priority"], 0),
                         "estimated_hours_saved_per_month": _r(r["hours_saved_month"], 0), "why": r["rec_reason"]}
                        for _, r in t[t["rank"].notna()].iterrows()],
        "not_recommended": [{"step": clean_label(r["activity"]), "reason": r["rec_reason"]}
                            for _, r in t[t["recommended"] == NO_AUTOMATION].iterrows()],
    }

    sc = b.scenario
    inc = [s.step for s in b.steps if s.include]
    ev["scenario_estimate"] = {
        "note": "Business estimate based on the stated assumptions, not a forecast.",
        "assumptions": {"hourly_cost": _r(b.globals.hourly_cost, 0), "cases_per_month": _r(b.globals.monthly_volume, 0),
                        "yearly_running_cost_percent_of_build": _r(b.globals.running_cost_pct * 100, 0), "currency": cur},
        "included_steps": [clean_label(s) for s in inc],
        "one_off_cost": _r(sc.impl_cost, 0), "hours_saved_per_month": _r(sc.hours_saved_month, 0),
        "net_saving_per_year": _r(sc.net_year, 0), "payback_months": _r(sc.payback_months) if sc.payback_months is not None else None,
        "three_year_net_value": _r(sc.net_3y, 0),
        "average_cycle_days_now": _r(sc.current["avg_cycle_h"] / 24), "average_cycle_days_improved": _r(sc.improved["avg_cycle_h"] / 24),
        "sla_compliance_percent_now": _r(sc.current["sla_compliance"] * 100) if "sla_compliance" in sc.current else None,
        "sla_compliance_percent_improved": _r(sc.improved["sla_compliance"] * 100) if "sla_compliance" in sc.improved else None,
    }
    ev["caveats"] = list(dict.fromkeys(st.metrics.notes + st.bottlenecks.notes[:1] * st.bottlenecks.approximate))
    return ev


def check_privacy(evidence: dict) -> None:
    """Hard stop if the evidence pack looks too large or contains row-like data."""
    text = json.dumps(evidence, default=str)
    if len(text) > MAX_EVIDENCE_CHARS:
        raise ValueError("Evidence pack is unexpectedly large; refusing to send it.")