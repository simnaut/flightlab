"""Performance metrics computed from a run log.

Angles are reported in degrees. Windows come from the reference schedule:
each interval where the command is constant is a "window", and a window that
starts with a jump in the command is a "step response".
"""

import math

import numpy as np

DEG = math.pi / 180.0


def _windows(log, schedule, t_end):
    return schedule.flat_windows(t_end)


def _slice(t, t0, t1):
    return (t >= t0) & (t <= t1 + 1e-9)


def steady_state_error(log, signal, schedule, tail_s=3.0, **_):
    """Largest average |error| over the last ``tail_s`` seconds of each window."""
    t = log["t"]
    e = log[f"ref_{signal}"] - log[signal]
    worst = 0.0
    for t0, t1, _, _ in _windows(log, schedule, t[-1]):
        if t1 - t0 < tail_s:
            continue
        m = _slice(t, t1 - tail_s, t1)
        worst = max(worst, float(np.mean(np.abs(e[m]))))
    return worst / DEG


def overshoot(log, signal, schedule, min_step_deg=1.0, **_):
    """Largest overshoot (% of step size) over all step responses."""
    t, y = log["t"], log[signal]
    worst = 0.0
    for t0, t1, target, step in _windows(log, schedule, t[-1]):
        if step is None or abs(step) < min_step_deg * DEG:
            continue
        m = _slice(t, t0, t1)
        beyond = (y[m] - target) * math.copysign(1.0, step)
        worst = max(worst, float(np.max(beyond)) / abs(step) * 100.0)
    return max(0.0, worst)


def settling_time(log, signal, schedule, band_pct=5.0, min_band_deg=0.25,
                  min_step_deg=1.0, **_):
    """Longest time for a step response to stay within a band around its final value.

    The final value is the average over the last second of the window (so a
    controller with steady-state error can still "settle", just not on target;
    steady-state error is a separate check). The band is ``band_pct`` % of the
    step, but at least ``min_band_deg``. A response that never settles counts
    as the whole window.
    """
    t, y = log["t"], log[signal]
    worst = 0.0
    for t0, t1, target, step in _windows(log, schedule, t[-1]):
        if step is None or abs(step) < min_step_deg * DEG:
            continue
        band = max(abs(step) * band_pct / 100.0, min_band_deg * DEG)
        m = _slice(t, t0, t1)
        tw, yw = t[m], y[m]
        final = float(np.mean(yw[tw >= t1 - 1.0]))
        outside = np.nonzero(np.abs(yw - final) > band)[0]
        if len(outside) == 0:
            ts = 0.0
        elif outside[-1] == len(yw) - 1:
            ts = t1 - t0                      # never settled
        else:
            ts = tw[outside[-1] + 1] - t0
        worst = max(worst, float(ts))
    return worst


def rms_error(log, signal, schedule=None, t_start=1.0, **_):
    """Root-mean-square tracking error after ``t_start``."""
    t = log["t"]
    e = log[f"ref_{signal}"] - log[signal]
    m = t >= t_start
    return float(np.sqrt(np.mean(e[m] ** 2))) / DEG


def max_error(log, signal, schedule=None, t_start=1.0, **_):
    """Largest |tracking error| after ``t_start``."""
    t = log["t"]
    e = log[f"ref_{signal}"] - log[signal]
    m = t >= t_start
    return float(np.max(np.abs(e[m]))) / DEG


def rms_surface_rate(log, signal=None, schedule=None, surface="de", t_start=1.0, **_):
    """RMS rate of surface motion (deg/s): how busy the controller is."""
    t, d = log["t"], log[surface]
    rate = np.diff(d) / np.diff(t)
    m = t[1:] >= t_start
    return float(np.sqrt(np.mean(rate[m] ** 2))) / DEG


def max_surface(log, signal=None, schedule=None, surface="de", t_start=0.0, **_):
    """Largest |surface deflection| (deg)."""
    t, d = log["t"], log[surface]
    return float(np.max(np.abs(d[t >= t_start]))) / DEG


METRICS = {
    "steady_state_error": (steady_state_error, "Steady-state error", "deg"),
    "overshoot": (overshoot, "Overshoot", "%"),
    "settling_time": (settling_time, "Settling time", "s"),
    "rms_error": (rms_error, "RMS tracking error", "deg"),
    "max_error": (max_error, "Max tracking error", "deg"),
    "rms_surface_rate": (rms_surface_rate, "RMS elevator rate", "deg/s"),
    "max_surface": (max_surface, "Max elevator deflection", "deg"),
}
