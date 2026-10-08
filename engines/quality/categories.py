"""Detects spelling/format variants of the same category value (e.g. 'FIN OPS' vs 'Finance Ops')."""
import difflib
import re

import pandas as pd

_NUMBER_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
                 "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}
MAX_VARIANT_SHARE = 0.10   # a fuzzy variant must be rarer than 10% of its canonical value


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _tokens(value: str) -> list[str]:
    return [_NUMBER_WORDS.get(t, t) for t in re.findall(r"[a-z0-9]+", value.lower())]


def _subsequence(short: str, long_: str) -> bool:
    it = iter(long_)
    return all(ch in it for ch in short)


def _token_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 3:
        return False
    if a.startswith(b) or b.startswith(a):
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if short[0] == long_[0] and _subsequence(short, long_):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.88


def _similar(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta) == len(tb) and len(ta) > 0 and all(_token_match(x, y) for x, y in zip(ta, tb))


def find_variants(counts: pd.Series) -> tuple[dict[str, tuple[str, str]], list[tuple[str, str]]]:
    """counts: value -> number of records.

    Returns (mapping, review) where
      mapping: variant -> (canonical, kind) safe to apply; kind is 'format' or 'spelling'
      review:  (value, possible_match) pairs too uncertain to apply automatically
    """
    ordered = list(counts.sort_values(ascending=False).index)
    canonical: list[str] = []
    mapping: dict[str, tuple[str, str]] = {}
    review: list[tuple[str, str]] = []

    for value in ordered:
        fmt = [c for c in canonical if _key(value) == _key(c)]
        if len(fmt) == 1:
            mapping[value] = (fmt[0], "format")
            continue
        sim = [c for c in canonical if _similar(value, c)]
        if len(sim) == 1:
            if counts[value] <= MAX_VARIANT_SHARE * counts[sim[0]]:
                mapping[value] = (sim[0], "spelling")
            else:
                review.append((value, sim[0]))
                canonical.append(value)
        elif len(sim) > 1:
            review.append((value, " / ".join(sim)))
            canonical.append(value)
        else:
            canonical.append(value)
    return mapping, review