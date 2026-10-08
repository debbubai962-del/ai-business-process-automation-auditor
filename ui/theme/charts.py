"""Shared Plotly styling so every chart matches the product palette."""
import plotly.graph_objects as go

from ui.theme import palette as p

_LAYOUT = dict(
    font=dict(family="Inter, Segoe UI, sans-serif", color=p.INK, size=13),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hoverlabel=dict(font_family="Inter, Segoe UI, sans-serif"),
)


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, **_LAYOUT)
    fig.update_xaxes(gridcolor=p.BORDER, zeroline=False, linecolor=p.BORDER)
    fig.update_yaxes(gridcolor=p.BORDER, zeroline=False, linecolor=p.BORDER)
    return fig