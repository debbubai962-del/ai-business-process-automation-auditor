"""The six workspaces."""
from ui.components.cards import guide_panel, page_header, placeholder_panel
from ui.pages.automation import render_automation
from ui.pages.data_intake import render_data_intake
from ui.pages.executive_brief import render_executive_brief
from ui.pages.export import render_export
from ui.pages.findings import render_findings
from ui.pages.process_health import render_process_health

WORKSPACES = [
    {
        "title": "Data Intake",
        "eyebrow": "Step 1 of 6",
        "subtitle": "Upload, assess, and map your operational data before any analysis begins.",
        "question": "Can I trust this data, and does the system understand my process?",
        "why": "Every finding downstream is only as reliable as the data beneath it.",
        "next": "Upload a CSV or Excel export, or load a demo dataset.",
        "phase": "Phases 3 to 5",
        "render": render_data_intake,
    },
    {
        "title": "Process Health",
        "eyebrow": "Step 2 of 6",
        "subtitle": "Baseline performance of the process: speed, compliance, rework, and variation.",
        "question": "How is this process performing overall?",
        "why": "A baseline is needed before anyone can claim an improvement.",
        "next": "Note where time accumulates, then open Findings to see why.",
        "phase": "Phase 6",
        "render": render_process_health,
    },
    {
        "title": "Findings",
        "eyebrow": "Step 3 of 6",
        "subtitle": "Bottlenecks ranked by frequency and by impact, with evidence for likely causes.",
        "question": "Where is the pain, and why?",
        "why": "Fixing the wrong stage wastes budget. Evidence prevents that.",
        "next": "Review the bottlenecks, then test which factors explain them.",
        "phase": "Phases 7 and 8",
        "render": render_findings,
    },
    {
        "title": "Automation",
        "eyebrow": "Step 4 of 6",
        "subtitle": "Transparent prioritization of automation candidates and a savings simulator.",
        "question": "What should we automate first, and what is it worth?",
        "why": "Automation is only valuable where work is repetitive, rule-based, and frequent.",
        "next": "Review the ranked opportunities, then tune the savings assumptions in the simulator.",
        "phase": "Phases 9 and 10",
        "render": render_automation,
    },
    {
        "title": "Executive Brief",
        "eyebrow": "Step 5 of 6",
        "subtitle": "Leadership-ready interpretation and a 30/60/90-day improvement plan.",
        "question": "What do I tell leadership?",
        "why": "Decision-makers need conclusions and actions, not raw analysis.",
        "next": "Generate the brief, then check the verification panel before sharing it.",
        "phase": "Phase 11",
        "render": render_executive_brief,
    },
    {
        "title": "Export",
        "eyebrow": "Step 6 of 6",
        "subtitle": "Download the report and the full audit trail of every change and calculation.",
        "question": "How do I share and defend this?",
        "why": "Findings must be traceable to be trusted.",
        "next": "Download the report, workbook and audit trail.",
        "phase": "Phase 12",
        "render": render_export,
    },
]


def render_workspace(ws: dict) -> None:
    page_header(ws["eyebrow"], ws["title"], ws["subtitle"])
    guide_panel(ws["question"], ws["why"], ws["next"])
    if "render" in ws:
        ws["render"]()
    else:
        placeholder_panel(
            "This workspace is under construction",
            f"The analysis for this section is built in <b>{ws['phase']}</b> of the development plan.",
        )