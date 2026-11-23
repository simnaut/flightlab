"""Aerodynamic forces and moments from stability derivatives.

Coefficient build-up (HARNESS_DESIGN.md §4.6):

    CL = CL0 + CL_alpha*alpha + CL_q*(q c / 2V) + CL_de*de
    CD = CD0 + K*CL^2
    Cm = Cm0 + Cm_alpha*alpha + Cm_q*(q c / 2V) + Cm_de*de
    CY = CY_beta*beta + CY_p*(p b / 2V) + CY_r*(r b / 2V) + CY_dr*dr
    Cl = Cl_beta*beta + Cl_p*(p b / 2V) + Cl_r*(r b / 2V) + Cl_da*da + Cl_dr*dr
    Cn = Cn_beta*beta + Cn_p*(p b / 2V) + Cn_r*(r b / 2V) + Cn_da*da + Cn_dr*dr

Forces are returned in body axes. Moments are about the aerodynamic
reference point; dynamics.py transfers them to the actual CG.
"""

import math

import numpy as np


def air_angles(v_air_body):
    """Airspeed, angle of attack and sideslip from the air-relative velocity."""
    u, v, w = v_air_body
    airspeed = math.sqrt(u * u + v * v + w * w)
    if airspeed < 1e-6:
        return 0.0, 0.0, 0.0
    alpha = math.atan2(w, u)
    beta = math.asin(max(-1.0, min(1.0, v / airspeed)))
    return airspeed, alpha, beta


def coefficients(a, alpha, beta, airspeed, p, q, r, de, da, dr, c, b):
    """Non-dimensional aero coefficients (CL, CD, CY, Cl, Cm, Cn)."""
    if airspeed < 1e-3:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    qhat = q * c / (2 * airspeed)
    phat = p * b / (2 * airspeed)
    rhat = r * b / (2 * airspeed)
    CL = a.CL0 + a.CL_alpha * alpha + a.CL_q * qhat + a.CL_de * de
    CD = a.CD0 + a.K * CL * CL
    Cm = a.Cm0 + a.Cm_alpha * alpha + a.Cm_q * qhat + a.Cm_de * de
    CY = a.CY_beta * beta + a.CY_p * phat + a.CY_r * rhat + a.CY_dr * dr
    Cl = a.Cl_beta * beta + a.Cl_p * phat + a.Cl_r * rhat + a.Cl_da * da + a.Cl_dr * dr
    Cn = a.Cn_beta * beta + a.Cn_p * phat + a.Cn_r * rhat + a.Cn_da * da + a.Cn_dr * dr
    return CL, CD, CY, Cl, Cm, Cn


def forces_and_moments(ac, rho, v_air_body, rates, surfaces):
    """Aero force (body axes, N) and moment about the reference point (N m).

    Returns (force, moment, info) where info holds airspeed, alpha, beta, qbar.
    """
    airspeed, alpha, beta = air_angles(v_air_body)
    p, q, r = rates
    de, da, dr = surfaces
    g = ac.geometry
    CL, CD, CY, Cl, Cm, Cn = coefficients(
        ac.aero, alpha, beta, airspeed, p, q, r, de, da, dr, g.c, g.b
    )
    qbar = 0.5 * rho * airspeed * airspeed
    qS = qbar * g.S
    ca, sa = math.cos(alpha), math.sin(alpha)
    force = np.array([
        qS * (-CD * ca + CL * sa),
        qS * CY,
        qS * (-CD * sa - CL * ca),
    ])
    moment = np.array([qS * g.b * Cl, qS * g.c * Cm, qS * g.b * Cn])
    info = (airspeed, alpha, beta, qbar)
    return force, moment, info
