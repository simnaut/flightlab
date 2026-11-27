"""The browser viewer: server protocol (headless) and a browser smoke test."""

import json
import time
import urllib.error
import urllib.request

import pytest
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from flightlab import Command, ControllerBase
from flightlab.scenario.chapter import load_chapter
from flightlab.sim.simulation import Simulation
from flightlab.viz.runner import Runner
from flightlab.viz.server import ViewerServer
from flightlab.viz.sources import LiveSource


class LoggingController(ControllerBase):
    def update(self, observations, dt):
        error = observations.ref.theta - observations.sensors.theta
        self.log("error", error)
        return Command(elevator=-2.0 * error)


@pytest.fixture
def viewer():
    ch = load_chapter("1.00")
    sim = Simulation(ch, LoggingController())
    runner = Runner(LiveSource(sim), ch)
    server = ViewerServer(runner, ch).start()
    runner.start()
    yield sim, runner, server
    runner.stop()
    server.stop()


def _ws_url(server, token=None):
    return f"ws://{server.host}:{server.port}/ws?token={token or server.token}"


def _recv(ws, kind, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = json.loads(ws.recv(timeout=timeout))
        if msg["type"] == kind:
            return msg
    raise AssertionError(f"no {kind} message")


def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_static_files_served_and_contained(viewer):
    _, _, server = viewer
    base = f"http://{server.host}:{server.port}"
    with urllib.request.urlopen(base + "/") as r:
        assert r.headers["Content-Type"].startswith("text/html")
        assert b"importmap" in r.read()
    with urllib.request.urlopen(base + "/vendor/preact.mjs") as r:
        assert r.headers["Content-Type"].startswith("text/javascript")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/../server.py")
    assert exc.value.code == 404


def test_websocket_requires_token(viewer):
    _, _, server = viewer
    with pytest.raises(InvalidStatus):
        connect(_ws_url(server, token="wrong"))


def test_hello_frames_and_inputs(viewer):
    sim, runner, server = viewer
    with connect(_ws_url(server)) as ws:
        hello = _recv(ws, "hello")
        assert hello["chapter"]["id"] == "1.00"
        assert hello["live"] is True and hello["mode"] == "controller"

        frame = _recv(ws, "frame")
        assert frame["reset"] is True                       # first frame starts the log
        assert {"t", "theta", "de"} <= set(frame["rows"])
        while "log.error" not in frame.get("rows", {}):     # appears once the controller runs
            frame = _recv(ws, "frame")
        assert not frame["reset"]
        assert not any(name.startswith("x.") for name in frame["rows"])

        ws.send(json.dumps({"type": "kick", "sign": 1}))
        ws.send(json.dumps({"type": "set_air", "airspeed": 40, "flow_angle": 0.1, "smooth": False}))
        ws.send(json.dumps({"type": "elevator", "value": "not a number"}))   # ignored
        ws.send("not json")                                                  # ignored
        assert _wait_for(lambda: {"kick", "air"} <= {e["kind"] for e in sim.log.events})
        assert sim.tunnel.target == (40.0, 0.1)

        ws.send(json.dumps({"type": "pause"}))
        assert _wait_for(lambda: runner.state()["run"] == "paused")
        t_paused = sim.t
        ws.send(json.dumps({"type": "step"}))
        assert _wait_for(lambda: sim.t >= t_paused + sim.ctrl_dt - 1e-9)
        time.sleep(0.1)                                     # and then it stays paused
        assert sim.t == pytest.approx(t_paused + sim.ctrl_dt)

        ws.send(json.dumps({"type": "reset"}))
        frame = _recv(ws, "frame")
        while not frame.get("reset"):
            frame = _recv(ws, "frame")
        assert frame["state"]["generation"] == 1
        assert frame["rows"]["t"][0] == 0.0


def test_controller_error_pauses_and_is_reported():
    class Broken(ControllerBase):
        def update(self, observations, dt):
            return 1.0 / 0.0

    ch = load_chapter("1.00")
    runner = Runner(LiveSource(Simulation(ch, Broken())), ch)
    runner.advance(0.1)
    state = runner.state()
    assert state["run"] == "error"
    assert "ZeroDivisionError" in state["error"]["details"]
    runner.apply({"type": "resume"})                         # can't resume past an error
    assert runner.state()["run"] == "error"


# ------------------------------------------------------------ browser smoke
def _chromium_available():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chromium_available(),
                    reason="needs Playwright + Chromium (uv sync --extra browser; "
                           "playwright install chromium)")
def test_browser_smoke(viewer):
    from playwright.sync_api import sync_playwright

    sim, runner, server = viewer
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(server.url)
        page.wait_for_selector("body[data-ready='1']", timeout=15000)

        # The student's self.log() signal shows up in the picker, checked
        page.get_by_label("error").wait_for(timeout=5000)
        assert page.get_by_label("error").is_checked()

        page.get_by_role("button", name="Kick ▲").click()
        page.keyboard.press("ArrowUp")                       # switches to manual, pushes
        page.locator(".air-handle").drag_to(page.locator(".view-canvas"),
                                            target_position={"x": 700, "y": 200})
        page.get_by_role("button", name="❚❚ Pause").click()
        assert _wait_for(lambda: runner.state()["run"] == "paused")
        page.get_by_role("button", name="▶ Play").wait_for()
        browser.close()

    kinds = {e["kind"] for e in sim.log.events}
    assert {"kick", "manual", "manual_elevator", "air"} <= kinds
    assert sim.manual and sim.manual_elevator > 0           # ↑ = push = nose down
    assert errors == []
