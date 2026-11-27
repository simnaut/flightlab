"""The sim thread: owns the clock and applies the viewer's inputs.

The browser never touches the Simulation. Its messages are queued and applied
here, between physics steps, so every input lands at a definite sim time and
is logged as an event (replays stay exact).

The log is read by the server thread under ``lock``. The sim thread holds it
for short slices of physics steps and then yields, so readers always get a
turn. If the student stops at a breakpoint in their controller, only reads
block: the server notices and tells the browser.
"""

import math
import queue
import sys
import threading
import time
import traceback

from flightlab.sim.simulation import ControllerError, SimulationError

TICK_S = 1 / 60          # how often the sim thread wakes to advance the clock
MAX_WALL_DT = 0.1        # never catch up more than this per tick (after a stall)
SPEED_RANGE = (0.05, 16.0)
HISTORY_S = 30.0         # how far back a newly connected browser gets the log
BUSY_AFTER_S = 0.5       # a step taking this long is reported as "busy"
SLICE_S = 0.008          # hold the lock at most this long before letting readers in
RESYNC_S = 0.01          # if the sim is this far from its intended time, stop catching up

LIVE_ONLY = {"kick", "set_air", "reset_air", "manual", "elevator"}


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _column(arr):
    """A JSON-safe list: NaN becomes null."""
    return [None if v != v else v for v in arr.tolist()]


