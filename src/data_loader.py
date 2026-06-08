# src/data_loader.py

import os
import pandas as pd
from typing import Tuple, Dict, List
from src.utils import RECTIFIER_LIMITS


def load_and_validate_data(file_path: str) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Loads the telecom sites dataset from Excel and performs validation checks.
    
    Returns:
        Tuple containing:
            - A pandas DataFrame of valid sites ready for optimization.
            - A list of dictionaries detailing the excluded sites and reasons.
    """
    exclusions = []
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found at: {file_path}")
        
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read the Excel file: {str(e)}")
        
    required_cols = [
        'No.', 'Site Name', 'Rectifier Type', 'Rectifier Capacity',
        'PV Capacity (Kw)', 'Battery Capacity (AH)', '2026 Average Monthly Bill',
        'Revised Average Load'
    ]
    
    # Check for missing required columns
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in dataset: {missing_cols}")
        
    cleaned_rows = []
    
    for index, row in df.iterrows():
        site_no = row['No.']
        site_name = row['Site Name']
        rectifier_type = row['Rectifier Type']
        rectifier_cap = row['Rectifier Capacity']
        pv_capacity = row['PV Capacity (Kw)']
        battery_ah = row['Battery Capacity (AH)']
        monthly_bill = row['2026 Average Monthly Bill']
        revised_load = row['Revised Average Load']
        
        reasons = []
        
        # 1. Validate Site ID
        if pd.isna(site_no) or pd.isna(site_name) or str(site_name).strip() == "":
            reasons.append("Missing Site ID or Site Name")
            
        # 2. Validate Rectifier Type
        if pd.isna(rectifier_type) or str(rectifier_type).strip() == "":
            reasons.append("Missing Rectifier Type")
        else:
            rectifier_type = str(rectifier_type).strip()
            if rectifier_type not in RECTIFIER_LIMITS:
                reasons.append(f"Unknown Rectifier Type '{rectifier_type}'")
                
        # 3. Validate Rectifier Capacity
        try:
            rectifier_cap = float(rectifier_cap)
            if pd.isna(rectifier_cap) or rectifier_cap <= 0:
                reasons.append(f"Invalid Rectifier Capacity: {rectifier_cap}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric Rectifier Capacity: {rectifier_cap}")
            
        # 4. Validate PV Capacity
        try:
            pv_capacity = float(pv_capacity)
            if pd.isna(pv_capacity) or pv_capacity < 0:
                reasons.append(f"Invalid Existing PV Capacity: {pv_capacity}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric Existing PV Capacity: {pv_capacity}")
            
        # 5. Validate Battery Capacity
        try:
            battery_ah = float(battery_ah)
            if pd.isna(battery_ah) or battery_ah < 0:
                reasons.append(f"Invalid Battery Capacity: {battery_ah}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric Battery Capacity: {battery_ah}")
            
        # 6. Validate Monthly Bill
        try:
            monthly_bill = float(monthly_bill)
            if pd.isna(monthly_bill) or monthly_bill < 0:
                reasons.append(f"Invalid 2026 Average Monthly Bill: {monthly_bill}")
        except (ValueError, TypeError):
            reasons.append(f"Non-numeric 2026 Average Monthly Bill: {monthly_bill}")
            
        # 7. Validate Revised Average Load
        # Handle string placeholder like '-'
        if isinstance(revised_load, str) and revised_load.strip() == '-':
            reasons.append("Revised Average Load is marked as '-' (missing)")
        else:
            try:
                revised_load = float(revised_load)
                if pd.isna(revised_load) or revised_load < 0:
                    reasons.append(f"Invalid Revised Average Load: {revised_load}")
                elif revised_load == 0:
                    # Let's check if load is exactly 0. If load is 0, the site is not consuming energy.
                    reasons.append("Revised Average Load is 0 (site inactive)")
            except (ValueError, TypeError):
                reasons.append(f"Non-numeric Revised Average Load: {revised_load}")

        # 8. Rectifier Constraint Check
        if not reasons and rectifier_type in RECTIFIER_LIMITS:
            max_limit = RECTIFIER_LIMITS[rectifier_type]
            if pv_capacity > max_limit:
                reasons.append(
                    f"Existing PV capacity ({pv_capacity} kWp) exceeds rectifier limit for {rectifier_type} ({max_limit} kWp)"
                )

        if reasons:
            exclusions.append({
                'No.': site_no if not pd.isna(site_no) else index,
                'Site Name': site_name if pd.notna(site_name) else "Unknown",
                'Rectifier Type': rectifier_type,
                'Rectifier Capacity': rectifier_cap,
                'PV Capacity (Kw)': pv_capacity,
                'Battery Capacity (AH)': battery_ah,
                '2026 Average Monthly Bill': monthly_bill,
                'Revised Average Load': row['Revised Average Load'],
                'Reason': "; ".join(reasons)
            })
        else:
            cleaned_rows.append({
                'No.': int(site_no),
                'Site Name': str(site_name).strip(),
                'Power_Source': str(row.get('Power_Source', 'Unknown')).strip(),
                'Single/Coloc': str(row.get('Single/Coloc', 'Unknown')).strip(),
                'Rectifier Type': rectifier_type,
                'Rectifier Capacity': float(rectifier_cap),
                'PV Capacity (Kw)': float(pv_capacity),
                'Battery Capacity (AH)': float(battery_ah),
                '2026 Average Monthly Bill': float(monthly_bill),
                'Revised Average Load': float(revised_load),
                # Copy other columns for reporting
                'Solar Expected Yield': float(row.get('Solar Expected Yield', 0.0)) if pd.notna(row.get('Solar Expected Yield')) else 0.0,
                'Battery Capacity (kWh)': float(row.get('Battery Capacity (kWh)', 0.0)) if pd.notna(row.get('Battery Capacity (kWh)')) else 0.0
            })
            
    valid_df = pd.DataFrame(cleaned_rows)
    return valid_df, exclusions
