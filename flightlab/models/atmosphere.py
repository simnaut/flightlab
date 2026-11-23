"""International Standard Atmosphere (troposphere only)."""

RHO_SL = 1.225       # sea-level density (kg/m^3)
T_SL = 288.15        # sea-level temperature (K)
LAPSE = 0.0065       # temperature lapse rate (K/m)
G = 9.80665          # gravity (m/s^2)


def density(altitude_m):
    """Air density (kg/m^3) at a geometric altitude above sea level."""
    h = max(0.0, min(altitude_m, 11000.0))
    temperature = T_SL - LAPSE * h
    return RHO_SL * (temperature / T_SL) ** 4.2559
