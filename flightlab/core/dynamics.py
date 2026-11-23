"""Rigid-body 6DOF equations of motion.

The plant is a pure function:

    xdot = f(x, u, ac, env)

with no hidden state: everything with memory (actuators, engine, fuel) lives
in the state vector ``x``. This lets the same function be used for
simulation, trimming, linearization and model-based control.

Equations (body axes, flat non-rotating earth):

    m (v_dot + omega x v) = F_aero + F_thrust + F_gravity + F_ext
    J omega_dot + omega x (J omega) = M_aero + M_thrust + M_ext
    p_dot_ned = R(quat) v
    quat_dot = 0.5 * Omega(omega) quat
"""

from dataclasses import dataclass, field

import numpy as np

from flightlab.core.state import IDX, N_STATES, CMD, quat_to_dcm
from flightlab.models import aero, propulsion
from flightlab.models.atmosphere import G, density
from flightlab.models.mass import mass_properties


@dataclass
class Environment:
    """Everything outside the aircraft that the dynamics depend on.

    wind_ned:          steady wind (m/s, NED) for free-flight rigs
    air_velocity_ned:  if set, the aircraft's velocity *relative to the air*
                       (NED); used by test-stand rigs where the aircraft is
                       fixed and the air moves past it
    rho:               air density override (kg/m^3); None = ISA at altitude
    ext_force_body:    extra force (N, body axes), e.g., a test-stand constraint
    ext_moment_body:   extra moment (N m, body axes), e.g., a "kick"
    actuator_tau:      surface servo time constant (s); None = ideal surfaces
                       (set directly by the harness, no dynamics)
    """

    wind_ned: np.ndarray = field(default_factory=lambda: np.zeros(3))
    air_velocity_ned: np.ndarray | None = None
    rho: float | None = None
    ext_force_body: np.ndarray = field(default_factory=lambda: np.zeros(3))
    ext_moment_body: np.ndarray = field(default_factory=lambda: np.zeros(3))
    actuator_tau: float | None = None


@dataclass
class Outputs:
    """Derived quantities useful for logging and observations."""

    airspeed: float
    alpha: float
    beta: float
    qbar: float
    rho: float
    mass: float
    cg_x: float
    thrust: float


def evaluate(x, u, ac, env):
    """Return (xdot, outputs) for state x and commands u."""
    quat = x[IDX.quat]
    v = x[IDX.vel]
    omega = x[IDX.rates]
    R = quat_to_dcm(quat)          # body -> NED

    rho = env.rho if env.rho is not None else density(-x[IDX.pD])
    mass, cg_x, J = mass_properties(ac, x[IDX.m_fuel])

    # Air-relative velocity in body axes
    if env.air_velocity_ned is not None:
        v_air = R.T @ env.air_velocity_ned
    else:
        v_air = v - R.T @ env.wind_ned

    # Aerodynamics, with moments transferred from the reference point to the CG
    f_aero, m_aero_ref, (airspeed, alpha, beta, qbar) = aero.forces_and_moments(
        ac, rho, v_air, omega, x[IDX.surfaces]
    )
    r_ref = np.array([ac.aero.ref_point_x - cg_x, 0.0, 0.0])   # CG -> ref point
    m_aero = m_aero_ref + np.cross(r_ref, f_aero)

    # Propulsion
    n = x[IDX.n]
    thrust = propulsion.thrust(ac, rho, airspeed, n)
    f_thrust = np.array([thrust, 0.0, 0.0])
    m_thrust = np.array([0.0, ac.propulsion.thrust_z * thrust, 0.0])

    # Gravity (acts at the CG, so no moment)
    f_grav = R.T @ np.array([0.0, 0.0, mass * G])

    force = f_aero + f_thrust + f_grav + env.ext_force_body
    moment = m_aero + m_thrust + env.ext_moment_body

    xdot = np.zeros(N_STATES)
    xdot[IDX.pos] = R @ v
    xdot[IDX.vel] = force / mass - np.cross(omega, v)
    xdot[IDX.rates] = np.linalg.solve(J, moment - np.cross(omega, J @ omega))

    p, q, r = omega
    q0, q1, q2, q3 = quat
    xdot[IDX.quat] = 0.5 * np.array([
        -p * q1 - q * q2 - r * q3,
        p * q0 + r * q2 - q * q3,
        q * q0 - r * q1 + p * q3,
        r * q0 + q * q1 - p * q2,
    ])

    if env.actuator_tau is not None:
        cmd = u[[CMD.elevator, CMD.aileron, CMD.rudder]]
        xdot[IDX.surfaces] = (cmd - x[IDX.surfaces]) / env.actuator_tau

    xdot[IDX.n] = propulsion.engine_rate(ac, n, u[CMD.throttle])
    xdot[IDX.m_fuel] = propulsion.fuel_rate(ac, n, x[IDX.m_fuel])

    outputs = Outputs(airspeed, alpha, beta, qbar, rho, mass, cg_x, thrust)
    return xdot, outputs


def f(x, u, ac, env):
    """State derivative xdot = f(x, u, ac, env)."""
    return evaluate(x, u, ac, env)[0]
