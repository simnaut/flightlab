"""The harness gives beginner-friendly errors for common controller mistakes."""

import pytest

from flightlab import Command, ControllerBase
from flightlab.scenario.chapter import load_chapter
from flightlab.sim.simulation import ControllerError, Simulation


def run_briefly(controller):
    sim = Simulation(load_chapter("1.02"), controller)
    sim.run(0.5)
    return sim


class ReturnsNumber(ControllerBase):
    def update(self, observations, dt):
        return 0.1


class ReturnsNone(ControllerBase):
    def update(self, observations, dt):
        pass


class ReturnsNaN(ControllerBase):
    def update(self, observations, dt):
        return Command(elevator=float("nan"))


class Raises(ControllerBase):
    def update(self, observations, dt):
        return 1 / 0


class UsesMissingSensor(ControllerBase):
    def update(self, observations, dt):
        return Command(elevator=observations.sensors.altitude)


@pytest.mark.parametrize("controller, text", [
    (ReturnsNumber(), "Wrap it in a Command"),
    (ReturnsNone(), "forget the return"),
    (ReturnsNaN(), "finite number"),
    (Raises(), "ZeroDivisionError"),
    (UsesMissingSensor(), "Available: theta, q"),
])
def test_helpful_errors(controller, text):
    with pytest.raises(ControllerError) as info:
        run_briefly(controller)
    assert text in str(info.value)


def test_observations_and_telemetry():
    seen = {}

    class Spy(ControllerBase):
        def update(self, observations, dt):
            seen["dt"] = dt
            seen["ref"] = observations.ref.theta
            seen["truth_alpha"] = observations.truth.alpha
            self.log("hello", 42)
            return Command()

    sim = run_briefly(Spy())
    assert seen["dt"] == pytest.approx(0.02)
    assert "log.hello" in sim.log
    assert sim.log.last("log.hello") == 42


def test_controller_runs_at_its_rate():
    calls = []

    class Counter(ControllerBase):
        def update(self, observations, dt):
            calls.append(observations.t)
            return Command()

    sim = Simulation(load_chapter("1.02"), Counter())
    sim.run(1.0)
    assert len(calls) == 50


def test_log_round_trip(tmp_path):
    sim = Simulation(load_chapter("1.02"), None, mode="open_loop")
    sim.kick(+1)
    sim.run(2.0)
    folder = sim.log.save(tmp_path / "run")
    from flightlab.sim.log import RunLog
    loaded = RunLog.load(folder)
    assert loaded.n == sim.log.n
    assert loaded.meta["sandbox"] is True
    assert loaded.events[0]["kind"] == "kick"
