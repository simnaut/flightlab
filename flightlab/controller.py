"""The student-facing controller interface."""

import math
from dataclasses import dataclass

DEG = math.pi / 180.0
"""Degrees-to-radians factor: ``5 * DEG`` is 5 degrees in radians,
``angle / DEG`` converts radians to degrees."""


@dataclass
class Command:
    """What the controller asks the aircraft to do.

    elevator, aileron, rudder: surface deflection in radians.
        Positive elevator = trailing edge down = nose DOWN.
        Positive aileron  = roll right.
        Positive rudder   = trailing edge left = nose LEFT.
    throttle: 0 (idle) to 1 (full).
    brake:    0 (off) to 1 (full).

    Fields not used by the current chapter are ignored.
    """

    elevator: float = 0.0
    aileron: float = 0.0
    rudder: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0


class ControllerBase:
    """Base class for student controllers.

    Subclass it and implement ``update``. Optionally implement ``reset`` to set
    up variables (integrators, filters, ...) before each run.
    """

    def reset(self, info):
        """Called once before each run. ``info`` describes the chapter setup."""

    def update(self, observations, dt):
        """Called every controller tick. Return a ``Command``."""
        return Command()

    def log(self, name, value):
        """Record a signal; it shows up in the live plots and the run log."""
        if not hasattr(self, "_telemetry"):
            self._telemetry = {}
        try:
            self._telemetry[str(name)] = float(value)
        except (TypeError, ValueError):
            raise TypeError(
                f"self.log('{name}', ...) needs a number, got {type(value).__name__}: {value!r}"
            ) from None

    def _take_telemetry(self):
        t = getattr(self, "_telemetry", None) or {}
        self._telemetry = {}
        return t


class ZeroController(ControllerBase):
    """Leaves every surface at neutral (used for --open-loop)."""
