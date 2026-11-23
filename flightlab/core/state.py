"""State vector layout and attitude helpers.

The state vector order is fixed (see HARNESS_DESIGN.md §4.2):

    x = [pN, pE, pD,          position, NED (m)
         u, v, w,             body-axis velocity (m/s)
         q0, q1, q2, q3,      attitude quaternion (scalar first)
         p, q, r,             body rates (rad/s)
         de, da, dr,          actual surface positions (rad)
         n,                   engine state (0..1)
         m_fuel]              fuel mass (kg)

Naming note: ``q`` is pitch rate. The quaternion is ``quat``.
"""

import math

import numpy as np


class IDX:
    """Named indices into the state vector."""

    pN, pE, pD = 0, 1, 2
    u, v, w = 3, 4, 5
    q0, q1, q2, q3 = 6, 7, 8, 9
    p, q, r = 10, 11, 12
    de, da, dr = 13, 14, 15
    n = 16
    m_fuel = 17

    pos = slice(0, 3)
    vel = slice(3, 6)
    quat = slice(6, 10)
    rates = slice(10, 13)
    surfaces = slice(13, 16)


N_STATES = 18

STATE_NAMES = [
    "pN", "pE", "pD",
    "u", "v", "w",
    "q0", "q1", "q2", "q3",
    "p", "q", "r",
    "de", "da", "dr",
    "n",
    "m_fuel",
]


class CMD:
    """Named indices into the command vector u."""

    elevator, aileron, rudder, throttle, brake = 0, 1, 2, 3, 4


N_COMMANDS = 5


def euler_to_quat(phi, theta, psi):
    """Euler angles (roll, pitch, yaw; ZYX order) to quaternion [q0, q1, q2, q3]."""
    cphi, sphi = math.cos(phi / 2), math.sin(phi / 2)
    cth, sth = math.cos(theta / 2), math.sin(theta / 2)
    cpsi, spsi = math.cos(psi / 2), math.sin(psi / 2)
    return np.array([
        cpsi * cth * cphi + spsi * sth * sphi,
        cpsi * cth * sphi - spsi * sth * cphi,
        cpsi * sth * cphi + spsi * cth * sphi,
        spsi * cth * cphi - cpsi * sth * sphi,
    ])


def quat_to_euler(quat):
    """Quaternion to Euler angles (phi, theta, psi)."""
    q0, q1, q2, q3 = quat
    phi = math.atan2(2 * (q0 * q1 + q2 * q3), q0 * q0 + q3 * q3 - q1 * q1 - q2 * q2)
    theta = math.asin(max(-1.0, min(1.0, 2 * (q0 * q2 - q1 * q3))))
    psi = math.atan2(2 * (q0 * q3 + q1 * q2), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3)
    return phi, theta, psi


def quat_to_dcm(quat):
    """Rotation matrix taking body-frame vectors to NED-frame vectors."""
    q0, q1, q2, q3 = quat
    return np.array([
        [q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3, 2 * (q1 * q2 - q0 * q3), 2 * (q1 * q3 + q0 * q2)],
        [2 * (q1 * q2 + q0 * q3), q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3, 2 * (q2 * q3 - q0 * q1)],
        [2 * (q1 * q3 - q0 * q2), 2 * (q2 * q3 + q0 * q1), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3],
    ])


def initial_state(aircraft, theta=0.0, phi=0.0, psi=0.0, airspeed=0.0, fuel_kg=None):
    """Build a state vector at rest (or flying straight at ``airspeed``)."""
    x = np.zeros(N_STATES)
    x[IDX.quat] = euler_to_quat(phi, theta, psi)
    x[IDX.u] = airspeed
    x[IDX.m_fuel] = aircraft.fuel.initial_kg if fuel_kg is None else fuel_kg
    return x
