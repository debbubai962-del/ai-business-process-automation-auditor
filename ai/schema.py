"""The structure of the executive brief. The AI must return exactly this shape."""
from pydantic import BaseModel, Field


class _Model(BaseModel):
    """Lets the rule-based builder pass fields positionally; validation is unchanged."""

    def __init__(self, *args, **kwargs):
        kwargs.update(zip(type(self).model_fields, args))
        super().__init__(**kwargs)


class Issue(_Model):
    title: str
    detail: str


class Hypothesis(_Model):
    hypothesis: str
    evidence: str


class Action(_Model):
    action: str
    rationale: str


class Brief(_Model):
    headline: str
    executive_summary: str
    top_issues: list[Issue] = Field(default_factory=list)
    root_cause_hypotheses: list[Hypothesis] = Field(default_factory=list)
    automation_opportunities: list[Issue] = Field(default_factory=list)
    business_impact: str = ""
    recommended_actions: list[Action] = Field(default_factory=list)
    plan_30_days: list[str] = Field(default_factory=list)
    plan_60_days: list[str] = Field(default_factory=list)
    plan_90_days: list[str] = Field(default_factory=list)
    data_caveats: list[str] = Field(default_factory=list)


def flatten(b: Brief) -> str:
    parts = [b.headline, b.executive_summary, b.business_impact]
    parts += [f"{i.title}. {i.detail}" for i in b.top_issues + b.automation_opportunities]
    parts += [f"{h.hypothesis}. {h.evidence}" for h in b.root_cause_hypotheses]
    parts += [f"{a.action}. {a.rationale}" for a in b.recommended_actions]
    parts += b.plan_30_days + b.plan_60_days + b.plan_90_days + b.data_caveats
    return "\n".join(parts)