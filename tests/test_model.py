# tests/test_model.py

import unittest
import pandas as pd
from src.utils import (
    calculate_daily_solar_production,
    calculate_monthly_solar_production,
    convert_ah_to_kwh,
    TARIFF_KES,
    INSTALLED_COST_KES,
)
from src.optimizer import assess_existing_solar, generate_scenarios, optimize_site
from src.data_loader import load_and_validate_data


class TestSolarModeling(unittest.TestCase):

    def test_solar_production_formulas(self):
        """Daily = PV × 5.5 × 0.8; Monthly = Daily × 30"""
        pv = 10.0
        self.assertAlmostEqual(calculate_daily_solar_production(pv), 44.0)
        self.assertAlmostEqual(calculate_monthly_solar_production(pv), 1320.0)

    def test_battery_ah_to_kwh(self):
        """kWh = Ah × 54.5 / 1000"""
        self.assertAlmostEqual(convert_ah_to_kwh(1000.0), 54.5)

    def test_existing_solar_assessment(self):
        """
        Monthly energy = 1320 kWh  →  target PV = 10 kWp
        5.0 kWp → Under-sized      (ratio 0.50)
        8.0 kWp → Adequately sized (ratio 0.80)
        10.0 kWp → Near optimum   (ratio 1.00)
        12.0 kWp → Over-sized     (ratio 1.20)
        """
        e = 1320.0
        self.assertEqual(assess_existing_solar(5.0,  e)['category'], 'Under-sized')
        self.assertEqual(assess_existing_solar(8.0,  e)['category'], 'Adequately sized')
        self.assertEqual(assess_existing_solar(10.0, e)['category'], 'Near optimum')
        self.assertEqual(assess_existing_solar(12.0, e)['category'], 'Over-sized')

    def test_scenario_count(self):
        """
        Eltek rectifier = 18 kWp.  Existing PV = 10.35 kWp.
        Headroom = 7.65 kWp.  Panel = 0.575 kWp.
        floor(7.65 / 0.575) = 13  →  14 scenarios (0 … 13).
        """
        row = pd.Series({
            'Site Name': 'Test Site',
            'Rectifier Type': 'Eltek',
            'PV Capacity (Kw)': 10.35,
            'Panel Rating (kWp)': 0.575,
            'Revised Average Load': 5.23,
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 105_693.0,
        })
        scens = generate_scenarios(row)
        self.assertEqual(len(scens), 14)   # 0 to 13 inclusive

    def test_baseline_scenario_zero_savings(self):
        """n=0 → no new panels → savings = 0, CAPEX = 0, ROI = 0, payback = 0."""
        row = pd.Series({
            'Site Name': 'Test Site',
            'Rectifier Type': 'Eltek',
            'PV Capacity (Kw)': 10.35,
            'Panel Rating (kWp)': 0.575,
            'Revised Average Load': 5.23,
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 105_693.0,
        })
        s0 = generate_scenarios(row)[0]
        self.assertEqual(s0['panels_added'],            0)
        self.assertAlmostEqual(s0['capex_kes'],         0.0)
        self.assertAlmostEqual(s0['actual_monthly_savings_kes'], 0.0)
        self.assertAlmostEqual(s0['roi_pct'],           0.0)
        self.assertAlmostEqual(s0['payback_years'],     0.0)
        self.assertAlmostEqual(s0['actual_new_bill_kes'], 105_693.0)

    def test_scenario_financial_vs_actual_bill(self):
        """
        Actual bill = KES 105,693.
        Current grid energy = 105,693 / 28 = 3,774.75 kWh.
        Adding 2 panels (1.15 kWp):
          new-panel gen = 1.15 × 132 = 151.8 kWh  (< 3,774.75 → not capped)
          monthly savings = 151.8 × 28 = KES 4,250.40
          annual savings  = 4,250.40 × 12 = KES 51,004.80
          CAPEX           = 2 × 29,500 = KES 59,000
          ROI             = 51,004.80 / 59,000 × 100 = 86.45 %
          payback         = 59,000 / 51,004.80 = 1.1568 years
        """
        row = pd.Series({
            'Site Name': 'Test Site',
            'Rectifier Type': 'Eltek',
            'PV Capacity (Kw)': 10.35,
            'Panel Rating (kWp)': 0.575,
            'Revised Average Load': 5.23,
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 105_693.0,
        })
        s2 = generate_scenarios(row)[2]
        self.assertAlmostEqual(s2['actual_monthly_savings_kes'], 4_250.40, places=2)
        self.assertAlmostEqual(s2['actual_annual_savings_kes'],  51_004.80, places=2)
        self.assertAlmostEqual(s2['capex_kes'],                  59_000.0,  places=2)
        self.assertAlmostEqual(s2['roi_pct'],                    86.45,     places=1)
        self.assertAlmostEqual(s2['payback_years'],              1.1568,    places=3)

    def test_optimizer_recommends_max_panels_when_load_exceeds_capacity(self):
        """
        Actual bill = KES 105,693  →  current grid energy ≈ 3,774 kWh.
        Max rectifier: 18 kWp.  Existing: 10.35 kWp  →  13 new panels max.
        Full expansion gen = 13 × 0.575 × 132 = 987.9 kWh < 3,774 kWh
        → every additional panel still saves money → recommend 13 panels.
        """
        row = pd.Series({
            'Site Name': 'Test Site',
            'Rectifier Type': 'Eltek',
            'PV Capacity (Kw)': 10.35,
            'Panel Rating (kWp)': 0.575,
            'Revised Average Load': 5.23,
            'Battery Capacity (AH)': 1000.0,
            '2026 Average Monthly Bill': 105_693.0,
        })
        rec, _ = optimize_site(row)
        self.assertEqual(rec['panels_added'], 13)

    def test_optimizer_recommends_zero_when_bill_already_zero(self):
        """
        If the actual bill is zero there is nothing to save — but such sites
        are excluded by the data loader before reaching the optimiser.
        Guard: if somehow a zero-bill site reaches optimise_site, savings = 0
        and it recommends 0 panels.
        """
        row = pd.Series({
            'Site Name': 'Already-Free Site',
            'Rectifier Type': 'Megmeet',
            'PV Capacity (Kw)': 6.9,
            'Panel Rating (kWp)': 0.575,
            'Revised Average Load': 1.0,
            'Battery Capacity (AH)': 800.0,
            '2026 Average Monthly Bill': 0.0,
        })
        rec, _ = optimize_site(row)
        self.assertEqual(rec['panels_added'], 0)
        self.assertAlmostEqual(rec['actual_annual_savings_kes'], 0.0)

    def test_data_loader_excludes_zero_bill_sites(self):
        """
        Sites with a zero 2026 Average Monthly Bill must be excluded by
        the data loader because there is no billing baseline for savings.
        """
        valid_df, exclusions = load_and_validate_data('Data/Sensitivity Project 2.0.xlsx')

        excluded_names = [e['Site Name'] for e in exclusions]

        # Bar Kowino has bill = 0 in the dataset → must be excluded
        self.assertIn('Bar Kowino', excluded_names)

        # No zero-bill site should appear in the valid set
        self.assertTrue(
            (valid_df['2026 Average Monthly Bill'] > 0).all(),
            "All valid sites must have a positive 2026 Monthly Bill"
        )

    def test_data_loader_accepts_positive_bill_sites(self):
        """All sites with a positive bill AND valid load should pass."""
        valid_df, _ = load_and_validate_data('Data/Sensitivity Project 2.0.xlsx')
        self.assertGreater(len(valid_df), 0)
        self.assertTrue((valid_df['Revised Average Load'] > 0).all())
        self.assertTrue((valid_df['2026 Average Monthly Bill'] > 0).all())


if __name__ == '__main__':
    unittest.main()
