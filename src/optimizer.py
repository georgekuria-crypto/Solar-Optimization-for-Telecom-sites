# src/optimizer.py

import math
import pandas as pd
from typing import Dict, List, Tuple
from src.utils import (
    RECTIFIER_LIMITS,
    PEAK_SUN_HOURS,
    SYSTEM_EFFICIENCY,
    DAYS_IN_MONTH,
    TARIFF_KES,
    INSTALLED_COST_KES,
    PANEL_RATING_KWP,
    calculate_monthly_solar_production
)


def assess_existing_solar(pv_exist: float, monthly_energy: float) -> Dict:
    """
    Assesses whether the existing solar capacity is under-sized, adequately sized,
    near optimum, or over-sized compared to the monthly energy consumption.
    
    Target capacity is the solar capacity needed to cover 100% of the site's energy:
        PV_target = Monthly Energy / 132
    """
    # 1 kWp produces 132 kWh/month
    pv_target = monthly_energy / 132.0 if monthly_energy > 0 else 0.0
    
    if pv_target == 0:
        return {
            'ratio': 0.0,
            'category': 'No Load / Inactive',
            'pv_target': 0.0,
            'justification': "Site has no energy consumption load."
        }
        
    ratio = pv_exist / pv_target
    
    if ratio > 1.1:
        category = 'Over-sized'
        explanation = "exceeds the site's energy consumption by more than 10% (excess solar will be wasted without batteries)."
    elif 0.9 <= ratio <= 1.1:
        category = 'Near optimum'
        explanation = "is well balanced and covers approximately 90% to 110% of the site's monthly energy consumption."
    elif 0.7 <= ratio < 0.9:
        category = 'Adequately sized'
        explanation = "covers 70% to 90% of the site's consumption. It is well-sized but has slight room for expansion if rectifier capacity allows."
    else:
        category = 'Under-sized'
        explanation = "is less than 70% of the target capacity, meaning the site relies heavily on the grid and could benefit from expansion."
        
    justification = (
        f"Existing solar of {pv_exist:.2f} kWp is {ratio*100:.1f}% of the target solar capacity "
        f"({pv_target:.2f} kWp) needed to cover the {monthly_energy:.1f} kWh monthly site consumption. "
        f"This asset size is categorized as **{category}** because it {explanation}"
    )
    
    return {
        'ratio': ratio,
        'category': category,
        'pv_target': pv_target,
        'justification': justification
    }


def generate_scenarios(row: pd.Series) -> List[Dict]:
    """
    Generates all possible solar panel expansion scenarios for a site.
    Scenarios range from 0 additional panels up to the maximum rectifier limit.
    """
    site_name = row['Site Name']
    rectifier_type = row['Rectifier Type']
    rectifier_cap = RECTIFIER_LIMITS.get(rectifier_type, 12.0)
    pv_exist = row['PV Capacity (Kw)']
    
    # Calculate energy demand
    avg_load = row['Revised Average Load']
    daily_energy = avg_load * 24.0
    monthly_energy = daily_energy * 30.0
    
    # Existing solar offset calculations
    exist_solar_gen = calculate_monthly_solar_production(pv_exist)
    exist_offset = min(exist_solar_gen, monthly_energy)
    exist_bill = (monthly_energy - exist_offset) * TARIFF_KES
    
    # Maximum additional capacity possible under the rectifier limit
    available_headroom = rectifier_cap - pv_exist
    if available_headroom <= 0:
        n_max = 0
    else:
        # Round down since we cannot exceed the rectifier limit
        n_max = int(math.floor(available_headroom / PANEL_RATING_KWP))
        
    scenarios = []
    
    for n in range(0, n_max + 1):
        add_pv = n * PANEL_RATING_KWP
        total_pv = pv_exist + add_pv
        rectifier_util = (total_pv / rectifier_cap) * 100.0 if rectifier_cap > 0 else 0.0
        
        # Technical calculations
        daily_solar_gen = total_pv * PEAK_SUN_HOURS * SYSTEM_EFFICIENCY
        monthly_solar_gen = daily_solar_gen * 30.0
        solar_contrib = (monthly_solar_gen / monthly_energy) * 100.0 if monthly_energy > 0 else 0.0
        
        # Capped monthly energy offset (cannot exceed site load)
        total_offset = min(monthly_solar_gen, monthly_energy)
        
        # Financial calculations
        # Total monthly savings from ALL solar
        total_monthly_savings = total_offset * TARIFF_KES
        
        # Additional monthly savings from the expansion panels
        add_monthly_offset = total_offset - exist_offset
        add_monthly_savings = add_monthly_offset * TARIFF_KES
        add_annual_savings = add_monthly_savings * 12.0
        
        capex = n * INSTALLED_COST_KES
        
        # Payback & ROI are based on the expansion CAPEX and additional savings
        if n == 0:
            roi = 0.0
            payback = 0.0
        else:
            roi = (add_annual_savings / capex) * 100.0 if capex > 0 else 0.0
            payback = capex / add_annual_savings if add_annual_savings > 0 else float('inf')
            
        scenarios.append({
            'scenario_id': n,
            'panels_added': n,
            'additional_pv_kwp': add_pv,
            'total_pv_kwp': total_pv,
            'rectifier_utilization': rectifier_util,
            'daily_solar_production_kwh': daily_solar_gen,
            'monthly_solar_production_kwh': monthly_solar_gen,
            'solar_contribution_pct': solar_contrib,
            'monthly_energy_offset_kwh': total_offset,
            'additional_monthly_savings_kes': add_monthly_savings,
            'additional_annual_savings_kes': add_annual_savings,
            'capex_kes': capex,
            'roi_pct': roi,
            'payback_years': payback,
            'new_monthly_grid_bill_kes': (monthly_energy - total_offset) * TARIFF_KES
        })
        
    return scenarios