class Runner:
    def __init__(self, source, chapter):
        self.source = source
        self.chapter = chapter
        self.lock = threading.Lock()
        self.inputs = queue.Queue()
        self.paused = False
        self.speed = 1.0
        self.error = None            # {"message", "details"} after a controller/sim error
        self.generation = 0          # bumped on reset; tells readers to start over
        self.saved_folder = None
        self._busy_since = None
        self.actual_speed = None     # measured sim-time / wall-time while running
        self._intended = None        # sim time the clock should be at (None = resync)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="flightlab-sim", daemon=True)

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self._thread.start()

    def stop(self, timeout=1.0):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout)

    def submit(self, msg):
        """Queue a message from the browser (called from the server thread)."""
        self.inputs.put(msg)

    # ----------------------------------------------------------------- loop
    def _loop(self):
        last = time.perf_counter()
        sim_last = self.source.t
        while not self._stop.is_set():
            self._drain()
            now = time.perf_counter()
            elapsed = now - last
            if not self.paused and self.error is None:
                if elapsed > 0 and self.source.t >= sim_last:
                    # Sim time gained per wall second since the previous tick started
                    rate = (self.source.t - sim_last) / elapsed
                    self.actual_speed = rate if self.actual_speed is None else \
                        0.9 * self.actual_speed + 0.1 * rate
            else:
                self.actual_speed = None
            last, sim_last = now, self.source.t
            if not self.paused and self.error is None:
                self._tick(min(elapsed, MAX_WALL_DT) * self.speed)
            else:
                self._intended = None
            time.sleep(max(0.001, TICK_S - (time.perf_counter() - now)))

    def _drain(self):
        while True:
            try:
                msg = self.inputs.get_nowait()
            except queue.Empty:
                return
            self.apply(msg)

    def _tick(self, dt):
        """Advance the running clock by dt, carrying over each tick's overshoot.

        The sim moves in whole physics steps, so each advance lands up to one
        step past its target. Aiming each tick from the intended time (not from
        where the sim landed) keeps 1x at exactly real time.
        """
        t = self.source.t
        base = self._intended
        if base is None or abs(base - t) > RESYNC_S:
            base = t
        self._intended = base + dt
        self.advance(self._intended - t)

    def advance(self, dt):
        """Advance the clock by dt seconds of sim time (one physics step at a time)."""
        src = self.source
        if not src.live:
            with self.lock:
                src.advance(dt)
            return
        sim = src.sim
        target = sim.t + dt
        try:
            while sim.t < target - 1e-9 and not self._stop.is_set():
                with self.lock:
                    started = self._busy_since = time.perf_counter()
                    try:
                        while sim.t < target - 1e-9 and time.perf_counter() - started < SLICE_S:
                            sim.step()
                    finally:
                        self._busy_since = None
                time.sleep(0)                  # let a waiting reader take the lock
        except (ControllerError, SimulationError) as exc:
            self._fail(getattr(exc, "message", str(exc)), getattr(exc, "details", ""), exc)
        except Exception as exc:   # a harness bug: show it rather than kill the thread
            self._fail(f"Internal error in the simulation at t = {sim.t:.2f} s:",
                       traceback.format_exc(), exc)

    def advance_to(self, t):
        if t > self.source.t:
            self.advance(t - self.source.t)

    def _fail(self, message, details, exc):
        self.error = {"message": message, "details": details}
        self.paused = True
        print(f"\n{message}\n{details}".rstrip(), file=sys.stderr)

    # ------------------------------------------------------------- messages
    def apply(self, msg):
        """Apply one browser message. Unknown or malformed messages are ignored."""
        kind = msg.get("type") if isinstance(msg, dict) else None
        src = self.source
        if kind in LIVE_ONLY and not src.live:
            return
        if kind == "pause":
            self.paused = True
        elif kind == "resume":
            if self.error is None:
                self.paused = False
        elif kind == "step":
            self.paused = True
            if self.error is None:
                self.advance(src.ctrl_dt)
        elif kind == "speed" and _finite(msg.get("value")):
            self.speed = min(max(float(msg["value"]), SPEED_RANGE[0]), SPEED_RANGE[1])
        elif kind == "reset":
            self.reset()
        elif kind == "kick" and _finite(msg.get("sign")):
            with self.lock:
                src.sim.kick(msg["sign"])
        elif kind == "set_air" and _finite(msg.get("airspeed")) and _finite(msg.get("flow_angle")):
            with self.lock:
                src.sim.set_air(float(msg["airspeed"]), float(msg["flow_angle"]),
                                smooth=bool(msg.get("smooth", True)))
        elif kind == "reset_air":
            with self.lock:
                src.sim.reset_air(smooth=bool(msg.get("smooth", True)))
        elif kind == "manual":
            with self.lock:
                src.sim.set_manual(bool(msg.get("enabled")))
        elif kind == "elevator" and _finite(msg.get("value")):
            with self.lock:
                src.sim.set_manual_elevator(float(msg["value"]))

    def reset(self):
        src = self.source
        self._intended = None
        if src.live:
            self.save_log()
            sim = src.sim
            manual, elevator = sim.manual, sim.manual_elevator
            with self.lock:
                self.error = None
                try:
                    sim.reset()
                except (ControllerError, SimulationError) as exc:
                    self._fail(getattr(exc, "message", str(exc)), getattr(exc, "details", ""), exc)
                    self.generation += 1
                    return
                if manual:                    # keep flying by hand across a reset
                    sim.set_manual(True)
                    sim.set_manual_elevator(elevator)
                self.generation += 1
        else:
            with self.lock:
                src.reset()
                self.generation += 1
        self.paused = False

    # ------------------------------------------------------------- reading
    def state(self):
        src = self.source
        busy = self._busy_since is not None and time.perf_counter() - self._busy_since > BUSY_AFTER_S
        if self.error is not None:
            run = "error"
        elif self.paused:
            run = "paused"
        elif not src.live and src.t >= src.duration:
            run = "finished"
        else:
            run = "running"
        out = {"t": src.t, "run": run, "speed": self.speed, "busy": busy,
               "actual_speed": self.actual_speed,
               "generation": self.generation, "error": self.error}
        if src.live:
            sim = src.sim
            airspeed, flow = sim.tunnel.target
            out.update(manual=sim.manual, elevator=sim.manual_elevator,
                       air_target={"airspeed": airspeed, "flow_angle": flow})
        return out

    def read(self, generation, cursor, timeout=0.25):
        """New log rows for a reader at (generation, cursor).

        Returns (generation, cursor, reset, rows) with rows as {channel: [values]},
        or None if the sim thread is holding the lock (e.g., at a breakpoint).
        """
        if not self.lock.acquire(timeout=timeout):
            return None
        try:
            log = self.source.log
            reset = generation != self.generation
            end = self.source.end_index()
            if reset or cursor > end:          # new run, or a replay that restarted
                reset = True
                start = log.index_at(self.source.t - HISTORY_S) if log.n else 0
            else:
                start = cursor
            rows = {}
            if end > start:
                for name in log.names():
                    if not name.startswith("x."):          # state vector: logs only
                        rows[name] = _column(log[name][start:end])
            return self.generation, end, reset, rows
        finally:
            self.lock.release()

    # -------------------------------------------------------------- saving
    def save_log(self):
        src = self.source
        if src.live and src.t > 1.0:
            self.saved_folder = src.log.save(label="live")
            print(f"Run saved to {self.saved_folder}")
