"""The epistemic labels. Every output in the app carries one of these."""

LABELS = {
    "fact": ("DATA FACT", "b-fact", "Directly observed in the uploaded data."),
    "metric": ("CALCULATED METRIC", "b-metric", "Computed deterministically by the analysis engine."),
    "estimate": ("BUSINESS ESTIMATE", "b-estimate", "Scenario result based on user-editable assumptions."),
    "ai": ("AI INTERPRETATION", "b-ai", "AI narrative built only from calculated findings."),
    "hypothesis": ("AI HYPOTHESIS", "b-hypo", "A possible explanation. Not proven. Validate with the process owner."),
    "inference": ("RULE-BASED HYPOTHESIS", "b-hypo",
                  "A possible explanation produced by transparent rules from the calculated evidence. "
                  "Not proven. Validate with the process owner."),
}


def badge_html(kind: str) -> str:
    text, css, tip = LABELS[kind]
    return f'<span class="badge {css}" title="{tip}">{text}</span>'