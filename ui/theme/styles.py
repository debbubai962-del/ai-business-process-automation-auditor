"""Global stylesheet. Injected once per page run."""
import streamlit as st

from ui.theme import palette as p

_FONT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');"

_ROOT = f"""
:root {{
  --navy:{p.NAVY}; --ink:{p.INK}; --muted:{p.MUTED}; --bg:{p.BG};
  --surface:{p.SURFACE}; --border:{p.BORDER}; --indigo:{p.INDIGO};
  --blue:{p.BLUE}; --teal:{p.TEAL}; --cyan:{p.CYAN};
  --emerald:{p.EMERALD}; --amber:{p.AMBER}; --coral:{p.CORAL};
}}
"""

_CSS = """
.stApp, .stMarkdown, p, li, label, h1, h2, h3, h4, h5, h6, button, input, textarea {
  font-family: 'Inter', 'Segoe UI', sans-serif;
}
.stApp { background: var(--bg); }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1280px; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
h1, h2, h3, h4 { color: var(--navy); letter-spacing: -0.01em; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
.brand { display:flex; align-items:center; gap:12px; padding: 6px 4px 18px 4px; }
.brand-mark {
  width:38px; height:38px; border-radius:10px; color:#fff; font-weight:700;
  display:flex; align-items:center; justify-content:center; font-size:15px;
  background: linear-gradient(135deg, var(--indigo), var(--teal));
}
.brand-name { font-weight:700; color:var(--navy); font-size:15px; line-height:1.2; }
.brand-sub { font-size:11px; color:var(--muted); letter-spacing:.04em; text-transform:uppercase; }
.nav-caption {
  font-size:11px; font-weight:600; letter-spacing:.08em; color:var(--muted);
  margin: 14px 4px 10px 4px; line-height:1.4; display:block;
}

/* Sidebar navigation buttons */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.2rem; }
[data-testid="stSidebar"] button {
  display: flex !important;
  justify-content: flex-start !important;
  align-items: center !important;
  text-align: left !important;
  border-radius: 10px;
  padding: 0.5rem 0.8rem;
  box-shadow: none;
}
[data-testid="stSidebar"] button > div,
[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {
  display: flex !important;
  justify-content: flex-start !important;
  text-align: left !important;
  width: 100% !important;
}
[data-testid="stSidebar"] button p {
  font-size: 14px; font-weight: 500; text-align: left !important; width: 100%; margin: 0;
}
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
  background: transparent; border: 1px solid transparent; color: var(--ink);
}
[data-testid="stSidebar"] button[kind="secondary"]:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
  background: #F1F4FB; border-color: transparent; color: var(--navy);
}
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
  background: #EEF0FF; border: 1px solid #D9DCFB; color: var(--indigo);
}
[data-testid="stSidebar"] button[kind="primary"] p,
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {
  color: var(--indigo); font-weight: 600;
}
[data-testid="stSidebar"] button[kind="primary"]:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
  background: #E6E9FF; border-color: #D9DCFB;
}

.chip {
  display:inline-flex; align-items:center; gap:8px; font-size:12px; font-weight:500;
  padding:6px 12px; border-radius:999px; border:1px solid var(--border); background:#F8FAFD; color:var(--ink);
}
.chip .dot { width:8px; height:8px; border-radius:50%; background: var(--emerald); }
.chip.off .dot { background: var(--amber); }

/* ---------- Stepper ---------- */
.stepper {
  display:flex; background: var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:16px 12px; margin-bottom:22px;
}
.step { flex:1; display:flex; flex-direction:column; align-items:center; gap:8px; position:relative; }
.step:not(:last-child)::after {
  content:""; position:absolute; top:15px; left:calc(50% + 20px); right:calc(-50% + 20px);
  height:2px; background: var(--border);
}
.step.done:not(:last-child)::after { background: var(--teal); }
.step-dot {
  width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:13px; font-weight:600; background:#EEF1F8; color:var(--muted); z-index:1;
}
.step.active .step-dot { background: var(--indigo); color:#fff; box-shadow: 0 0 0 5px #E3E5FD; }
.step.done .step-dot { background: var(--teal); color:#fff; }
.step-label { font-size:12px; font-weight:500; color:var(--muted); text-align:center; }
.step.active .step-label { color: var(--navy); font-weight:600; }

/* ---------- Page header ---------- */
.eyebrow { font-size:12px; font-weight:600; letter-spacing:.1em; color:var(--indigo); text-transform:uppercase; }
.page-title { font-size:30px; font-weight:700; color:var(--navy); margin:4px 0 4px 0; letter-spacing:-0.02em; }
.page-sub { font-size:15px; color:var(--muted); margin-bottom:18px; max-width:760px; }

/* ---------- Guide panel ---------- */
.guide-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:14px; margin-bottom:22px; }
.guide-card {
  background: var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:16px 18px; border-top:3px solid var(--indigo);
}
.guide-card.why { border-top-color: var(--teal); }
.guide-card.next { border-top-color: var(--cyan); }
.guide-label { font-size:11px; font-weight:600; letter-spacing:.08em; color:var(--muted); text-transform:uppercase; }
.guide-text { font-size:14px; color:var(--ink); margin-top:6px; line-height:1.5; }

/* ---------- KPI cards ---------- */
.kpi-grid { display:grid; grid-template-columns: repeat(4, 1fr); gap:14px; margin-bottom:22px; }
.kpi {
  background: var(--surface); border:1px solid var(--border); border-radius:14px; padding:16px 18px;
  box-shadow: 0 1px 2px rgba(11,27,63,.04);
}
.kpi-label { font-size:12px; font-weight:600; color:var(--muted); letter-spacing:.02em; }
.kpi-value { font-size:30px; font-weight:700; color:var(--navy); margin:6px 0 6px 0; letter-spacing:-0.02em; }
.kpi-value.good { color: var(--emerald); }
.kpi-value.warn { color: var(--amber); }
.kpi-value.bad { color: var(--coral); }
.kpi-caption { font-size:12px; color:var(--muted); margin-top:8px; }

/* ---------- Trust badges ---------- */
.badge {
  display:inline-block; font-size:10px; font-weight:700; letter-spacing:.07em;
  padding:3px 8px; border-radius:6px; border:1px solid transparent; white-space:nowrap;
}
.b-fact { background:#E8EEFB; color:#1E40AF; border-color:#C9D7F6; }
.b-metric { background:#DDF5F2; color:#0F766E; border-color:#B5E6E0; }
.b-estimate { background:#FEF3C7; color:#92400E; border-color:#F6DFA0; }
.b-ai { background:#E8E7FD; color:#4338CA; border-color:#CFCDF9; }
.b-hypo { background:#F5F0FF; color:#6D28D9; border:1px dashed #B79CF0; }

/* ---------- Callouts ---------- */
.callout { border-radius:12px; padding:14px 16px; margin:10px 0; border:1px solid; border-left-width:4px; }
.callout-title { font-weight:600; font-size:14px; margin-bottom:3px; }
.callout-body { font-size:13.5px; line-height:1.5; }
.callout.info { background:#EFF6FF; border-color:#BFDBFE; color:#1E3A8A; }
.callout.success { background:#ECFDF5; border-color:#A7F3D0; color:#065F46; }
.callout.warning { background:#FFFBEB; border-color:#FDE68A; color:#92400E; }
.callout.critical { background:#FEF2F2; border-color:#FECACA; color:#991B1B; }

/* ---------- Placeholder panel ---------- */
.panel {
  background: var(--surface); border:1px dashed #C9D2E6; border-radius:14px;
  padding:34px; text-align:center; color:var(--muted);
}
.panel-title { color:var(--navy); font-weight:600; font-size:16px; margin-bottom:6px; }

/* ---------- Native widgets ---------- */
button[data-baseweb="tab"] p { font-weight:600; font-size:14px; }
.stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:600; }
[data-testid="stExpander"] { background: var(--surface); border:1px solid var(--border); border-radius:12px; }
"""


def inject_css() -> None:
    st.markdown(f"<style>{_FONT}{_ROOT}{_CSS}</style>", unsafe_allow_html=True)