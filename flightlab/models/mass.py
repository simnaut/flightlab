"""Mass properties: total mass, CG location and inertia as fuel burns."""

import numpy as np


def mass_properties(ac, m_fuel):
    """Return (mass_kg, cg_x, inertia_matrix) for the current fuel load.

    The fuel is modelled as a point mass at the tank location. The CG is
    measured from the datum (m, + forward) and the inertia is about the CG.
    """
    m_dry = ac.mass.dry_kg
    m_fuel = max(0.0, m_fuel)
    mass = m_dry + m_fuel
    x_dry = ac.mass.cg_dry_x
    x_tank = ac.fuel.tank_x
    cg_x = (m_dry * x_dry + m_fuel * x_tank) / mass

    # Parallel-axis terms for the dry airframe and the fuel point mass
    d_dry = x_dry - cg_x
    d_fuel = x_tank - cg_x
    extra = m_dry * d_dry ** 2 + m_fuel * d_fuel ** 2
    J = np.array([
        [ac.mass.Ixx, 0.0, -ac.mass.Ixz],
        [0.0, ac.mass.Iyy + extra, 0.0],
        [-ac.mass.Ixz, 0.0, ac.mass.Izz + extra],
    ])
    return mass, cg_x, J
