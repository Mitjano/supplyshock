"""Carbon emission estimation for commodity voyages.

Provides fuel consumption and CO2 estimation based on vessel type,
distance, speed, and deadweight tonnage. Calculates CII rating
per IMO guidelines.
"""

# Daily fuel consumption by vessel type (tonnes/day at service speed)
FUEL_CONSUMPTION: dict[str, float] = {
    "tanker_vlcc": 80.0,
    "tanker_suezmax": 55.0,
    "tanker_aframax": 40.0,
    "bulk_capesize": 45.0,
    "bulk_panamax": 32.0,
    "container_large": 150.0,
    "lng_carrier": 130.0,
    "default": 35.0,
}

# CO2 emission factor for Heavy Fuel Oil (tonnes CO2 per tonne fuel)
CO2_FACTOR = 3.114

# CII rating thresholds (grams CO2 per tonne-mile)
CII_THRESHOLDS = {
    "A": 0.003,
    "B": 0.004,
    "C": 0.005,
    "D": 0.006,
}


def estimate_voyage_emissions(
    distance_nm: float,
    vessel_type: str,
    speed_knots: float,
    dwt: float,
) -> dict:
    """Estimate fuel consumption, CO2 emissions, and CII rating for a voyage.

    Args:
        distance_nm: Voyage distance in nautical miles.
        vessel_type: Vessel type key (e.g. 'tanker_vlcc', 'bulk_panamax').
        speed_knots: Average speed in knots.
        dwt: Deadweight tonnage of the vessel.

    Returns:
        dict with fuel_estimate_tonnes, co2_estimate_tonnes, cii_value, cii_rating.
    """
    if speed_knots <= 0 or distance_nm <= 0 or dwt <= 0:
        return {
            "fuel_estimate_tonnes": 0.0,
            "co2_estimate_tonnes": 0.0,
            "cii_value": None,
            "cii_rating": None,
        }

    daily_consumption = FUEL_CONSUMPTION.get(vessel_type, FUEL_CONSUMPTION["default"])

    # fuel = distance * daily_consumption / (24 * speed)
    fuel_tonnes = distance_nm * daily_consumption / (24.0 * speed_knots)
    co2_tonnes = fuel_tonnes * CO2_FACTOR

    # CII = CO2 / (DWT * distance)
    cii_value = co2_tonnes / (dwt * distance_nm)

    # Determine CII rating
    if cii_value < CII_THRESHOLDS["A"]:
        cii_rating = "A"
    elif cii_value < CII_THRESHOLDS["B"]:
        cii_rating = "B"
    elif cii_value < CII_THRESHOLDS["C"]:
        cii_rating = "C"
    elif cii_value < CII_THRESHOLDS["D"]:
        cii_rating = "D"
    else:
        cii_rating = "E"

    return {
        "fuel_estimate_tonnes": round(fuel_tonnes, 2),
        "co2_estimate_tonnes": round(co2_tonnes, 2),
        "cii_value": round(cii_value, 8),
        "cii_rating": cii_rating,
    }
