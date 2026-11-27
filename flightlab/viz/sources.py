"""What the viewer plays: a live Simulation, or a saved RunLog."""

import math


class LiveSource:
    """Runs a Simulation as the viewer plays."""

    live = True

    def __init__(self, sim):
        self.sim = sim

    @property
    def log(self):
        return self.sim.log

    @property
    def t(self):
        return self.sim.t

    @property
    def mode(self):
        return self.sim.mode

    @property
    def ctrl_dt(self):
        return self.sim.ctrl_dt

    def end_index(self):
        """Number of log rows the viewer may show."""
        return self.log.n

    def value(self, name, default=math.nan):
        return self.log.last(name, default)


class ReplaySource:
    """Plays back a saved RunLog on its own clock."""

    live = False
    mode = "replay"
    ctrl_dt = 0.02

    def __init__(self, log):
        self.log = log
        self.t = 0.0
        self.duration = float(log["t"][-1]) if log.n else 0.0

    def advance(self, dt):
        self.t = min(self.duration, self.t + dt)

    def reset(self):
        self.t = 0.0

    def end_index(self):
        return self.log.index_at(self.t) + 1 if self.log.n else 0

    def value(self, name, default=math.nan):
        if name not in self.log or self.log.n == 0:
            return default
        return self.log[name][self.log.index_at(self.t)]
