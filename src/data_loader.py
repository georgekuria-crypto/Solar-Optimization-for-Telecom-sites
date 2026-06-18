# src/data_loader.py

import os
import pandas as pd
from typing import Tuple, Dict, List
from src.utils import RECTIFIER_LIMITS


def load_and_validate_data(file_path: str) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Loads the telecom sites dataset from Excel and performs validation checks.

    A site is excluded if it has ANY of the following critical issues:
      - Missing Site ID or Site Name
      - Missing or unknown Rectifier Type
      - Invalid or zero Rectifier Capacity
      - Negative or non-numeric Existing PV Capacity
      - Invalid Battery Capacity
      - Zero, negative, or missing 2026 Average Monthly Bill
        (zero bill means no billing baseline exists — site cannot be optimised)
      - Zero, negative, missing, or non-numeric Revised Average Load
        (load is the sole energy model input)
      - Existing PV already exceeds the rectifier limit

    Returns:
        Tuple of:
            - valid_df  : DataFrame of clean sites ready for optimisation.
            - exclusions: List of dicts describing every excluded site and its reasons.
    """
    exclusions: List[Dict] = []

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found at: {file_path}")

    try:
        df = pd.read_excel(file_path)
    except Exception as exc:
        raise ValueError(f"Failed to read Excel file: {exc}") from exc

    required_cols = [
        'No.', 'Site Name', 'Rectifier Type', 'Rectifier Capacity',
        'PV Capacity (Kw)', 'Battery Capacity (AH)',
        '2026 Average Monthly Bill', 'Revised Average Load', 'PV Rating'
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in dataset: {missing_cols}")

    cleaned_rows: List[Dict] = []

    for index, row in df.iterrows():
        raw_no        = row['No.']
        raw_name      = row['Site Name']
        raw_rect_type = row['Rectifier Type']
        raw_rect_cap  = row['Rectifier Capacity']
        raw_pv        = row['PV Capacity (Kw)']
        raw_bat       = row['Battery Capacity (AH)']
        raw_pv_rating = row.get('PV Rating')
        raw_bill      = row['2026 Average Monthly Bill']
        raw_load      = row['Revised Average Load']

        reasons: List[str] = []

        # ── 1. Site ID ──────────────────────────────────────────────────────────
        if pd.isna(raw_no) or pd.isna(raw_name) or str(raw_name).strip() == '':
            reasons.append("Missing Site ID or Site Name")

        # ── 2. Rectifier Type ───────────────────────────────────────────────────
        if pd.isna(raw_rect_type) or str(raw_rect_type).strip() == '':
            reasons.append("Missing Rectifier Type")
            rect_type = str(raw_rect_type)
        else:
            rect_type = str(raw_rect_type).strip()
            if rect_type not in RECTIFIER_LIMITS:
                reasons.append(f"Unknown Rectifier Type '{rect_type}'")

        # ── 3. Rectifier Capacity ───────────────────────────────────────────────
        try:
            rect_cap = float(raw_rect_cap)
            if pd.isna(rect_cap) or rect_cap <= 0:
                reasons.append(f"Invalid Rectifier Capacity: {raw_rect_cap}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric Rectifier Capacity: {raw_rect_cap}")
            rect_cap = 0.0

        # ── 4. Existing PV Capacity ─────────────────────────────────────────────
        try:
            pv_cap = float(raw_pv)
            if pd.isna(pv_cap) or pv_cap < 0:
                reasons.append(f"Invalid Existing PV Capacity: {raw_pv}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric Existing PV Capacity: {raw_pv}")
            pv_cap = -1.0

        # ── 5. Battery Capacity ─────────────────────────────────────────────────
        try:
            bat_ah = float(raw_bat)
            if pd.isna(bat_ah) or bat_ah < 0:
                reasons.append(f"Invalid Battery Capacity: {raw_bat}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric Battery Capacity: {raw_bat}")
            bat_ah = 0.0

        # ── 5.5 PV Rating ───────────────────────────────────────────────────────
        try:
            pv_rating_w = float(raw_pv_rating)
            if pd.isna(pv_rating_w) or pv_rating_w <= 0:
                reasons.append(f"Invalid PV Rating: {raw_pv_rating}")
                pv_rating_kwp = 0.575 # fallback
            else:
                pv_rating_kwp = pv_rating_w / 1000.0
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric PV Rating: {raw_pv_rating}")
            pv_rating_kwp = 0.575  # fallback

        # ── 6. 2026 Average Monthly Bill (CRITICAL BASELINE) ────────────────────
        # A zero or negative bill means no billing data exists for this site.
        # Without a real billing baseline we cannot calculate savings or ROI.
        try:
            monthly_bill = float(raw_bill)
            if pd.isna(monthly_bill):
                reasons.append("Missing 2026 Average Monthly Bill")
            elif monthly_bill <= 0:
                reasons.append(
                    f"2026 Average Monthly Bill is {monthly_bill:.2f} KES "
                    "(zero or negative bill — no billing baseline for savings calculation)"
                )
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric 2026 Average Monthly Bill: {raw_bill}")
            monthly_bill = 0.0

        # ── 7. Revised Average Load (CRITICAL ENERGY INPUT) ────────────────────
        # This is the sole load metric.  A missing or zero value means we have no
        # energy model for the site.
        if isinstance(raw_load, str) and raw_load.strip() == '-':
            reasons.append("Revised Average Load is marked as '-' (missing)")
            revised_load = 0.0
        else:
            try:
                revised_load = float(raw_load)
                if pd.isna(revised_load):
                    reasons.append("Revised Average Load is missing (NaN)")
                elif revised_load <= 0:
                    reasons.append(
                        f"Revised Average Load is {revised_load} kW "
                        "(zero or negative — site has no measurable energy demand)"
                    )
            except (ValueError, TypeError):
                reasons.append(f"Non-numeric Revised Average Load: {raw_load}")
                revised_load = 0.0

        # ── 8. Rectifier capacity constraint ───────────────────────────────────
        if not reasons and rect_type in RECTIFIER_LIMITS and pv_cap >= 0:
            max_limit = RECTIFIER_LIMITS[rect_type]
            if pv_cap > max_limit:
                reasons.append(
                    f"Existing PV ({pv_cap} kWp) exceeds rectifier limit "
                    f"for {rect_type} ({max_limit} kWp)"
                )

        # ── Route to exclusions or cleaned set ─────────────────────────────────
        if reasons:
            exclusions.append({
                'No.':                       raw_no if not pd.isna(raw_no) else index,
                'Site Name':                 raw_name if pd.notna(raw_name) else 'Unknown',
                'Rectifier Type':            raw_rect_type,
                'Rectifier Capacity':        raw_rect_cap,
                'PV Capacity (Kw)':          raw_pv,
                'PV Rating':                 raw_pv_rating,
                'Battery Capacity (AH)':     raw_bat,
                '2026 Average Monthly Bill': raw_bill,
                'Revised Average Load':      raw_load,
                'Reason':                    '; '.join(reasons),
            })
        else:
            cleaned_rows.append({
                'No.':                       int(raw_no),
                'Site Name':                 str(raw_name).strip(),
                'Power_Source':              str(row.get('Power_Source', 'Unknown')).strip(),
                'Single/Coloc':              str(row.get('Single/Coloc', 'Unknown')).strip(),
                'Rectifier Type':            rect_type,
                'Rectifier Capacity':        float(rect_cap),
                'PV Capacity (Kw)':          float(pv_cap),
                'Panel Rating (kWp)':        float(pv_rating_kwp),
                'Battery Capacity (AH)':     float(bat_ah),
                '2026 Average Monthly Bill': float(monthly_bill),
                'Revised Average Load':      float(revised_load),
                'Solar Expected Yield':      (
                    float(row['Solar Expected Yield'])
                    if pd.notna(row.get('Solar Expected Yield')) else 0.0
                ),
                'Battery Capacity (kWh)':    (
                    float(row['Battery Capacity (kWh)'])
                    if pd.notna(row.get('Battery Capacity (kWh)')) else 0.0
                ),
            })

    valid_df = pd.DataFrame(cleaned_rows)
    return valid_df, exclusions
