# src/optimizer.py

import math
import pandas as pd
from typing import Dict, List, Tuple
from src.utils import (
    RECTIFIER_LIMITS,
    PEAK_SUN_HOURS,
    SYSTEM_EFFICIENCY,
    TARIFF_KES,
    INSTALLED_COST_KES,
    PANEL_RATING_KWP,
    calculate_monthly_solar_production,
)


# Monthly kWh produced per kWp  (5.5 PSH × 0.80 eff × 30 days)
KWH_PER_KWP_MONTH = PEAK_SUN_HOURS * SYSTEM_EFFICIENCY * 30  # = 132


def assess_existing_solar(pv_exist: float, monthly_energy: float) -> Dict:
    """
    Categorises the existing solar capacity relative to the site's monthly
    energy demand (derived from Revised Average Load × 720 h).

    Categories:
        Under-sized    – pv_exist < 70 % of target
        Adequately sized – 70 % ≤ pv_exist < 90 %
        Near optimum   – 90 % ≤ pv_exist ≤ 110 %
        Over-sized     – pv_exist > 110 % of target
    """
    pv_target = monthly_energy / KWH_PER_KWP_MONTH if monthly_energy > 0 else 0.0

    if pv_target == 0:
        return {
            'ratio': 0.0,
            'category': 'No Load / Inactive',
            'pv_target': 0.0,
            'justification': "Site has no measurable energy consumption load.",
        }

    ratio = pv_exist / pv_target

    if ratio > 1.1:
        category = 'Over-sized'
        explanation = (
            "exceeds the site's total energy consumption by more than 10%. "
            "Excess generation cannot be utilised without additional battery storage."
        )
    elif 0.9 <= ratio <= 1.1:
        category = 'Near optimum'
        explanation = (
            "covers approximately 90 %–110 % of the site's monthly energy consumption — "
            "well balanced for the current load."
        )
    elif 0.7 <= ratio < 0.9:
        category = 'Adequately sized'
        explanation = (
            "covers 70 %–90 % of consumption. Slightly under target but may have room "
            "for expansion if rectifier headroom allows."
        )
    else:
        category = 'Under-sized'
        explanation = (
            "covers less than 70 % of the target capacity. The site relies heavily on "
            "grid power and would benefit significantly from expansion."
        )

    justification = (
        f"Existing solar of {pv_exist:.2f} kWp is {ratio * 100:.1f}% of the "
        f"{pv_target:.2f} kWp target needed to cover the site's "
        f"{monthly_energy:.1f} kWh monthly demand. "
        f"This asset is categorised as **{category}** — it {explanation}"
    )

    return {
        'ratio': ratio,
        'category': category,
        'pv_target': pv_target,
        'justification': justification,
    }


def generate_scenarios(row: pd.Series) -> List[Dict]:
    """
    Generates every feasible solar panel expansion scenario for a site,
    from 0 additional panels up to the maximum allowed by the rectifier limit.

    Financial baseline
    ------------------
    The **2026 Average Monthly Bill** is the primary financial baseline.
    This figure already reflects the effect of the existing solar panels
    (i.e. it is the net grid bill the site currently pays).

    Savings from adding N new panels are calculated against this actual bill:
        current_grid_energy (kWh) = Actual Bill / Tariff
        additional_gen (kWh)      = N × panel_kWp × 132   (capped at current_grid_energy)
        actual_monthly_savings    = additional_gen_capped × Tariff
        actual_new_bill           = Actual Bill − actual_monthly_savings

    Secondary metric (for reference)
    ----------------------------------
    A calculated bill is derived from the full energy model:
        monthly_energy (kWh) = Revised Average Load × 720
        total_solar_gen      = total_pv × 132
        calc_offset          = min(total_solar_gen, monthly_energy)
        calculated_bill      = (monthly_energy − calc_offset) × Tariff
    """
    rectifier_type = row['Rectifier Type']
    rectifier_cap  = RECTIFIER_LIMITS.get(rectifier_type, 12.0)
    pv_exist       = row['PV Capacity (Kw)']

    # ── Energy model (from Revised Average Load) ──────────────────────────────
    avg_load       = row['Revised Average Load']          # kW
    monthly_energy = avg_load * 24.0 * 30.0              # kWh / month

    # Existing solar production (for energy model display)
    exist_solar_gen = pv_exist * KWH_PER_KWP_MONTH       # kWh / month
    exist_offset    = min(exist_solar_gen, monthly_energy)

    # ── Actual bill baseline ──────────────────────────────────────────────────
    actual_bill             = row['2026 Average Monthly Bill']   # KES (current, net of existing solar)
    current_grid_energy     = actual_bill / TARIFF_KES            # kWh currently bought from grid

    # ── Rectifier headroom ────────────────────────────────────────────────────
    available_headroom = rectifier_cap - pv_exist
    n_max = (
        int(math.floor(available_headroom / PANEL_RATING_KWP))
        if available_headroom > 0 else 0
    )

    scenarios: List[Dict] = []

    for n in range(0, n_max + 1):
        add_pv    = n * PANEL_RATING_KWP
        total_pv  = pv_exist + add_pv
        rect_util = (total_pv / rectifier_cap) * 100.0 if rectifier_cap > 0 else 0.0

        # ── Energy model (technical display) ─────────────────────────────────
        total_solar_gen  = total_pv * KWH_PER_KWP_MONTH          # kWh / month
        solar_contrib    = (
            (total_solar_gen / monthly_energy) * 100.0
            if monthly_energy > 0 else 0.0
        )
        total_offset     = min(total_solar_gen, monthly_energy)   # capped at site load
        calculated_bill  = (monthly_energy - total_offset) * TARIFF_KES  # secondary

        # ── Primary financial metrics (vs. actual bill baseline) ─────────────
        if n == 0:
            # Baseline scenario – no new investment
            actual_monthly_savings = 0.0
            actual_annual_savings  = 0.0
            actual_new_bill        = actual_bill
            capex                  = 0.0
            roi                    = 0.0
            payback                = 0.0
        else:
            # Generation from new panels only
            new_panel_gen = add_pv * KWH_PER_KWP_MONTH           # kWh / month
            # Cap: cannot save more than what is currently bought from the grid
            gen_applied_to_bill    = min(new_panel_gen, current_grid_energy)
            actual_monthly_savings = gen_applied_to_bill * TARIFF_KES
            actual_annual_savings  = actual_monthly_savings * 12.0
            actual_new_bill        = actual_bill - actual_monthly_savings

            capex   = n * INSTALLED_COST_KES
            roi     = (actual_annual_savings / capex) * 100.0 if capex > 0 else 0.0
            payback = capex / actual_annual_savings if actual_annual_savings > 0 else float('inf')

        scenarios.append({
            # Identity
            'scenario_id':                  n,
            'panels_added':                 n,
            # Technical
            'additional_pv_kwp':            add_pv,
            'total_pv_kwp':                 total_pv,
            'rectifier_utilization':        rect_util,
            'monthly_solar_production_kwh': total_solar_gen,
            'solar_contribution_pct':       solar_contrib,
            'monthly_energy_offset_kwh':    total_offset,
            # Primary financial (vs. actual bill)
            'actual_monthly_savings_kes':   actual_monthly_savings,
            'actual_annual_savings_kes':    actual_annual_savings,
            'actual_new_bill_kes':          actual_new_bill,
            'capex_kes':                    capex,
            'roi_pct':                      roi,
            'payback_years':                payback,
            # Secondary financial (energy-model reference)
            'calculated_monthly_bill_kes':  calculated_bill,
        })

    return scenarios


