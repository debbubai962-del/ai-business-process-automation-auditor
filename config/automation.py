"""Transparent defaults for the automation engine. Every number here is an assumption the user can inspect."""

NO_AUTOMATION = "No automation recommended"

# type -> (default time reduction, base complexity 0-1, affects waiting time, plain-language description)
AUTOMATION_TYPES: dict[str, tuple[float, float, bool, str]] = {
    "RPA": (0.80, 0.35, False, "A software robot keys or copies data between systems, exactly as a person would."),
    "Rule-based automation": (0.70, 0.40, False, "Fixed business rules perform checks, matching or calculations automatically."),
    "API integration": (0.90, 0.50, False, "Systems exchange data directly, so the manual step disappears."),
    "Workflow automation": (0.40, 0.55, True, "Automatic routing, reminders and escalation so work does not sit in queues."),
    "AI-assisted automation": (0.50, 0.75, False, "AI handles semi-structured work and a person reviews uncertain cases."),
    "Human-in-the-loop automation": (0.50, 0.60, True, "Automate the standard cases and route exceptions and decisions to a person."),
    "Process redesign": (0.30, 0.70, True, "Change the process itself (for example approval limits or parallel steps) before automating."),
    NO_AUTOMATION: (0.0, 0.0, False, "Human judgement dominates, or the benefit does not justify the effort and risk."),
}

DEFAULT_WEIGHTS = {"impact": 0.25, "suitability": 0.25, "frequency": 0.10,
                   "time_saving": 0.20, "complexity": 0.10, "risk": 0.10}
POSITIVE = ("impact", "suitability", "frequency", "time_saving")
NEGATIVE = ("complexity", "risk")
WEIGHT_LABELS = {"impact": "Business impact", "suitability": "Automation suitability", "frequency": "Frequency",
                 "time_saving": "Potential time saving", "complexity": "Implementation complexity (subtracts)",
                 "risk": "Risk (subtracts)"}

HANDS_ON_SHARE = 0.25         # share of the recorded step duration assumed to be hands-on work
HANDS_ON_CAP_MIN = 30         # recorded durations often include waiting and interruptions, so hands-on time is capped
LOW_VOLUME_PER_MONTH = 20     # below this, automation rarely pays back
JUDGMENT_CV = 0.8             # processing-time variation above this suggests case-by-case judgement

IMPLEMENTATION_COST = {"Low": 15_000, "Medium": 40_000, "High": 100_000}   # default one-off cost, user editable
RUNNING_COST_PCT = 0.20       # yearly running cost as a share of implementation cost, user editable
DEFAULT_HOURLY_COST = 30.0