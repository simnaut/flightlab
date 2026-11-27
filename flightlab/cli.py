"""Command-line interface: ``flightlab <command>``."""

import argparse
import shutil
import sys
from pathlib import Path

from flightlab.paths import RUNS_DIR, STUDENT_DIR
from flightlab.scenario.chapter import all_chapters, load_chapter, normalize_id, student_filename

TEMPLATE = STUDENT_DIR / "ch01_00.py"


def _student_file(chapter_id, override=None):
    if override:
        return Path(override)
    return STUDENT_DIR / student_filename(chapter_id)


def cmd_list(args):
    from flightlab.grade import load_progress
    progress = load_progress()
    print(f"{'':2}{'Chapter':<9}{'Title':<34}{'Your file':<14}Status")
    for ch in all_chapters():
        f = STUDENT_DIR / student_filename(ch.id)
        entry = progress.get(ch.id, {})
        if not ch.graded:
            status = "explore (not graded)"
        elif entry.get("passed"):
            status = "PASSED"
        elif entry:
            status = "not passed yet"
        else:
            status = "-"
        print(f"  {ch.id:<9}{ch.title:<34}{f.name if f.exists() else '-':<14}{status}")


def cmd_guide(args):
    ch = load_chapter(args.chapter)
    print(ch.guide_path.read_text())
    print(f"\n(Rendered with equations: open {ch.guide_path.relative_to(ch.folder.parents[1])} "
          f"on GitHub.)")


def cmd_new(args):
    cid = normalize_id(args.chapter)
    load_chapter(cid)   # validate
    target = STUDENT_DIR / student_filename(cid)
    if target.exists():
        print(f"{target.relative_to(STUDENT_DIR.parent)} already exists; not overwriting.")
        return 1
    # Start from the most recent earlier chapter file, else the template
    earlier = [c for c in all_chapters()
               if tuple(map(int, c.id.split("."))) < tuple(map(int, cid.split(".")))]
    source = TEMPLATE
    for ch in reversed(earlier):
        f = STUDENT_DIR / student_filename(ch.id)
        if f.exists():
            source = f
            break
    shutil.copy(source, target)
    print(f"Created {target.relative_to(STUDENT_DIR.parent)} (copied from {source.name}).")
    print(f"Read the guide:  flightlab guide {cid}")
    print(f"Run it:          flightlab run {cid}")
    return 0


def cmd_run(args):
    from flightlab.loader import ControllerLoadError, load_controller
    from flightlab.sim.simulation import Simulation
    from flightlab.viz.app import LiveSource, show

    ch = load_chapter(args.chapter)
    mode = "manual" if args.manual else "open_loop" if args.open_loop else "controller"
    controller, path = None, None
    if mode == "controller":
        path = _student_file(ch.id, args.controller)
        if not path.exists():
            print(f"No controller file {path.relative_to(STUDENT_DIR.parent)} yet.")
            print(f"Create it with:   flightlab new {ch.id}")
            print(f"Or fly by hand:   flightlab run {ch.id} --manual")
            return 1
        try:
            controller = load_controller(path)
        except ControllerLoadError as exc:
            print(exc)
            return 1
        print(f"Running chapter {ch.id} with {path}")
    sim = Simulation(ch, controller, mode=mode, controller_path=path)
    actions = []
    if args.kick_at is not None:
        actions.append((args.kick_at, {"type": "kick", "sign": 1}))
    show(LiveSource(sim), ch, screenshot=args.screenshot, until=args.until, actions=actions,
         host=args.host, port=args.port)
    return 0


def cmd_grade(args):
    from flightlab.grade import grade
    ch = load_chapter(args.chapter)
    path = _student_file(ch.id, args.controller)
    if not path.exists():
        print(f"No controller file {path}. Create it with: flightlab new {ch.id}")
        return 1
    result = grade(ch, path, save_runs=not args.no_save,
                   record_progress=args.controller is None)
    return 0 if result.passed else 2


def cmd_replay(args):
    from flightlab.scenario.chapter import load_chapter_file
    from flightlab.sim.log import RunLog
    from flightlab.viz.app import ReplaySource, show

    folder = Path(args.folder)
    if not (folder / "meta.json").exists():
        # Allow "latest"
        if args.folder == "latest":
            runs = sorted(p for p in RUNS_DIR.rglob("meta.json"))
            if not runs:
                print("No saved runs yet.")
                return 1
            folder = max(runs, key=lambda p: p.stat().st_mtime).parent
        else:
            print(f"{folder} is not a run folder (no meta.json).")
            return 1
    log = RunLog.load(folder)
    ch = load_chapter(log.meta["chapter"])
    print(f"Replaying {folder}")
    show(ReplaySource(log), ch, screenshot=args.screenshot, until=args.until,
         host=args.host, port=args.port)
    return 0


def _viewer_args(p):
    p.add_argument("--host", default="127.0.0.1",
                   help="address the viewer listens on (default: this computer only). "
                        "Use your Tailscale/LAN IP to open the viewer from another device.")
    p.add_argument("--port", type=int, default=0,
                   help="viewer port (default: any free port)")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="flightlab",
        description="FlightLab: learn flight control one chapter at a time.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list chapters and your progress").set_defaults(fn=cmd_list)

    p = sub.add_parser("guide", help="print a chapter's guide")
    p.add_argument("chapter")
    p.set_defaults(fn=cmd_guide)

    p = sub.add_parser("new", help="start a chapter (copies your previous chapter's file)")
    p.add_argument("chapter")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("run", help="run a chapter in the live viewer (opens in your browser)")
    p.add_argument("chapter")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--manual", action="store_true", help="fly it yourself")
    g.add_argument("--open-loop", action="store_true", help="no controller, surfaces neutral")
    p.add_argument("--controller", help="use this controller file instead of student/chNN_MM.py")
    p.add_argument("--screenshot", help=argparse.SUPPRESS)
    p.add_argument("--until", type=float, help=argparse.SUPPRESS)
    p.add_argument("--kick-at", type=float, help=argparse.SUPPRESS)
    _viewer_args(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("grade", help="grade a chapter (headless)")
    p.add_argument("chapter")
    p.add_argument("--controller", help="grade this file instead of student/chNN_MM.py")
    p.add_argument("--no-save", action="store_true", help="don't save run logs")
    p.set_defaults(fn=cmd_grade)

    p = sub.add_parser("replay", help="replay a saved run (folder path, or 'latest')")
    p.add_argument("folder")
    p.add_argument("--screenshot", help=argparse.SUPPRESS)
    p.add_argument("--until", type=float, help=argparse.SUPPRESS)
    _viewer_args(p)
    p.set_defaults(fn=cmd_replay)

    args = parser.parse_args(argv)
    try:
        return args.fn(args) or 0
    except ValueError as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
