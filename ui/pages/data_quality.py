"""Data Quality tab: audit trail, review queue, original-vs-cleaned comparison, approval."""
import pandas as pd
import streamlit as st

from engines.quality.compare import changed_values
from engines.quality.engine import clean_dataset
from models.dataset import LoadedDataset
from models.quality import AuditEntry, QualityResult
from services.session import (get_quality, is_quality_approved, set_quality,
                              set_quality_approved)
from ui.components.badges import badge_html
from ui.components.cards import callout, kpi_row
from ui.components.html import render


def _label(e: AuditEntry) -> str:
    return f"{e.category}   |   {e.column}   |   {e.records:,} records"


def _entry_body(e: AuditEntry) -> None:
    c1, c2, c3 = st.columns([5, 5, 2])
    c1.markdown("**Original issue**")
    c1.write(e.issue)
    c2.markdown("**Action taken**" if e.status == "applied" else "**Recommended action**")
    c2.write(e.action)
    c3.markdown("**Records affected**")
    c3.write(f"{e.records:,}")
    if e.details:
        st.markdown("\n".join(f"- {d}" for d in e.details))
    if e.sample is not None and len(e.sample):
        st.caption("Example records")
        st.dataframe(e.sample, width="stretch", hide_index=False)
    render(badge_html("fact"))


def _audit_log_csv(result: QualityResult) -> bytes:
    rows = [{"Status": "Fixed" if e.status == "applied" else "Needs review", "Category": e.category,
             "Column": e.column, "Original issue": e.issue, "Action": e.action,
             "Records affected": e.records, "Details": " | ".join(e.details)} for e in result.audit]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def _intro(ds: LoadedDataset) -> None:
    callout("info", "What this step does",
            "The system inspects your data for missing values, duplicates, inconsistent spellings, mixed "
            "date formats, impossible timestamps and extreme values. Safe formatting problems are fixed on "
            "a copy and logged. Anything that could change a business conclusion is flagged for you, "
            "never changed silently. Your original upload is never modified.")
    if st.button("Run data quality check", type="primary"):
        with st.spinner("Inspecting the data..."):
            set_quality(clean_dataset(ds.df))
        st.rerun()


def _audit_tab(result: QualityResult) -> None:
    st.caption("Every automatic change, in the form: original issue, action taken, records affected.")
    if not result.applied:
        st.success("No automatic fixes were needed.")
    for e in result.applied:
        with st.expander(_label(e)):
            _entry_body(e)


def _review_tab(result: QualityResult) -> None:
    st.caption("These items were NOT changed. Tick each one once you have reviewed it.")
    if not result.review:
        st.success("Nothing needs review.")
    for i, e in enumerate(result.review):
        with st.expander(_label(e)):
            _entry_body(e)
            st.checkbox("I have reviewed this item", key=f"ack_{i}")


def _compare_tab(ds: LoadedDataset, result: QualityResult) -> None:
    st.caption("Pick a column to see exactly which values were changed.")
    col = st.selectbox("Column", list(result.cleaned.columns), label_visibility="collapsed")
    n, table = changed_values(ds.df, result.cleaned, col)
    if n == 0:
        st.info(f"No values were changed in '{col}'.")
    else:
        st.markdown(f"**{n:,}** of {len(result.cleaned):,} values changed in `{col}`.")
        st.dataframe(table, width="stretch", hide_index=True)
        if len(table) == 25 and (table["Records"] == 1).all():
            st.caption("Showing the first 25 examples.")
    with st.expander(f"Duplicate rows set aside ({len(result.quarantined):,})"):
        st.caption("First 100 removed rows. They are kept for audit and excluded from analysis.")
        st.dataframe(result.quarantined.head(100), width="stretch")


def _approval(result: QualityResult) -> None:
    st.markdown("#### Approve and continue")
    pending = sum(1 for i in range(len(result.review)) if not st.session_state.get(f"ack_{i}"))
    if is_quality_approved():
        callout("success", "Cleaned data approved",
                f"{len(result.cleaned):,} records are ready for process mapping and analysis. "
                f"{len(result.review)} review item(s) stay documented as caveats in the audit trail.")
        if st.button("Reopen review"):
            set_quality_approved(False)
            st.rerun()
        return
    if pending:
        callout("warning", f"{pending} review item(s) not yet ticked",
                "You can still approve. Unreviewed items will be recorded as open caveats.")
    if st.button("Approve cleaned data and continue", type="primary"):
        set_quality_approved(True)
        st.rerun()


def _results(ds: LoadedDataset, result: QualityResult) -> None:
    removed = result.rows_before - result.rows_after
    kpi_row([
        {"label": "Records after cleaning", "value": f"{result.rows_after:,}", "badge": "fact",
         "caption": f"{result.rows_before:,} before, {removed:,} repeated rows set aside"},
        {"label": "Safe fixes applied", "value": f"{len(result.applied)}", "badge": "fact",
         "caption": "Each one is logged in the audit trail", "tone": "good"},
        {"label": "Items for your review", "value": f"{len(result.review)}", "badge": "fact",
         "caption": "Not changed. Need a human decision", "tone": "warn" if result.review else "good"},
        {"label": "Original upload", "value": "Unchanged", "badge": "fact",
         "caption": "Cleaning is done on a copy"},
    ])
    t1, t2, t3 = st.tabs([f"Audit trail ({len(result.applied)})",
                          f"Needs review ({len(result.review)})", "Original vs cleaned"])
    with t1:
        _audit_tab(result)
    with t2:
        _review_tab(result)
    with t3:
        _compare_tab(ds, result)

    d1, d2, _ = st.columns([2, 2, 4])
    d1.download_button("Download audit log (CSV)", _audit_log_csv(result),
                       file_name="data_quality_audit_log.csv", mime="text/csv")
    d2.download_button("Download cleaned data (CSV)", result.cleaned.to_csv(index=False).encode("utf-8"),
                       file_name="cleaned_data.csv", mime="text/csv")
    st.markdown("---")
    _approval(result)


def render_data_quality(ds: LoadedDataset) -> None:
    result = get_quality()
    if result is None:
        _intro(ds)
    else:
        _results(ds, result)