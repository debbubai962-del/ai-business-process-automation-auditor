"""Synthetic invoice-processing event log generator.

Creates two files in sample_data/:
  - invoice_process_clean.csv   (ground-truth quality data)
  - invoice_process_messy.csv   (same data with deliberate quality problems)

A fixed random seed makes the output reproducible, so tests can rely on it.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_CASES = 5000
OUT_DIR = Path(__file__).parent

rng = np.random.default_rng(SEED)

DEPARTMENTS = ["Finance Ops", "Procurement", "Logistics", "Operations"]
DEPT_WEIGHTS = [0.35, 0.25, 0.20, 0.20]
VENDOR_TYPES = ["Established", "New"]
PRIORITIES = ["Low", "Medium", "High"]
SLA_HOURS = 72  # 3 days end to end

# Mean working duration per step in hours: (mean, sigma of lognormal)
STEP_PROFILE = {
    "Invoice Received": (0.2, 0.3),
    "Data Entry": (1.5, 0.35),
    "Three-Way Match": (2.0, 0.40),
    "Manager Approval": (20.0, 0.60),
    "Exception Review": (14.0, 1.00),
    "Payment Release": (0.3, 0.30),
}

TEAMS = {
    "Finance Ops": ["FinOps-A", "FinOps-B", "FinOps-C"],
    "Procurement": ["Proc-A", "Proc-B"],
    "Logistics": ["Log-A", "Log-B"],
    "Operations": ["Ops-A", "Ops-B", "Ops-C"],
}


def lognormal_hours(mean_hours: float, sigma: float) -> float:
    """Draw a positive duration whose average is close to mean_hours."""
    mu = np.log(mean_hours) - (sigma**2) / 2
    return float(rng.lognormal(mu, sigma))


def build_case(case_num: int, start: pd.Timestamp) -> list[dict]:
    dept = rng.choice(DEPARTMENTS, p=DEPT_WEIGHTS)
    vendor = rng.choice(VENDOR_TYPES, p=[0.8, 0.2])
    priority = rng.choice(PRIORITIES, p=[0.3, 0.5, 0.2])
    amount = round(float(rng.lognormal(7.0, 0.9)), 2)
    team = rng.choice(TEAMS[dept])
    case_id = f"INV-{100000 + case_num}"

    # Planted effects
    approval_mult = 1.0
    if dept == "Finance Ops":
        approval_mult *= 1.8
    if start.dayofweek in (0, 4):  # Monday, Friday
        approval_mult *= 1.4
    if priority == "High":
        approval_mult *= 0.6

    rework_prob = 0.12 + (0.10 if vendor == "New" else 0.0)
    has_rework = rng.random() < rework_prob
    has_exception = rng.random() < (0.10 + (0.08 if amount > 3000 else 0.0))

    sequence = ["Invoice Received", "Data Entry", "Three-Way Match"]
    if has_rework:
        sequence += ["Data Entry", "Three-Way Match"]
    sequence += ["Manager Approval"]
    if has_exception:
        sequence += ["Exception Review"]
    sequence += ["Payment Release"]

    events = []
    clock = start
    for step in sequence:
        mean, sigma = STEP_PROFILE[step]
        if step == "Manager Approval":
            mean *= approval_mult
        processing = lognormal_hours(mean, sigma)
        # Waiting before the step starts (queue time)
        wait_mean = {"Manager Approval": 10.0, "Exception Review": 6.0}.get(step, 0.5)
        if step == "Manager Approval":
            wait_mean *= approval_mult
        wait = lognormal_hours(wait_mean, 0.5)

        step_start = clock + pd.Timedelta(hours=wait)
        step_end = step_start + pd.Timedelta(hours=processing)
        events.append(
            {
                "Invoice ID": case_id,
                "Activity": step,
                "Start Time": step_start,
                "End Time": step_end,
                "Department": dept,
                "Team": team,
                "Priority": priority,
                "Vendor Type": vendor,
                "Invoice Amount": amount,
                "SLA Hours": SLA_HOURS,
                "Status": "Completed",
            }
        )
        clock = step_end
    return events


def generate_clean() -> pd.DataFrame:
    rows: list[dict] = []
    base = pd.Timestamp("2025-01-06 08:00")  # a Monday
    for i in range(N_CASES):
        day_offset = int(rng.integers(0, 180))
        hour_offset = float(rng.uniform(0, 9))
        start = base + pd.Timedelta(days=day_offset, hours=hour_offset)
        # Skip weekends: push to Monday
        while start.dayofweek >= 5:
            start += pd.Timedelta(days=1)
        rows.extend(build_case(i, start))
    df = pd.DataFrame(rows)
    return df.sort_values(["Invoice ID", "Start Time"]).reset_index(drop=True)


def make_messy(clean: pd.DataFrame) -> pd.DataFrame:
    """Inject realistic data-quality problems into a copy of the clean data."""
    df = clean.copy()
    n = len(df)

    # Keep the true start times as real datetimes so later steps never re-parse text
    true_start = clean["Start Time"].copy()

    # Convert times to strings so we can mix formats
    df["Start Time"] = true_start.dt.strftime("%Y-%m-%d %H:%M:%S")
    df["End Time"] = clean["End Time"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Mixed date formats on ~6% of start times (day/month/year)
    idx = rng.choice(n, size=int(n * 0.06), replace=False)
    df.loc[idx, "Start Time"] = true_start.loc[idx].dt.strftime("%d/%m/%Y %H:%M")

    # 2. Inconsistent department names on ~8% of rows
    variants = {
        "Finance Ops": ["finance ops", "FIN OPS", "Finance Operations", " Finance Ops "],
        "Procurement": ["procurement", "PROCUREMENT", "Procurment"],
        "Logistics": ["logistics", "LOGISTICS", "Logistic"],
        "Operations": ["operations", "OPS", "Operation"],
    }
    idx = rng.choice(n, size=int(n * 0.08), replace=False)
    for i in idx:
        original = df.at[i, "Department"]
        df.at[i, "Department"] = rng.choice(variants[original])

    # 3. Inconsistent activity names on ~4% of rows
    act_variants = {
        "Data Entry": ["data entry", "Data entry", "DATA ENTRY"],
        "Three-Way Match": ["3-way match", "Three Way Match", "three-way match"],
        "Manager Approval": ["manager approval", "Mgr Approval", "Manager approval"],
    }
    idx = rng.choice(n, size=int(n * 0.04), replace=False)
    for i in idx:
        original = df.at[i, "Activity"]
        if original in act_variants:
            df.at[i, "Activity"] = rng.choice(act_variants[original])

    # 4. Missing values
    for col, frac in [("Department", 0.02), ("Priority", 0.03), ("Invoice Amount", 0.02), ("Team", 0.02)]:
        idx = rng.choice(n, size=int(n * frac), replace=False)
        df.loc[idx, col] = np.nan

    # 5. Impossible timestamps: End before Start on ~1% of rows
    idx = rng.choice(n, size=int(n * 0.01), replace=False)
    df.loc[idx, "End Time"] = (true_start.loc[idx] - pd.Timedelta(hours=5)).dt.strftime("%Y-%m-%d %H:%M:%S")

    # 6. Extreme outlier amounts (data entry mistakes) on ~0.3% of rows
    idx = rng.choice(n, size=int(n * 0.003), replace=False)
    df.loc[idx, "Invoice Amount"] = df.loc[idx, "Invoice Amount"] * 1000

    # 7. Exact duplicate rows (~2%)
    dupes = df.sample(frac=0.02, random_state=SEED)
    df = pd.concat([df, dupes], ignore_index=True)

    # 8. Inconsistent column naming and a status typo
    df = df.rename(columns={"Invoice ID": "invoice_id", "Start Time": "Start time ", "SLA Hours": "SLA_hours"})
    idx = rng.choice(len(df), size=int(len(df) * 0.01), replace=False)
    df.loc[idx, "Status"] = "complted"

    return df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def main() -> None:
    clean = generate_clean()
    messy = make_messy(clean)

    clean_path = OUT_DIR / "invoice_process_clean.csv"
    messy_path = OUT_DIR / "invoice_process_messy.csv"
    clean.to_csv(clean_path, index=False)
    messy.to_csv(messy_path, index=False)

    print(f"Clean file : {clean_path.name}  ({len(clean):,} events, {clean['Invoice ID'].nunique():,} cases)")
    print(f"Messy file : {messy_path.name}  ({len(messy):,} rows)")


if __name__ == "__main__":
    main()