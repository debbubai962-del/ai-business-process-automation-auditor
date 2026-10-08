"""Reusable presentation components."""
from ui.components.badges import badge_html
from ui.components.html import render


def sidebar_brand() -> None:
    render("""
    <div class="brand">
      <div class="brand-mark">PA</div>
      <div>
        <div class="brand-name">Process Automation Auditor</div>
        <div class="brand-sub">Process Intelligence</div>
      </div>
    </div>
    """)


def status_chip(text: str, ok: bool) -> None:
    css = "chip" if ok else "chip off"
    render(f'<span class="{css}"><span class="dot"></span>{text}</span>')


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    render(f"""
    <div class="eyebrow">{eyebrow}</div>
    <div class="page-title">{title}</div>
    <div class="page-sub">{subtitle}</div>
    """)


def guide_panel(question: str, why: str, next_step: str) -> None:
    render(f"""
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-label">Question answered here</div>
        <div class="guide-text">{question}</div></div>
      <div class="guide-card why"><div class="guide-label">Why it matters</div>
        <div class="guide-text">{why}</div></div>
      <div class="guide-card next"><div class="guide-label">What to do next</div>
        <div class="guide-text">{next_step}</div></div>
    </div>
    """)


def kpi_row(items: list[dict]) -> None:
    """items: [{label, value, caption, badge, tone}] where tone in '', good, warn, bad."""
    cards = ""
    for it in items:
        cards += f"""
        <div class="kpi">
          <div class="kpi-label">{it['label']}</div>
          <div class="kpi-value {it.get('tone', '')}">{it['value']}</div>
          {badge_html(it['badge'])}
          <div class="kpi-caption">{it.get('caption', '')}</div>
        </div>
        """
    render(f'<div class="kpi-grid">{cards}</div>')


def callout(tone: str, title: str, body: str) -> None:
    """tone: info | success | warning | critical"""
    render(f"""
    <div class="callout {tone}">
      <div class="callout-title">{title}</div>
      <div class="callout-body">{body}</div>
    </div>
    """)


def placeholder_panel(title: str, body: str) -> None:
    render(f"""
    <div class="panel"><div class="panel-title">{title}</div><div>{body}</div></div>
    """)