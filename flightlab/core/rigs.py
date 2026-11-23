"""Test rigs: constrain the full 6DOF plant to fewer degrees of freedom.

Every rig evaluates the same 6DOF dynamics function. It then zeros the
derivatives of the locked states. On test-stand rigs the aircraft is pinned at
its CG and the air moves past it (the environment's ``air_velocity_ned``).
"""

import math
from dataclasses import replace

import numpy as np

from flightlab.core import dynamics
from flightlab.core.state import IDX, N_STATES, quat_to_euler


class Rig:
    name = "free"
    description = "Free flight: all degrees of freedom"
    free_states = list(range(N_STATES))
    test_stand = False
    kick_axis = 1          # body axis a "kick" applies a moment about (0=x, 1=y, 2=z)
    kick_moment = 9500.0   # N m
    kick_duration = 0.1    # s

    def __init__(self):
        self.mask = np.zeros(N_STATES, dtype=bool)
        self.mask[self.free_states] = True

    def stop_moment(self, x):
        """Moment from the stand's mechanical end stops (none by default)."""
        return None

    def evaluate(self, x, u, ac, env):
        """Constrained (xdot, outputs)."""
        extra = self.stop_moment(x)
        if extra is not None:
            env = replace(env, ext_moment_body=env.ext_moment_body + extra)
        xdot, out = dynamics.evaluate(x, u, ac, env)
        xdot[~self.mask] = 0.0
        return xdot, out

    def derivative(self, x, u, ac, env):
        return self.evaluate(x, u, ac, env)[0]


class PitchGimbal(Rig):
    """Wind-tunnel stand: the aircraft can only pitch about its CG."""

    name = "pitch_gimbal"
    description = "Pitch stand: pinned at the CG, free to pitch only"
    free_states = [IDX.q0, IDX.q1, IDX.q2, IDX.q3, IDX.q,
                   IDX.de, IDX.da, IDX.dr, IDX.n, IDX.m_fuel]
    test_stand = True
    kick_axis = 1

    stop_angle = math.radians(35.0)   # stand's mechanical pitch limit
    stop_stiffness = 2.0e6            # N m / rad
    stop_damping = 1.0e5              # N m s / rad

    def stop_moment(self, x):
        theta = quat_to_euler(x[IDX.quat])[1]
        excess = abs(theta) - self.stop_angle
        if excess <= 0.0:
            return None
        sign = math.copysign(1.0, theta)
        q = x[IDX.q]
        m = -sign * self.stop_stiffness * excess
        if q * sign > 0:                        # only damp while pushing into the stop
            m -= self.stop_damping * q
        return np.array([0.0, m, 0.0])


RIGS = {cls.name: cls for cls in (PitchGimbal, Rig)}


def make_rig(name):
    try:
        return RIGS[name]()
    except KeyError:
        raise ValueError(f"Unknown rig '{name}'. Available: {', '.join(RIGS)}") from None
