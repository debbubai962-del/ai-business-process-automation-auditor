"""Orchestrates brief generation: AI when available, rule-based otherwise, always validated."""
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from ai.client import AIError, call_llm
from ai.evidence import check_privacy
from ai.prompts import SYSTEM_PROMPT, user_prompt
from ai.rules import rules_brief
from ai.schema import Brief, flatten
from ai.validate import Validation, validate_text
from config.settings import Settings


@dataclass
class BriefResult:
    brief: Brief
    source: str                 # "ai" or "rules"
    validation: Validation
    model: str | None
    fallback_reason: str | None
    generated_at: str


class BriefParseError(Exception):
    pass


def parse_brief(raw: str) -> Brief:
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise BriefParseError("no JSON object found")
    try:
        return Brief.model_validate(json.loads(text[start:end + 1]))
    except Exception as exc:
        raise BriefParseError("invalid brief structure") from exc


def _rules_result(evidence: dict, reason: str | None) -> BriefResult:
    b = rules_brief(evidence)
    return BriefResult(b, "rules", validate_text(flatten(b), evidence), None, reason,
                       datetime.now().strftime("%d %b %Y %H:%M"))


def generate_brief(evidence: dict, settings: Settings,
                   llm: Callable[[Settings, str, str], str] | None = None) -> BriefResult:
    check_privacy(evidence)
    if not settings.ai_enabled:
        return _rules_result(evidence, "No API key is configured, so the rule-based brief was generated.")
    llm = llm or call_llm
    brief = None
    for attempt in range(2):
        try:
            brief = parse_brief(llm(settings, SYSTEM_PROMPT, user_prompt(evidence, retry=attempt > 0)))
            break
        except BriefParseError:
            continue
        except AIError as exc:
            return _rules_result(evidence, f"{exc.user_message} A rule-based brief was generated instead.")
        except Exception:   # never surface raw errors: they could contain secrets
            return _rules_result(evidence, "The AI service failed unexpectedly. A rule-based brief was generated instead.")
    if brief is None:
        return _rules_result(evidence, "The AI reply could not be read. A rule-based brief was generated instead.")
    return BriefResult(brief, "ai", validate_text(flatten(brief), evidence), settings.openrouter_model, None,
                       datetime.now().strftime("%d %b %Y %H:%M"))