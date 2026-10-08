"""Number-grounding check: every figure the AI writes must be traceable to the evidence pack."""
import re
from dataclasses import dataclass, field

_NUM = re.compile(r"(?<![A-Za-z_])\$?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(%|[kKmM](?![A-Za-z]))?")
_EXEMPT = [
    r"\b(30|60|90)\s?[- ]\s?day", r"\bdays?\s+(30|60|90)\b", r"\b30\s?/\s?60\s?/\s?90\b",
    r"(?m)^\s*\d+[.)]\s", r"\bphase\s+\d+", r"\b(30|60|90)\s+days\b",
]


DEFINITIONAL = {10.0, 100.0}


@dataclass
class Validation:
    total: int
    supported: int
    unsupported: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return 1.0 if self.total == 0 else self.supported / self.total

    @property
    def ok(self) -> bool:
        return not self.unsupported


def _value(num: str, suffix: str | None) -> float:
    v = float(num.replace(",", ""))
    if suffix and suffix.lower() == "k":
        v *= 1_000
    elif suffix and suffix.lower() == "m":
        v *= 1_000_000
    return v


def extract_numbers(text: str) -> list[tuple[str, float]]:
    for pattern in _EXEMPT:
        text = re.sub(pattern, " ", text, flags=re.I)
    return [(m.group(0).strip(), _value(m.group(1), m.group(2))) for m in _NUM.finditer(text)]


def allowed_numbers(evidence) -> set[float]:
    out: set[float] = set()

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            out.add(float(x))
        elif isinstance(x, str):
            out.update(v for _, v in extract_numbers(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(evidence)
    out |= {abs(a) for a in list(out)}                    # a loss may be written without its minus sign
    out |= {a / 24 for a in list(out) if a >= 24}      # hours quoted as days
    out |= DEFINITIONAL                                  # "the slowest 10%" is a definition, not a finding
    return out


def _supported(x: float, allowed: set[float]) -> bool:
    for a in allowed:
        if abs(x - a) <= max(0.06, 0.01 * abs(a)):
            return True
        if any(round(a, nd) == x for nd in (0, 1, 2)):
            return True
    return False


def validate_text(text: str, evidence: dict) -> Validation:
    allowed = allowed_numbers(evidence)
    found = extract_numbers(text)
    bad = [raw for raw, v in found if not _supported(v, allowed)]
    return Validation(len(found), len(found) - len(bad), list(dict.fromkeys(bad)))