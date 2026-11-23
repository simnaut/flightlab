"""Wind tunnel air for test-stand rigs.

The air vector is an airspeed plus a vertical flow angle. Positive flow angle
is up-flow (air rising as it passes the aircraft), which raises the angle of
attack without changing pitch, just like a vertical gust.

Changes can be applied as a step (instant) or smoothly over ``ramp_time``.
"""

import math

import numpy as np


class Tunnel:
    def __init__(self, airspeed, flow_angle, ramp_time=1.0):
        self.default = (float(airspeed), float(flow_angle))
        self.ramp_time = ramp_time
        self._set(0.0, self.default, self.default, 0.0)

    def _set(self, t0, start, target, duration):
        self._t0, self._start, self._target, self._duration = t0, start, target, duration

    def value(self, t):
        """(airspeed m/s, flow angle rad) at time t."""
        if self._duration <= 0 or t >= self._t0 + self._duration:
            return self._target
        s = (t - self._t0) / self._duration
        a0, f0 = self._start
        a1, f1 = self._target
        return a0 + (a1 - a0) * s, f0 + (f1 - f0) * s

    @property
    def target(self):
        return self._target

    def set_target(self, t, airspeed, flow_angle, smooth=True):
        self._set(t, self.value(t), (float(airspeed), float(flow_angle)),
                  self.ramp_time if smooth else 0.0)

    def reset(self, t, smooth=True):
        self.set_target(t, *self.default, smooth=smooth)

    def air_velocity_ned(self, t):
        """Aircraft velocity relative to the air, NED (m/s)."""
        airspeed, flow = self.value(t)
        # Up-flow means the air rises past the aircraft, i.e. the aircraft
        # moves forward and *down* relative to the air (+D).
        return np.array([airspeed * math.cos(flow), 0.0, airspeed * math.sin(flow)])
