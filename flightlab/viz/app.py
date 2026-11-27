"""FlightLab viewer: serves the browser client for a live run or a replay."""

import sys
import threading
import webbrowser

from flightlab.viz.runner import Runner
from flightlab.viz.server import ViewerServer
from flightlab.viz.sources import LiveSource, ReplaySource  # noqa: F401  (re-exported)

SCREENSHOT_SIZE = (1500, 900)


def show(source, chapter, screenshot=None, until=None, actions=None, open_browser=True,
         host="127.0.0.1", port=0):
    """Serve the viewer until Ctrl+C.

    With ``screenshot``, advance to sim time ``until`` (applying ``actions``, a
    list of (t, message) pairs), save a PNG of the page with headless Chromium,
    and return.
    """
    runner = Runner(source, chapter)
    if screenshot:
        runner.paused = True
        for t_action, msg in sorted(actions or [], key=lambda a: a[0]):
            runner.advance_to(t_action)
            runner.apply(msg)
        if until is not None:
            runner.advance_to(until)
    server = ViewerServer(runner, chapter, host=host, port=port).start()
    runner.start()
    try:
        if screenshot:
            _screenshot(server.url, screenshot)
            return runner
        print(f"\nFlightLab viewer: {server.url}", flush=True)
        if not open_browser or not webbrowser.open(server.url):
            print("Open that link in your web browser.")
        print("Press Ctrl+C here to stop.\n", flush=True)
        stop = threading.Event()
        while not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        print()
    finally:
        runner.stop()
        server.stop()
        if not screenshot:
            runner.save_log()
    return runner


def _screenshot(url, path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Screenshots need Playwright: uv sync --extra browser, then "
              "uv run playwright install chromium", file=sys.stderr)
        raise SystemExit(1)
    width, height = SCREENSHOT_SIZE
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url)
        page.wait_for_selector("body[data-ready='1']", timeout=15000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(path))
        browser.close()
    print(f"Saved {path}")
