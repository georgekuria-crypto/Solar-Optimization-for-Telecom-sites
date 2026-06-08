# tests/test_model.py

import unittest
import pandas as pd
from src.utils import (
    calculate_daily_solar_production,
    calculate_monthly_solar_production,
    convert_ah_to_kwh,
    RECTIFIER_LIMITS,
    TARIFF_KES,
    INSTALLED_COST_KES
)
from src.optimizer import assess_existing_solar, generate_scenarios, optimize_site
from src.data_loader import load_and_validate_data


class TestTelecomSolarOptimization(unittest.TestCase):
    
    def test_solar_production_formulas(self):
        """
        Verify the basic solar production formulas.
        Daily: PV Capacity * PSH * Efficiency = PV * 5.5 * 0.8 = PV * 4.4
        Monthly: Daily * 30 = PV * 132
        """
        pv_capacity = 10.0  # 10 kWp
        expected_daily = 10.0 * 5.5 * 0.8
        expected_monthly = expected_daily * 30.0
        
        self.assertAlmostEqual(calculate_daily_solar_production(pv_capacity), expected_daily)
        self.assertAlmostEqual(calculate_monthly_solar_production(pv_capacity), expected_monthly)
        self.assertAlmostEqual(expected_monthly, 1320.0)
        
    def test_battery_ah_to_kwh_conversion(self):
        """
        Verify the battery Ah to kWh conversion.
        Formula: kWh = Ah * 54.5 / 1000
        """
        ah_capacity = 1000.0
        expected_kwh = (1000.0 * 54.5) / 1000.0
        self.assertAlmostEqual(convert_ah_to_kwh(ah_capacity), expected_kwh)
        self.assertAlmostEqual(expected_kwh, 54.5)

    def test_existing_solar_asset_assessment(self):
        """
        Test the categorization logic for existing solar size.
        Target capacity is Monthly Energy / 132.
        For 1320 kWh monthly energy, target is 10 kWp.
        - PV_exist = 5.0 kWp (Ratio = 0.5) -> Under-sized
        - PV_exist = 8.0 kWp (Ratio = 0.8) -> Adequately sized
        - PV_exist = 10.0 kWp (Ratio = 1.0) -> Near optimum
        - PV_exist = 12.0 kWp (Ratio = 1.2) -> Over-sized
        """
        monthly_energy = 1320.0  # Target PV is 10.0 kWp
        
        self.assertEqual(assess_existing_solar(5.0, monthly_energy)['category'], 'Under-sized')
        self.assertEqual(assess_existing_solar(8.0, monthly_energy)['category'], 'Adequately sized')
        self.assertEqual(assess_existing_solar(10.0, monthly_energy)['category'], 'Near optimum')
        self.assertEqual(assess_existing_solar(12.0, monthly_energy)['category'], 'Over-sized')

    def test_scenario_calculations(self):
        """
        Verify scenario metrics calculation for a hypothetical site.
        """
        # Create a mock site row
        row = pd.Series({
            'Site Name': 'Test Site',
            'Rectifier Type': 'Eltek',  # Max 18 kWp
            'PV Capacity (Kw)': 10.35,  # Headroom: 18 - 10.35 = 7.65 kWp
            'Revised Average Load': 5.23,  # Monthly energy: 5.23 * 720 = 3765.6 kWh
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 105693.0
        })
        
        scenarios = generate_scenarios(row)
        
        # Max headroom = 7.65. With 0.575 panel rating:
        # floor(7.65 / 0.575) = 13 panels max
        self.assertEqual(len(scenarios), 14)  # 0 to 13 panels inclusive
        
        # Verify scenario for 0 panels added
        s0 = scenarios[0]
        self.assertEqual(s0['panels_added'], 0)
        self.assertAlmostEqual(s0['capex_kes'], 0.0)
        self.assertAlmostEqual(s0['roi_pct'], 0.0)
        self.assertAlmostEqual(s0['payback_years'], 0.0)
        self.assertAlmostEqual(s0['total_pv_kwp'], 10.35)
        
        # Verify scenario for 2 panels added
        s2 = scenarios[2]
        self.assertEqual(s2['panels_added'], 2)
        self.assertAlmostEqual(s2['capex_kes'], 2 * INSTALLED_COST_KES)
        
        # Additional savings:
        # Existing solar monthly generation: 10.35 * 132 = 1366.2 kWh. Offset = 1366.2 kWh.
        # Scenario 2 solar monthly generation: (10.35 + 2 * 0.575) * 132 = 11.5 * 132 = 1518.0 kWh. Offset = 1518.0 kWh.
        # Additional offset: 1518.0 - 1366.2 = 151.8 kWh.
        # Additional savings: 151.8 * 28 = 4250.4 KES/month = 51004.8 KES/year.
        # CAPEX: 2 * 29500 = 59000 KES.
        # ROI: (51004.8 / 59000) * 100 = 86.4488%
        # Payback: 59000 / 51004.8 = 1.1567 years
        self.assertAlmostEqual(s2['additional_monthly_savings_kes'], 4250.4)
        self.assertAlmostEqual(s2['additional_annual_savings_kes'], 51004.8)
        self.assertAlmostEqual(s2['roi_pct'], 86.4488, places=4)
        self.assertAlmostEqual(s2['payback_years'], 1.1568, places=4)

    def test_optimizer_sizing_decision(self):
        """
        Verify that the optimizer selects the correct financially optimal scenario.
        For a load of 5.23 kW (monthly energy 3765.6 kWh):
        Existing solar is 10.35 kWp (generation 1366.2 kWh).
        We want to cover 3765.6 kWh. Target capacity is 3765.6 / 132 = 28.52 kWp.
        Headroom in Eltek is up to 18 kWp (max 13 panels added, total 17.825 kWp).
        Since target solar (28.52 kWp) is much greater than rectifier capacity (18 kWp),
        the optimizer should recommend the maximum possible panels under the rectifier limit: 13 panels.
        """
        row = pd.Series({
            'Site Name': 'Test Site',
            'Rectifier Type': 'Eltek',
            'PV Capacity (Kw)': 10.35,
            'Revised Average Load': 5.23,
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 105693.0
        })
        
        recommended, scenarios = optimize_site(row)
        self.assertEqual(recommended['panels_added'], 13)
        self.assertAlmostEqual(recommended['total_pv_kwp'], 10.35 + 13 * 0.575)
        
        # Test a site where existing solar already covers the load
        # Load: 1.0 kW -> 720 kWh/month -> Target solar is 720/132 = 5.45 kWp.
        # Existing solar: 6.9 kWp.
        # Optimizer should recommend 0 panels added.
        row_oversized = pd.Series({
            'Site Name': 'Oversized Site',
            'Rectifier Type': 'Megmeet',
            'PV Capacity (Kw)': 6.9,
            'Revised Average Load': 1.0,
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 20160.0
        })
        
        recommended_oversized, _ = optimize_site(row_oversized)
        self.assertEqual(recommended_oversized['panels_added'], 0)


if __name__ == '__main__':
    unittest.main()
