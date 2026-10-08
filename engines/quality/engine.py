"""Data Quality Engine. Safe fixes are applied and logged; risky items are only flagged for review."""
import re

import numpy as np
import pandas as pd

from engines.ingestion.profiler import detect_type
from engines.quality.categories import find_variants
from engines.quality.dates import parse_mixed_dates
from models.quality import AuditEntry, QualityResult

MAX_CATEGORY_VALUES = 60
OUTLIER_Z = 6.0


def _is_text(s: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def _tidy_headers(df, audit):
    new = {c: re.sub(r"\s+", " ", str(c)).strip() for c in df.columns}
    changed = {o: n for o, n in new.items() if o != n}
    if changed:
        df = df.rename(columns=new)
        audit.append(AuditEntry(
            "Structure", "Column names",
            "Some column names had stray spaces, which breaks matching and lookups.",
            "Removed leading/trailing/double spaces from column names.",
            len(changed), "applied",
            [f"'{o}' -> '{n}'" for o, n in changed.items()]))
    return df


def _tidy_whitespace(df, audit):
    for col in df.columns:
        s = df[col]
        if not _is_text(s):
            continue
        mask = s.notna()
        text = s[mask].astype(str)
        tidy = text.str.replace(r"\s+", " ", regex=True).str.strip()
        changed = text != tidy
        if changed.any():
            df.loc[tidy.index, col] = tidy
            audit.append(AuditEntry(
                "Text", col, "Values had extra spaces before, after, or inside the text.",
                "Trimmed the extra spaces. The wording itself was not changed.",
                int(changed.sum()), "applied",
                [f"'{o}' -> '{n}'" for o, n in list(dict.fromkeys(zip(text[changed], tidy[changed])))[:5]]))
    return df


def _normalise_categories(df, audit):
    for col in df.columns:
        s = df[col]
        if not _is_text(s) or detect_type(s) != "categorical":
            continue
        counts = s.value_counts()
        if len(counts) < 2 or len(counts) > MAX_CATEGORY_VALUES:
            continue
        mapping, review = find_variants(counts)
        if mapping:
            records = int(s.isin(list(mapping)).sum())
            df[col] = s.replace({v: c for v, (c, _) in mapping.items()})
            kinds = {k for _, (_, k) in mapping.items()}
            note = "capitalisation/spacing" if kinds == {"format"} else "spelling, abbreviation or capitalisation"
            audit.append(AuditEntry(
                "Categories", col,
                f"The same category was written {len(mapping) + df[col].nunique()} different ways "
                f"(differences in {note}).",
                f"Merged {len(mapping)} variant {'spelling' if len(mapping) == 1 else 'spellings'} into their standard value.",
                records, "applied",
                [f"'{v}' -> '{c}'  ({int(counts[v]):,} records)" for v, (c, _) in
                 sorted(mapping.items(), key=lambda kv: kv[1][0])]))
        for value, match in review:
            audit.append(AuditEntry(
                "Categories", col,
                f"'{value}' looks similar to '{match}' but is too common to merge without confirmation.",
                "Left unchanged. Confirm with the process owner whether these are the same.",
                int(counts[value]), "review"))
    return df


def _standardise_dates(df, audit):
    for col in df.columns:
        s = df[col]
        if not _is_text(s) or detect_type(s) != "datetime":
            continue
        parsed, info = parse_mixed_dates(s)
        df[col] = parsed
        if info["other_layout"] > 0:
            rule = info["rule"] or "undetermined"
            audit.append(AuditEntry(
                "Dates", col,
                f"Dates were stored in more than one layout ({info['iso']:,} as year-month-day and "
                f"{info['other_layout']:,} as day/month/year style). Reading them with one rule would "
                f"silently produce wrong dates.",
                "Converted every value to a real timestamp, resolving each one on its own evidence.",
                info["other_layout"], "applied",
                [f"Column rule for ambiguous values: {rule}",
                 "A part greater than 12 can only be a day, so those values were never guessed."]))
        else:
            audit.append(AuditEntry(
                "Dates", col, "Dates were stored as text.",
                "Converted to real timestamps so durations can be calculated.",
                info["total"], "applied"))
        if info["ambiguous"] > 0:
            audit.append(AuditEntry(
                "Dates", col,
                f"{info['ambiguous']:,} dates could be read as day/month or month/day.",
                f"Read using the column's dominant layout ({info['rule'] or 'none found'}). "
                f"Verify against the source system if exact dates matter.",
                info["ambiguous"], "review"))
        if info["unreadable"] > 0:
            audit.append(AuditEntry(
                "Dates", col, "Some values could not be read as dates.",
                "Set to blank. The original file is unchanged.", info["unreadable"], "applied"))
    return df


def _remove_duplicates(df, original, audit):
    mask = df.duplicated(keep="first")
    quarantined = df[mask].copy()
    if mask.any():
        raw_dupes = int(original.duplicated().sum())
        details = [f"Kept the first copy of each record. {int(mask.sum()):,} repeated rows set aside "
                   f"(not deleted from the audit trail)."]
        hidden = int(mask.sum()) - raw_dupes
        if hidden > 0:
            details.append(f"{hidden:,} of these only became identical after spelling and date "
                           f"fixes, so the raw file did not show them as duplicates.")
        audit.append(AuditEntry(
            "Duplicates", "All columns",
            "Identical records appeared more than once, which would double-count work.",
            "Removed repeated copies, keeping one.", int(mask.sum()), "applied",
            details, quarantined.head(10)))
    return df[~mask], quarantined


def _missing_report(df, audit):
    miss = df.isna().sum()
    miss = miss[miss > 0]
    if len(miss):
        audit.append(AuditEntry(
            "Missing", "Several columns",
            "Some fields are blank. Blanks can hide process steps or skew averages.",
            "Left blank. Values are never invented. Analyses will exclude blanks and say so.",
            int(miss.sum()), "review",
            [f"{c}: {int(n):,} blank ({n / len(df) * 100:.1f}%)" for c, n in miss.items()]))


def _impossible_durations(df, audit):
    dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    starts = [c for c in dt_cols if re.search(r"start|begin", c, re.I)]
    ends = [c for c in dt_cols if re.search(r"end|finish|complet", c, re.I)]
    if starts and ends:
        s, e = starts[0], ends[0]
        bad = df[e] < df[s]
        if bad.any():
            audit.append(AuditEntry(
                "Validity", f"{s} / {e}",
                "Some records finish before they start, which is impossible.",
                "Not changed. Recommend excluding these records from duration metrics.",
                int(bad.sum()), "review",
                [f"{bad.sum() / len(df) * 100:.1f}% of records"], df[bad].head(10)))


def _outliers(df, audit):
    for col in df.columns:
        s = df[col]
        if not pd.api.types.is_numeric_dtype(s) or s.nunique() < 20 or (s.dropna() <= 0).any():
            continue
        logs = np.log(s.dropna())
        med = logs.median()
        mad = (logs - med).abs().median() * 1.4826
        if mad == 0:
            continue
        z = (np.log(s) - med).abs() / mad
        flag = z > OUTLIER_Z
        if flag.any():
            audit.append(AuditEntry(
                "Outliers", col,
                f"Some '{col}' values are extremely far from typical (likely entry errors).",
                "Not changed. Review the listed records with the data owner.",
                int(flag.sum()), "review",
                [f"Typical value (median): {s.median():,.2f}", f"Largest value: {s.max():,.2f}"],
                df[flag].sort_values(col, ascending=False).head(10)))


def _naming_style(df, audit):
    def style(name):
        if "_" in name and name == name.lower():
            return "snake_case"
        if " " in name or name[:1].isupper():
            return "Title Case"
        return "other"
    styles = {c: style(c) for c in df.columns}
    if len(set(styles.values())) > 1:
        audit.append(AuditEntry(
            "Structure", "Column names", "Column names mix different naming styles.",
            "Not changed. Column mapping handles this automatically.",
            len(df.columns), "review", [f"{c}  ({st})" for c, st in styles.items()]))


def clean_dataset(df_in: pd.DataFrame) -> QualityResult:
    audit: list[AuditEntry] = []
    original = df_in.copy()
    work = df_in.copy()

    work = _tidy_headers(work, audit)
    original.columns = work.columns
    work = _tidy_whitespace(work, audit)
    work = _normalise_categories(work, audit)
    work = _standardise_dates(work, audit)
    work, quarantined = _remove_duplicates(work, original, audit)

    _missing_report(work, audit)
    _impossible_durations(work, audit)
    _outliers(work, audit)
    _naming_style(work, audit)

    return QualityResult(work, quarantined, audit, len(df_in), len(work))