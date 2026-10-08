"""Workspace 6: Export. Report, workbook, audit trail and evidence pack."""
import base64
import json

import streamlit as st

from reporting.audit import audit_dataframe
from reporting.excel_report import build_excel
from reporting.html_report import build_html_report
from services.bundle_ui import evidence_for, evidence_hash, get_brief, get_bundle
from ui.components.cards import callout


@st.cache_data(show_spinner="Building the workbook...")
def _excel(_ev: dict, _brief, _audit, key: str) -> bytes:
    return build_excel(_ev, _brief, _audit)


def render_export() -> None:
    bundle = get_bundle()
    if bundle is None:
        callout("warning", "Complete Data Intake first",
                "The report is built from your analysed findings. Upload data, approve the cleaned version, and "
                "confirm the process mapping to continue.")
        return

    ev = evidence_for(bundle)
    h = evidence_hash(ev)
    brief = get_brief(h)
    audit = audit_dataframe(bundle.quality)
    html = build_html_report(ev, brief, audit, bundle.generated_at)

    if brief is None:
        callout("info", "The Executive Brief is not included yet",
                "Generate it in the Executive Brief workspace first if you want it in the report and workbook.")
    else:
        callout("success", "Executive Brief included",
                f"The {'AI-written' if brief.source == 'ai' else 'rule-based'} brief from {brief.generated_at} is in the exports.")
    st.caption("Exports contain aggregated findings only. No raw records or case IDs are included.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### Report (HTML)")
        st.caption("A formatted, shareable report. Open it in a browser and use Print, then Save as PDF.")
        st.download_button("Download report (HTML)", html.encode("utf-8"), file_name="process_audit_report.html",
                           mime="text/html", type="primary")
        st.markdown("#### Audit trail (CSV)")
        st.caption("Every data-quality fix and review item: original issue, action taken, records affected.")
        st.download_button("Download audit trail (CSV)", audit.to_csv(index=False).encode("utf-8"),
                           file_name="data_quality_audit_trail.csv", mime="text/csv")
    with c2:
        st.markdown("#### Workbook (Excel)")
        st.caption("Findings, opportunities, scenario, brief and audit trail on separate sheets.")
        xlsx = _excel(ev, brief, audit, f"{h}-{brief.source if brief else 'none'}-{brief.generated_at if brief else ''}")
        st.download_button("Download workbook (Excel)", xlsx, file_name="process_audit_findings.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("#### Evidence pack (JSON)")
        st.caption("The exact aggregated findings the brief is built from, so every claim can be traced.")
        st.download_button("Download evidence pack (JSON)", json.dumps(ev, indent=2, default=str).encode("utf-8"),
                           file_name="evidence_pack.json", mime="application/json")

    with st.expander("Preview the report"):
        # A data: URL gives the preview its own isolated origin, so report content can never touch the app.
        st.iframe("data:text/html;base64," + base64.b64encode(html.encode("utf-8")).decode("ascii"), height=720)
    callout("warning", "Decision support, not decisions",
            "The report mixes calculated metrics, business estimates and hypotheses, each labelled. Validate with "
            "the business owners before implementation.")