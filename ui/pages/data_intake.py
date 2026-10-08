"""Workspace 1: Data Intake (upload, profile, data quality, process mapping)."""
from pathlib import Path

import pandas as pd
import streamlit as st

from engines.ingestion.loader import LoadError, list_excel_sheets, load_bytes
from engines.ingestion.profiler import profile_dataset
from models.dataset import LoadedDataset
from services.session import clear_dataset, get_dataset, set_dataset
from ui.components.cards import callout, kpi_row
from ui.pages.data_quality import render_data_quality
from ui.pages.process_mapping import render_process_mapping

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"

TYPE_LABELS = {
    "identifier": "Identifier",
    "datetime": "Date / time",
    "numeric": "Number",
    "categorical": "Category",
    "text": "Free text",
    "empty": "Empty",
}


@st.cache_data(show_spinner=False)
def _profile(df: pd.DataFrame):
    return profile_dataset(df)


def _upload_section() -> None:
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown("#### Upload your process data")
        up = st.file_uploader(
            "CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            help="Files are processed in memory and are not saved to disk.",
            label_visibility="collapsed",
        )
        if up is not None:
            raw = up.getvalue()
            sheet = None
            if up.name.lower().endswith((".xlsx", ".xls")):
                try:
                    sheets = list_excel_sheets(raw)
                    if len(sheets) > 1:
                        sheet = st.selectbox("Worksheet", sheets)
                except LoadError as exc:
                    st.error(str(exc))
                    return
            if st.button("Load file", type="primary"):
                try:
                    df = load_bytes(up.name, raw, sheet)
                    set_dataset(LoadedDataset(name=up.name, df=df, source="upload"))
                    st.rerun()
                except LoadError as exc:
                    st.error(str(exc))

    with right:
        st.markdown("#### Or try a demo dataset")
        st.caption("Synthetic invoice-processing data. Contains no real business information.")
        c1, c2 = st.columns(2)
        for col, label, fname in [
            (c1, "Demo: clean", "invoice_process_clean.csv"),
            (c2, "Demo: messy", "invoice_process_messy.csv"),
        ]:
            path = SAMPLE_DIR / fname
            if col.button(label, width="stretch", disabled=not path.exists()):
                df = load_bytes(fname, path.read_bytes())
                set_dataset(LoadedDataset(name=fname, df=df, source="demo"))
                st.rerun()

    callout(
        "info",
        "Data privacy",
        "Uploaded files are held in memory for this session only. Only aggregated findings are ever "
        "sent to the AI layer, never raw rows.",
    )


def _profile_section(ds: LoadedDataset) -> None:
    profile = _profile(ds.df)

    period = f"{profile.date_min} to {profile.date_max}" if profile.date_min else "Not detected"
    dup_tone = "warn" if profile.duplicate_rows else "good"
    miss_pct = profile.total_missing_cells / (profile.rows * profile.columns) * 100
    kpi_row([
        {"label": "Records", "value": f"{profile.rows:,}", "badge": "fact",
         "caption": f"{profile.columns} columns"},
        {"label": "Period covered", "value": period if len(period) < 24 else "See below", "badge": "fact",
         "caption": period if len(period) >= 24 else "Earliest to latest date found"},
        {"label": "Exact duplicate rows", "value": f"{profile.duplicate_rows:,}", "badge": "fact",
         "caption": "Identical in every column", "tone": dup_tone},
        {"label": "Missing cells", "value": f"{profile.total_missing_cells:,}", "badge": "fact",
         "caption": f"{miss_pct:.1f}% of all cells", "tone": "warn" if miss_pct > 1 else "good"},
    ])

    tab_cols, tab_preview = st.tabs(["Column overview", "Data preview"])

    with tab_cols:
        st.caption("Detected type is the system's best inference. You can confirm or correct it in Process Mapping.")
        table = pd.DataFrame(
            [
                {
                    "Column": c.name,
                    "Detected as": TYPE_LABELS.get(c.detected_type, c.detected_type),
                    "Missing": c.missing,
                    "Missing %": c.missing_pct,
                    "Distinct values": c.unique,
                    "Examples": ", ".join(c.sample_values),
                }
                for c in profile.column_profiles
            ]
        )
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={
                "Missing %": st.column_config.ProgressColumn(
                    "Missing %", min_value=0, max_value=100, format="%.1f%%"
                ),
            },
        )

    with tab_preview:
        st.caption("First 100 rows exactly as uploaded. Nothing has been modified.")
        st.dataframe(ds.df.head(100), width="stretch", hide_index=True)

    if profile.duplicate_rows or miss_pct >= 1:
        callout("warning", "Initial read",
                "Potential data-quality issues were detected. Open the Data quality tab to examine "
                "them and apply safe fixes. Nothing has been changed yet.")
    else:
        callout("success", "Initial read: looks tidy",
                "No obvious structural problems at this level. Deeper checks run in the Data quality tab.")


def render_data_intake() -> None:
    ds = get_dataset()
    if ds is None:
        _upload_section()
        return

    top = st.columns([6, 1])
    top[0].markdown(f"#### Dataset: `{ds.name}`")
    if top[1].button("Remove file"):
        clear_dataset()
        st.rerun()

    tab_profile, tab_quality, tab_mapping = st.tabs(["1. Profile", "2. Data quality", "3. Process mapping"])
    with tab_profile:
        _profile_section(ds)
    with tab_quality:
        render_data_quality(ds)
    with tab_mapping:
        render_process_mapping()