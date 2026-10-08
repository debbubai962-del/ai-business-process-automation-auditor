"""Deterministic brief used when no AI key is configured, or as a fallback. Every figure comes straight from the evidence."""
from ai.schema import Action, Brief, Hypothesis, Issue

PRIMARY, OCCASIONAL = "Primary bottleneck", "Occasional severe delay"

_ACTION = {
    "Process redesign": "Redesign how {s} works (approval limits, delegation, parallel review) before adding tools",
    "RPA": "Pilot a software robot for {s}",
    "Rule-based automation": "Automate the rule-based checks in {s}",
    "API integration": "Connect the systems around {s} directly",
    "Workflow automation": "Add automatic routing, reminders and escalation to {s}",
    "AI-assisted automation": "Trial AI assistance for {s} with human review of uncertain cases",
    "Human-in-the-loop automation": "Automate routine cases in {s} and route exceptions to a person",
}


def rules_brief(ev: dict) -> Brief:
    ph, dq, sc, scope = ev["process_health"], ev["data_quality"], ev["scenario_estimate"], ev["scope"]
    cur = sc["assumptions"]["currency"]
    prim = [b for b in ev["bottlenecks"] if b["classification"] == PRIMARY]
    occ = [b for b in ev["bottlenecks"] if b["classification"] == OCCASIONAL]
    rec = ev["automation"]["recommended"]
    notrec = ev["automation"]["not_recommended"]

    sla = ""
    if ph["sla_compliance_percent"] is not None:
        sla = (f" {ph['sla_compliance_percent']}% finish within the {ph['sla_target_days']}-day target, "
               f"so {ph['sla_breach_percent']}% breach their SLA.")
    p = prim[0] if prim else None
    lead = (f" {p['step']} is the longest step in {p['longest_step_in_percent_of_cases']:.0f}% of cases and accounts for "
            f"{p['share_of_total_time_percent']:.0f}% of all elapsed step time.") if p else ""
    summary = (f"Across {scope['cases']:,} cases ({scope['period']}), the average case takes "
               f"{ph['average_cycle_days']} days from start to finish.{sla} {ph['rework_percent']}% of cases repeat at "
               f"least one step.{lead}")
    can_estimate = (sc["hours_saved_per_month"] or 0) > 0
    if p and can_estimate:
        headline = (f"{p['step']} is the main bottleneck, and the recommended changes could save about "
                    f"{cur}{sc['net_saving_per_year']:,.0f} a year (estimate).")
    elif p:
        headline = f"{p['step']} is the main bottleneck, and the average case takes {ph['average_cycle_days']} days."
    else:
        headline = f"The process averages {ph['average_cycle_days']} days per case."

    issues: list[Issue] = []
    if p:
        sla_part = f" and the longest step in {p['share_of_sla_breaches_percent']:.0f}% of SLA breaches" \
            if p["share_of_sla_breaches_percent"] is not None else ""
        issues.append(Issue(f"{p['step']}: primary bottleneck",
                            f"Cases spend {p['average_time_at_step_hours']} hours at this step on average{sla_part}. "
                            f"Confidence: {p['confidence']}."))
    for o in occ:
        issues.append(Issue(f"{o['step']}: occasional severe delay",
                            f"Rarely the longest step ({o['longest_step_in_percent_of_cases']:.0f}% of cases), but each "
                            f"occurrence takes {o['average_time_at_step_hours']} hours on average."))
    if ph["sla_breach_percent"] is not None:
        issues.append(Issue("SLA breaches", f"{ph['sla_breach_percent']}% of cases miss their target. The slowest 10% take at "
                                            f"least {ph['slowest_10_percent_take_at_least_days']} days."))
    issues.append(Issue("Rework", f"{ph['rework_percent']}% of cases repeat a step; {ph['first_time_right_percent']}% are "
                                  f"completed right the first time."))

    hyps = [Hypothesis(f["possible_explanation_hypothesis"],
                       f"{f['factor']} explains {f['share_of_variation_percent']:.0f}% of the variation. {f['observed']}")
            for f in ev["root_causes"]["at_primary_step"]["factors"][:3] if f["possible_explanation_hypothesis"]]

    opps = [Issue(f"{r['step']}: {r['type']}",
                  f"{r['quadrant']}, priority {r['priority_score']:.0f} out of 100, about "
                  f"{r['estimated_hours_saved_per_month']:.0f} hours saved a month (estimate). {r['why']}") for r in rec[:4]]
    opps += [Issue(f"{n['step']}: not recommended for automation", n["reason"]) for n in notrec]

    impact = ""
    if sc["included_steps"] and not can_estimate:
        impact = ("Savings cannot be estimated yet because the hands-on effort per step is unknown for this dataset. "
                  "Enter it in the impact simulator to obtain an estimate.")
    elif sc["included_steps"]:
        a = sc["assumptions"]
        impact = (f"Under stated assumptions (hourly cost {cur}{a['hourly_cost']:,.0f}, {a['cases_per_month']:,.0f} cases per "
                  f"month), the selected opportunities save about {sc['hours_saved_per_month']:,.0f} hours a month and "
                  f"{cur}{sc['net_saving_per_year']:,.0f} net per year after running costs")
        if sc["payback_months"] is not None:
            impact += f", with payback in about {sc['payback_months']} months"
        impact += f". Average cycle time moves from {sc['average_cycle_days_now']} to {sc['average_cycle_days_improved']} days"
        if sc["sla_compliance_percent_now"] is not None:
            impact += (f" and SLA compliance from {sc['sla_compliance_percent_now']}% to "
                       f"{sc['sla_compliance_percent_improved']}%")
        impact += ". These are business estimates, not forecasts."

    actions = [Action(_ACTION[r["type"]].format(s=r["step"]), r["why"]) for r in rec[:4] if r["type"] in _ACTION]

    quick = next((r for r in rec if r["quadrant"] == "Quick win"), rec[0] if rec else None)
    strategic = p or (rec[0] if rec else None)
    p30 = ["Share these findings with the process owners and confirm the likely causes with the people who do the work",
           "Resolve the data-quality items left for review so future measurements are reliable",
           f"Record today's baseline (average cycle time {ph['average_cycle_days']} days, "
           f"SLA compliance {ph['sla_compliance_percent']}%) to judge improvement against"
           if ph["sla_compliance_percent"] is not None else
           f"Record today's baseline (average cycle time {ph['average_cycle_days']} days) to judge improvement against"]
    if quick:
        p30.append(f"Select the pilot: {quick['step']} ({quick['type']})")
    p60 = []
    if quick:
        p60.append(f"Run the {quick['step']} pilot and measure time saved against the baseline")
    if strategic:
        p60.append(f"Design the changes for {strategic['step']} with the people involved, starting with the factors found in the root-cause analysis")
    p60.append("Review progress weekly against the baseline and adjust")
    p90 = ["Roll out the pilots that met their targets and stop those that did not",
           "Re-run this audit on fresh data and compare it with the baseline",
           "Decide which strategic projects to fund, using the updated evidence"]

    caveats = list(ev["caveats"]) + dq["review_items"][:3]
    return Brief(headline, summary, issues, hyps, opps, impact, actions, p30, p60, p90, caveats)