def optimize_site(row: pd.Series) -> Tuple[Dict, List[Dict]]:
    """
    Evaluates all scenarios and selects the financially optimal solar expansion plan.
    
    The optimal plan is defined as:
    1. Maximum savings.
    2. If multiple scenarios achieve the same savings (meaning load is fully offset),
       choose the one with the lowest CAPEX (highest ROI/fastest payback).
    """
    scenarios = generate_scenarios(row)
    
    # If no expansion is possible, the recommended option is 0 panels added (scenario 0)
    if len(scenarios) <= 1:
        return scenarios[0], scenarios
        
    # Find the maximum additional annual savings achieved
    max_savings = max(s['additional_annual_savings_kes'] for s in scenarios)
    
    # Filter scenarios that achieve this max savings (to within KES 1 to avoid float issues)
    optimal_candidates = [s for s in scenarios if abs(s['additional_annual_savings_kes'] - max_savings) < 1.0]
    
    # Among those candidates, choose the one with the minimum CAPEX (i.e. fewest panels added)
    # This prevents recommending oversized solar that wastes capital
    recommended_scenario = min(optimal_candidates, key=lambda s: s['capex_kes'])
    
    # If the maximum savings is 0 (i.e. existing solar already covers 100% of consumption),
    # then the recommended expansion is 0 panels.
    if max_savings == 0:
        recommended_scenario = scenarios[0]
        
    return recommended_scenario, scenarios


def get_justification(row: pd.Series, recommended: Dict, assessment: Dict) -> str:
    """
    Generates a technical/financial justification narrative for the recommendation.
    """
    pv_exist = row['PV Capacity (Kw)']
    rectifier_type = row['Rectifier Type']
    rectifier_cap = RECTIFIER_LIMITS[rectifier_type]
    
    # If no panels added
    if recommended['panels_added'] == 0:
        if assessment['ratio'] >= 1.0:
            return (
                f"No solar expansion is recommended for {row['Site Name']}. "
                f"The existing solar capacity ({pv_exist:.2f} kWp) is already **{assessment['category']}** "
                f"and fully offsets the site's energy demand ({row['Revised Average Load'] * 720:.1f} kWh/month). "
                f"Adding panels would result in a 0% return on investment as the excess generation cannot be utilized."
            )
        else:
            return (
                f"No solar expansion is recommended because the existing capacity ({pv_exist:.2f} kWp) "
                f"is at the maximum capacity limit of the {rectifier_type} rectifier ({rectifier_cap:.2f} kWp). "
                f"Further expansion is physically restricted by the site rectifier capacity."
            )
            
    # If panels are added
    justification = (
        f"Recommend adding **{recommended['panels_added']} panels** (+{recommended['additional_pv_kwp']:.2f} kWp) "
        f"for a total solar capacity of **{recommended['total_pv_kwp']:.2f} kWp**. "
        f"This expansion will increase rectifier capacity utilization from {(pv_exist/rectifier_cap)*100:.1f}% to {recommended['rectifier_utilization']:.1f}%, "
        f"which is safely within the {rectifier_cap:.2f} kWp limit for a {rectifier_type} rectifier. "
        f"This investment requires a CAPEX of **KES {recommended['capex_kes']:,.2f}** and is expected to deliver "
        f"an additional **KES {recommended['additional_monthly_savings_kes']:,.2f}** in monthly savings "
        f"(**KES {recommended['additional_annual_savings_kes']:,.2f}** annually). "
        f"This achieves an exceptional **ROI of {recommended['roi_pct']:.1f}%** with a very short "
        f"payback period of **{recommended['payback_years']:.2f} years** ({int(recommended['payback_years']*12)} months). "
    )
    
    # Check if this expansion brings the site to near 100% solar offset
    if recommended['solar_contribution_pct'] >= 95.0:
        justification += "This sizing will allow the site to cover almost all of its daily energy consumption using solar power during peak sun hours."
    else:
        justification += (
            f"This will increase the solar contribution from {(pv_exist*132/(row['Revised Average Load']*720))*100:.1f}% "
            f"to {recommended['solar_contribution_pct']:.1f}% of the site load, leaving some remaining load to be covered by the grid. "
            f"Further expansion is limited by the {rectifier_type} rectifier capacity limit of {rectifier_cap} kWp."
            if recommended['total_pv_kwp'] >= rectifier_cap - 0.1 else 
            f"Further solar expansion is not recommended as it would exceed the site's daily energy consumption, wasting generation."
        )
        
    return justification
