"""Local web server for the viewer: static client files + one WebSocket.

Listens on 127.0.0.1 only. The page URL carries a random per-run token that
the WebSocket must present: any web page can open a WebSocket to localhost,
and without the token another site could drive the student's run.

Messages are JSON objects with a ``type`` (see HARNESS_DESIGN.md §5.1):
    server -> browser: hello (once), frame (~30 Hz)
    browser -> server: pause, resume, step, speed, reset, kick, set_air,
                       reset_air, manual, elevator
"""

import asyncio
import json
import math
import secrets
import socket
import threading
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from flightlab.scenario.chapter import viewer_features

PROTOCOL_VERSION = 1
FRAME_HZ = 30
WEB_DIR = Path(__file__).parent / "web"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".md": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8",
                 ".svg": "image/svg+xml"}

DEG = math.pi / 180.0
AIRSPEED_RANGE = (15.0, 70.0)        # wind tunnel panel limits (m/s)
FLOW_RANGE_DEG = 15.0                # +- vertical flow angle
ELEVATOR_RANGE_DEG = 25.0            # +- manual elevator slider


def hello_message(runner, chapter, features=None):
    src = runner.source
    cfg = chapter.config
    tunnel = cfg["tunnel"]
    msg = {
        "type": "hello",
        "protocol": PROTOCOL_VERSION,
        "chapter": {"id": chapter.id, "title": chapter.title, "rig": cfg["rig"],
                    "duration": float(cfg["duration_s"])},
        "mode": src.mode,
        "live": src.live,
        "ctrl_dt": src.ctrl_dt,
        "tunnel": {"airspeed": float(tunnel["airspeed_mps"]),
                   "flow_angle": float(tunnel["flow_angle_deg"]) * DEG,
                   "airspeed_range": AIRSPEED_RANGE,
                   "flow_range": FLOW_RANGE_DEG * DEG},
        "elevator_range": ELEVATOR_RANGE_DEG * DEG,
        "features": viewer_features(chapter) if features is None else features,
    }
    if not src.live:
        msg["replay"] = {"duration": src.duration}
    return msg


def _static(path):
    """(status, headers, body) for a static file under WEB_DIR."""
    rel = "index.html" if path in ("", "/") else path.lstrip("/")
    target = (WEB_DIR / rel).resolve()
    if WEB_DIR.resolve() not in target.parents or not target.is_file():
        return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not found"
    ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
    return HTTPStatus.OK, ctype, target.read_bytes()


class ViewerServer:
    """Runs the asyncio server in its own thread."""

    def __init__(self, runner, chapter, host="127.0.0.1", port=0):
        self.runner = runner
        self.chapter = chapter
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe(16)
        self.features = viewer_features(chapter)
        self.clients = 0
        self._loop = None
        self._stopped = None
        self._ready = threading.Event()
        self._start_error = None
        self._thread = threading.Thread(target=self._run, name="flightlab-viz", daemon=True)

    @property
    def url(self):
        host = socket.gethostname() if self.host in ("0.0.0.0", "::", "") else self.host
        return f"http://{host}:{self.port}/?token={self.token}"

    def start(self):
        self._thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("The viewer server did not start within 10 s.")
        if self._start_error is not None:
            raise RuntimeError(f"The viewer server could not listen on "
                               f"{self.host}:{self.port}: {self._start_error}") from self._start_error
        return self

    def stop(self):
        if self._loop and self._stopped:
            self._loop.call_soon_threadsafe(self._stopped.set_result, None)
            self._thread.join(2)

    # ------------------------------------------------------------- asyncio
    def _run(self):
        try:
            asyncio.run(self._main())
        except Exception as exc:          # e.g. the port is taken
            if self._ready.is_set():
                raise
            self._start_error = exc
            self._ready.set()

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._stopped = self._loop.create_future()
        async with serve(self._handler, self.host, self.port,
                         process_request=self._process_request) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._stopped

    def _process_request(self, connection, request):
        parts = urlsplit(request.path)
        if parts.path == "/ws":
            token = parse_qs(parts.query).get("token", [""])[0]
            if not secrets.compare_digest(token, self.token):
                return connection.respond(HTTPStatus.FORBIDDEN, "Bad or missing token\n")
            return None                       # go ahead with the WebSocket handshake
        status, ctype, body = _static(parts.path)
        headers = Headers([("Content-Type", ctype), ("Content-Length", str(len(body))),
                           ("Cache-Control", "no-store"), ("Connection", "close")])
        return Response(status.value, status.phrase, headers, body)

    async def _handler(self, ws):
        self.clients += 1
        try:
            await ws.send(json.dumps(hello_message(self.runner, self.chapter, self.features)))
            sender = asyncio.create_task(self._send_frames(ws))
            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except (TypeError, ValueError):
                        continue
                    self.runner.submit(msg)
            finally:
                sender.cancel()
        except ConnectionClosed:
            pass
        finally:
            self.clients -= 1

    async def _send_frames(self, ws):
        generation, cursor = -1, 0
        period = 1.0 / FRAME_HZ
        try:
            while True:
                started = self._loop.time()
                got = await asyncio.to_thread(self.runner.read, generation, cursor)
                frame = {"type": "frame", "state": self.runner.state()}
                if got is not None:
                    generation, cursor, reset, rows = got
                    frame["reset"] = reset
                    frame["rows"] = rows
                await ws.send(json.dumps(frame, allow_nan=False))
                await asyncio.sleep(max(0.0, period - (self._loop.time() - started)))
        except ConnectionClosed:
            pass
