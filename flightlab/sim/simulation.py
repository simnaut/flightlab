"""The simulation loop: plant + rig + scenario + controller + logging.

Rates (HARNESS_DESIGN.md §2):
    physics     400 Hz (RK4)
    controller  chapter's controller_rate_hz (default 50 Hz)
    log         100 Hz
Sim time never depends on wall-clock time.
"""

import math
import os
import traceback
from types import SimpleNamespace

import numpy as np

from flightlab.controller import Command, ZeroController
from flightlab.core.dynamics import Environment
from flightlab.core.integrator import rk4_step
from flightlab.core.rigs import make_rig
from flightlab.core.state import IDX, N_COMMANDS, CMD, STATE_NAMES, initial_state, quat_to_euler
from flightlab.models.aircraft import load_aircraft
from flightlab.scenario.reference import Schedule
from flightlab.scenario.tunnel import Tunnel
from flightlab.sim.log import RunLog
from flightlab.sim.observations import build_observations, is_finite_number

PHYSICS_HZ = 400
LOG_HZ = 100
DEG = math.pi / 180.0

_HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ControllerError(Exception):
    """The student's controller raised an exception or returned something invalid."""

    def __init__(self, message, details=""):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self):
        return f"{self.message}\n{self.details}".rstrip()


class SimulationError(Exception):
    """The simulation itself failed (e.g., the state became NaN)."""


