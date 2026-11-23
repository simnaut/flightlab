"""Simple engine + propeller model.

    T = T_max(rho) * n * (1 - V / V_max),   n_dot = (throttle - n) / tau
"""

from flightlab.models.atmosphere import RHO_SL


def thrust(ac, rho, airspeed, n):
    """Thrust (N) along the body x axis."""
    p = ac.propulsion
    t = p.T_max_sl * (rho / RHO_SL) * n * (1.0 - airspeed / p.V_max)
    return max(0.0, t)


def engine_rate(ac, n, throttle):
    """Time derivative of the engine state n."""
    throttle = min(1.0, max(0.0, throttle))
    return (throttle - n) / ac.propulsion.tau


def fuel_rate(ac, n, m_fuel):
    """Time derivative of fuel mass (kg/s, negative while burning)."""
    if m_fuel <= 0.0:
        return 0.0
    return -ac.fuel.flow_full_throttle_kg_s * max(0.0, n)
