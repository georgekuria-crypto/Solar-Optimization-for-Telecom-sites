# src/utils.py

# Rectifier Capacity Constraints (kWp)
RECTIFIER_LIMITS = {
    'Megmeet': 21.0,
    'Eltek': 18.0,
    'Megmeet FSU': 12.0
}

# Solar Modeling Assumptions
PEAK_SUN_HOURS = 5.5
SYSTEM_EFFICIENCY = 0.80
DAYS_IN_MONTH = 30
HOURS_IN_DAY = 24

# Electricity Tariff (KES per kWh)
TARIFF_KES = 28.0

# Financial Cost Assumptions (KES)
PANEL_COST_KES = 14500.0
LABOUR_COST_KES = 15000.0
INSTALLED_COST_KES = PANEL_COST_KES + LABOUR_COST_KES  # 29,500 KES

# Solar Panel Capacity (kWp)
# 575W per panel is the default, matching the dataset increments
PANEL_RATING_KWP = 0.575

# Battery Voltage (V) for Ah to kWh conversion
BATTERY_VOLTAGE = 54.5


def calculate_daily_solar_production(pv_capacity: float) -> float:
    """
    Daily Solar Production (kWh/day) = PV Capacity (kWp) * PSH * System Efficiency
    """
    return pv_capacity * PEAK_SUN_HOURS * SYSTEM_EFFICIENCY


def calculate_monthly_solar_production(pv_capacity: float) -> float:
    """
    Monthly Solar Production (kWh/month) = Daily Production * 30
    """
    return calculate_daily_solar_production(pv_capacity) * DAYS_IN_MONTH


def convert_ah_to_kwh(ah_capacity: float) -> float:
    """
    Converts battery capacity from Ah to kWh using the nominal system voltage (54.5 V).
    Formula: kWh = (Ah * 54.5) / 1000
    """
    return (ah_capacity * BATTERY_VOLTAGE) / 1000.0
