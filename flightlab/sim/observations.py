"""Build the ``observations`` object passed to the student's controller."""

import math


class Fields:
    """A read-only bag of named values with friendly error messages.

    Access values as attributes: ``observations.sensors.theta``.
    """

    def __init__(self, group, values):
        object.__setattr__(self, "_group", group)
        object.__setattr__(self, "_values", dict(values))

    def __getattr__(self, name):
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        group = object.__getattribute__(self, "_group")
        available = ", ".join(values) or "(nothing in this chapter)"
        raise AttributeError(
            f"{group} has no field '{name}' in this chapter. Available: {available}"
        )

    def __setattr__(self, name, value):
        raise AttributeError("observations are read-only")

    def __contains__(self, name):
        return name in self._values

    def as_dict(self):
        return dict(self._values)

    def __repr__(self):
        inner = ", ".join(f"{k}={_fmt(v)}" for k, v in self._values.items())
        return f"{self._group}({inner})"


def _fmt(v):
    if isinstance(v, Fields):
        return repr(v)
    if isinstance(v, float):
        return f"{v:.4g}"
    return repr(v)


# Every signal a chapter can expose, computed from the true state.
def truth_signals(sim):
    x, out = sim.x, sim.outputs
    phi, theta, psi = sim.euler
    from flightlab.core.state import IDX
    return {
        "theta": theta,
        "q": x[IDX.q],
        "phi": phi,
        "p": x[IDX.p],
        "psi": psi,
        "r": x[IDX.r],
        "alpha": out.alpha,
        "beta": out.beta,
        "airspeed": out.airspeed,
        "elevator": x[IDX.de],
    }


def build_observations(sim, config):
    """Observations for the controller, following the chapter's config."""
    truth = truth_signals(sim)

    sensors = {}
    for name in config.get("sensors", []):
        # M1: sensors are perfect. Noise, bias and delay arrive in later chapters.
        sensors[name] = truth[name]

    ref = {name: sim.reference_value(name) for name in config.get("ref", [])}

    groups = {
        "t": sim.t,
        "ref": Fields("observations.ref", ref),
        "sensors": Fields("observations.sensors", sensors),
    }
    if config.get("truth", False):
        groups["truth"] = Fields("observations.truth", truth)
    return Fields("observations", groups)


def is_finite_number(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False
