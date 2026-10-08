\# Methodology



All thresholds live in code constants and are shown in the app's "How was this calculated?" panels.



\## Data quality

\- Headers and text: trim whitespace.

\- Categories: values are merged when they match after removing case and punctuation (always applied), or when they are token-wise similar (prefix, abbreviation, close spelling) \*\*and\*\* the variant is under 10% as frequent as the standard value. Larger look-alikes are sent for review, never merged.

\- Dates: ISO values are unambiguous. For `dd/mm/yyyy` style, a part greater than 12 must be the day. Only values where both parts are 12 or less are ambiguous, and they follow the column's majority layout and are flagged.

\- Duplicates are removed after the above fixes, so duplicates hidden by spelling differences are found. Removed rows are kept for audit.

\- Never changed, only flagged: blanks, records ending before they start, extreme values (robust z-score above 6 on the log scale), naming style.



\## Mapping

Each column gets a score per role from its name pattern and data shape (type, distinct values, repetition). Low scores are not guessed: the user is asked. Required roles are case ID, step and start time.



\## Process health

\- Cycle time = last step end minus first step start, over cases with valid timestamps.

\- SLA compliance = share of cases with cycle time at or below the SLA.

\- Rework = case has any step more than once. First-time-right = 1 minus rework.

\- Working time = end minus start of a step. Waiting time = start minus the previous step's end.



\## Bottlenecks

\- Time at step = waiting before + working at the step.

\- Frequency = share of cases where the step has the largest time at step. Severity = average time at step of at least 3x the typical step (and at least 1 hour).

\- Classes: Primary (frequent and severe), Frequent delay, Occasional severe delay, No bottleneck.

\- Confidence: High with 100 or more measured occurrences, Medium with 30 or more, otherwise Low. Capped at Medium without end times.

\- Likely cause is a rule-based hypothesis from waiting share and variability.



\## Root causes

Each factor is tested alone with a Kruskal-Wallis test. Effect size is epsilon-squared (share of variation explained): under 1% negligible, under 6% small, under 14% moderate, otherwise strong. Significance threshold is 0.01 divided by the number of factors tested (Bonferroni). Groups under 20 cases are ignored. Findings are observed facts. Explanations are labelled hypotheses.



\## Automation

\- Suitability (0-100) = 35% standardisation (next-step predictability and duration consistency) + 25% volume (log scale) + 25% low exception rate + 15% low case-by-case variability.

\- Exception rate = share of occurrences that repeat a step within a case, or exceed twice the step's median time.

\- Recommended type comes from a fixed decision table. Screens out low volume, conditional highly variable steps, and non-standard steps.

\- Priority = (w1 Impact + w2 Suitability + w3 Frequency + w4 TimeSaving - w5 Complexity - w6 Risk), rescaled to 0-100. Weights are editable. A per-opportunity table shows every contribution.



\## Impact simulator

Hours saved = occurrences per month x hands-on minutes x time reduction. Cost, payback and 3-year value follow from user assumptions. Cycle time and SLA are recalculated per case with reductions applied to that case's step times. A sensitivity table shows results at 50% to 125% of the assumed reduction.



\## AI grounding

The model receives only the evidence pack. Every number it writes is extracted and matched to the evidence within rounding tolerance. Untraceable figures are shown to the user. Exempt: 30/60/90-day labels, list numbering, and definitional constants.