def _student_traceback(exc):
    """Traceback text with harness frames removed, so the student sees their code."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__)
              if not f.filename.startswith(_HARNESS_DIR)]
    lines = traceback.format_list(frames) if frames else []
    lines += traceback.format_exception_only(type(exc), exc)
    return "".join(lines)


class Simulation:
    def __init__(self, chapter, controller=None, mode="controller", seed=0,
                 initial=None, controller_path=None, physics_hz=PHYSICS_HZ):
        self.chapter = chapter
        cfg = chapter.config
        self.cfg = cfg
        self.mode = mode
        self.seed = seed
        self.controller_path = controller_path
        self.ac = load_aircraft(cfg["aircraft"])
        self.rig = make_rig(cfg["rig"])

        if mode == "open_loop" or controller is None:
            controller = ZeroController()
        self.controller = controller

        self.initial = dict(cfg["initial"])
        self.initial.update(initial or {})

        tunnel = cfg["tunnel"]
        self.tunnel = Tunnel(tunnel["airspeed_mps"], tunnel["flow_angle_deg"] * DEG)

        self.references = {}
        for key, points in (cfg.get("reference") or {}).items():
            name, scale = (key[:-4], DEG) if key.endswith("_deg") else (key, 1.0)
            self.references[name] = Schedule(points, scale)

        self.dt = 1.0 / physics_hz
        rate = float(cfg["controller_rate_hz"])
        self.ctrl_every = max(1, round(physics_hz / rate))
        self.ctrl_dt = self.ctrl_every * self.dt
        self.log_every = max(1, round(physics_hz / LOG_HZ))

        self.reset()

    # ------------------------------------------------------------------ setup
    def reset(self):
        init = self.initial
        self.x = initial_state(self.ac, theta=init.get("theta_deg", 0.0) * DEG)
        self.x[IDX.q] = init.get("q_dps", 0.0) * DEG
        self.u = np.zeros(N_COMMANDS)
        self.t = 0.0
        self.k = 0
        self.kick_until = -1.0
        self.kick_sign = 0.0
        self.manual = self.mode == "manual"
        self.manual_elevator = 0.0
        self.telemetry = {}
        self.error = None
        self.tunnel.reset(0.0, smooth=False)
        self.env = Environment(rho=1.225 if self.rig.test_stand else None)
        self.log = RunLog(meta={
            "chapter": self.chapter.id,
            "title": self.chapter.title,
            "rig": self.rig.name,
            "mode": self.mode,
            "seed": self.seed,
            "initial": self.initial,
            "controller": str(self.controller_path) if self.controller_path else None,
            "config": self.cfg,
            "sandbox": False,
        })
        self._update_outputs()
        self.controller.reset(self.info())
        self._record()

    def info(self):
        hard = self.ac.surfaces
        return SimpleNamespace(
            chapter=self.chapter.id,
            title=self.chapter.title,
            rig=self.rig.name,
            controller_rate_hz=1.0 / self.ctrl_dt,
            dt=self.ctrl_dt,
            elevator_limit=hard.elevator_hard_limit,
            aircraft=self.ac.name,
        )

    # ------------------------------------------------------------- accessors
    @property
    def euler(self):
        return quat_to_euler(self.x[IDX.quat])

    def reference_value(self, name, t=None):
        sched = self.references.get(name)
        return 0.0 if sched is None else sched(self.t if t is None else t)

    def _update_outputs(self):
        self._apply_env(self.t)
        _, self.outputs = self.rig.evaluate(self.x, self.u, self.ac, self.env)

    def _apply_env(self, t):
        if self.rig.test_stand:
            self.env.air_velocity_ned = self.tunnel.air_velocity_ned(t)
        moment = np.zeros(3)
        if t < self.kick_until:
            moment[self.rig.kick_axis] = self.kick_sign * self.rig.kick_moment
        self.env.ext_moment_body = moment

    # ---------------------------------------------------------- interaction
    def _sandbox(self):
        self.log.meta["sandbox"] = True

    def kick(self, sign=1.0):
        """Apply a short moment pulse (positive = nose up)."""
        self.kick_sign = math.copysign(1.0, sign)
        self.kick_until = self.t + self.rig.kick_duration
        self.log.event(self.t, "kick", sign=self.kick_sign)
        self._sandbox()

    def set_air(self, airspeed, flow_angle, smooth=True):
        """Wind tunnel: set airspeed (m/s) and flow angle (rad)."""
        self.tunnel.set_target(self.t, airspeed, flow_angle, smooth)
        self.log.event(self.t, "air", airspeed=airspeed, flow_angle_deg=flow_angle / DEG,
                       smooth=smooth)
        self._sandbox()

    def reset_air(self, smooth=True):
        self.tunnel.reset(self.t, smooth)
        self.log.event(self.t, "air_reset", smooth=smooth)

    def set_manual(self, enabled):
        self.manual = bool(enabled)
        self.log.event(self.t, "manual", enabled=self.manual)
        if enabled:
            self._sandbox()

    def set_manual_elevator(self, value):
        self.manual_elevator = float(value)
        self.log.event(self.t, "manual_elevator", value_deg=value / DEG)

    # ------------------------------------------------------------- stepping
    def _control(self):
        if self.manual:
            cmd = Command(elevator=self.manual_elevator)
            self.telemetry = {}
        else:
            obs = build_observations(self, self.cfg["observations"])
            try:
                cmd = self.controller.update(obs, self.ctrl_dt)
            except Exception as exc:
                raise ControllerError(
                    f"Your controller raised an error at t = {self.t:.2f} s:",
                    _student_traceback(exc)) from exc
            self._check_command(cmd)
            take = getattr(self.controller, "_take_telemetry", None)
            if take:
                self.telemetry.update(take())

        self.u[:] = [cmd.elevator, cmd.aileron, cmd.rudder, cmd.throttle, cmd.brake]
        # Ideal actuators: surfaces jump to the command (within the hard stop)
        if self.cfg["actuators"] == "ideal":
            s = self.ac.surfaces
            self.x[IDX.de] = np.clip(cmd.elevator, -s.elevator_hard_limit, s.elevator_hard_limit)
            self.x[IDX.da] = np.clip(cmd.aileron, -s.aileron_hard_limit, s.aileron_hard_limit)
            self.x[IDX.dr] = np.clip(cmd.rudder, -s.rudder_hard_limit, s.rudder_hard_limit)

    def _check_command(self, cmd):
        if cmd is None:
            raise ControllerError(
                "update() returned None.",
                "Did you forget the return statement? End update() with something like:\n"
                "    return Command(elevator=...)")
        if not isinstance(cmd, Command):
            hint = ""
            if is_finite_number(cmd):
                hint = (f"It looks like you returned a number ({cmd!r}). "
                        f"Wrap it in a Command:\n    return Command(elevator={cmd!r})")
            raise ControllerError(
                f"update() must return a Command, but returned a {type(cmd).__name__}.", hint)
        for name in ("elevator", "aileron", "rudder", "throttle", "brake"):
            value = getattr(cmd, name)
            if not is_finite_number(value):
                raise ControllerError(
                    f"Command.{name} is {value!r} at t = {self.t:.2f} s; it must be a finite number.",
                    "NaN or inf usually comes from dividing by zero or from a value that grew "
                    "without bound (e.g., an integrator).")

    def step(self):
        """Advance one physics step."""
        if self.k % self.ctrl_every == 0:
            self._control()
        t = self.t
        self._apply_env(t)
        u, ac, env, rig = self.u, self.ac, self.env, self.rig
        x = rk4_step(lambda s: rig.derivative(s, u, ac, env), self.x, self.dt)
        x[IDX.quat] /= np.linalg.norm(x[IDX.quat])
        if not np.all(np.isfinite(x)):
            raise SimulationError(f"The simulation became unstable (NaN) at t = {t:.2f} s.")
        self.x = x
        self.k += 1
        self.t = self.k * self.dt
        if self.k % self.log_every == 0:
            self._update_outputs()
            self._record()

    def advance(self, t_target):
        """Step until sim time reaches t_target."""
        while self.t < t_target - 1e-9:
            self.step()

    def run(self, duration=None):
        self.advance(self.cfg["duration_s"] if duration is None else duration)
        return self.log

    # -------------------------------------------------------------- logging
    def _record(self):
        x, out = self.x, self.outputs
        phi, theta, psi = self.euler
        airspeed_t, flow_t = self.tunnel.value(self.t)
        row = {
            "t": self.t,
            "theta": theta, "phi": phi, "psi": psi,
            "p": x[IDX.p], "q": x[IDX.q], "r": x[IDX.r],
            "alpha": out.alpha, "beta": out.beta, "airspeed": out.airspeed,
            "de": x[IDX.de], "da": x[IDX.da], "dr": x[IDX.dr],
            "de_cmd": self.u[CMD.elevator], "da_cmd": self.u[CMD.aileron],
            "dr_cmd": self.u[CMD.rudder], "throttle": self.u[CMD.throttle],
            "tunnel_airspeed": airspeed_t, "tunnel_flow": flow_t,
            "kick": self.kick_sign if self.t < self.kick_until else 0.0,
            "manual": 1.0 if self.manual else 0.0,
            "mass": out.mass, "cg_x": out.cg_x,
        }
        for name in self.references:
            row[f"ref_{name}"] = self.reference_value(name)
        for i, name in enumerate(STATE_NAMES):
            row[f"x.{name}"] = x[i]
        for name, value in self.telemetry.items():
            row[f"log.{name}"] = value
        self.log.record(row)