def optimize_site(row: pd.Series) -> Tuple[Dict, List[Dict]]:
    """
    Selects the financially optimal expansion scenario for a site.

    Rule:
        1. Maximise actual annual savings (vs. the actual 2026 monthly bill).
        2. When multiple scenarios achieve the same savings (load fully offset),
           choose the one with the lowest CAPEX (fewest panels, highest ROI).
        3. If the existing solar already covers the full grid bill
           (actual bill savings == 0), recommend no expansion.
    """
    scenarios = generate_scenarios(row)

    if len(scenarios) <= 1:
        return scenarios[0], scenarios

    max_savings = max(s['actual_annual_savings_kes'] for s in scenarios)

    if max_savings == 0.0:
        return scenarios[0], scenarios   # no financial benefit to expansion

    # All scenarios within KES 1 of the maximum (float safety margin)
    best_candidates = [
        s for s in scenarios
        if abs(s['actual_annual_savings_kes'] - max_savings) < 1.0
    ]

    # Among best candidates, pick the one with lowest CAPEX
    recommended = min(best_candidates, key=lambda s: s['capex_kes'])
    return recommended, scenarios


def get_justification(row: pd.Series, recommended: Dict, assessment: Dict) -> str:
    """
    Produces a plain-English explanation of the recommended expansion decision,
    grounded in the actual bill baseline and rectifier constraints.
    """
    pv_exist       = row['PV Capacity (Kw)']
    rectifier_type = row['Rectifier Type']
    rectifier_cap  = RECTIFIER_LIMITS[rectifier_type]
    actual_bill    = row['2026 Average Monthly Bill']
    avg_load       = row['Revised Average Load']

    exist_solar_pct = (pv_exist * KWH_PER_KWP_MONTH / (avg_load * 720)) * 100.0

    if recommended['panels_added'] == 0:
        if assessment['ratio'] >= 1.0:
            return (
                f"No solar expansion is recommended for {row['Site Name']}. "
                f"The existing {pv_exist:.2f} kWp is already **{assessment['category']}** "
                f"and covers the site's energy demand. "
                f"Adding panels would deliver KES 0 additional savings."
            )
        else:
            return (
                f"No solar expansion is recommended because the existing "
                f"{pv_exist:.2f} kWp is already at the maximum capacity of the "
                f"{rectifier_type} rectifier ({rectifier_cap:.1f} kWp). "
                f"Further expansion is physically restricted by the installed rectifier."
            )

    new_solar_pct = recommended['solar_contribution_pct']

    return (
        f"Recommend adding **{recommended['panels_added']} panel(s)** "
        f"(+{recommended['additional_pv_kwp']:.3f} kWp) to bring total solar capacity to "
        f"**{recommended['total_pv_kwp']:.3f} kWp** "
        f"({recommended['rectifier_utilization']:.1f}% of the {rectifier_cap:.1f} kWp "
        f"{rectifier_type} rectifier limit). "
        f"The site's current grid bill of **KES {actual_bill:,.2f}/month** will be reduced by "
        f"**KES {recommended['actual_monthly_savings_kes']:,.2f}/month** "
        f"(**KES {recommended['actual_annual_savings_kes']:,.2f}/year**), "
        f"bringing the new estimated monthly bill to "
        f"**KES {recommended['actual_new_bill_kes']:,.2f}**. "
        f"Total investment (CAPEX): **KES {recommended['capex_kes']:,.2f}** — "
        f"ROI: **{recommended['roi_pct']:.1f}%** — "
        f"Payback: **{recommended['payback_years']:.2f} years** "
        f"({int(recommended['payback_years'] * 12)} months). "
        f"Solar generation will cover {new_solar_pct:.1f}% of the site's total "
        f"energy demand (up from {exist_solar_pct:.1f}% with existing panels)."
    )
