"""Chapter configuration (chapters/<id>_<name>/chapter.yaml)."""

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from flightlab.paths import CHAPTERS_DIR

DEFAULTS = {
    "rig": "pitch_gimbal",
    "aircraft": "trainer",
    "duration_s": 20.0,
    "controller_rate_hz": 50.0,
    "tunnel": {"airspeed_mps": 55.0, "flow_angle_deg": 0.0},
    "actuators": "ideal",
    "initial": {"theta_deg": 0.0},
    "reference": {},
    "observations": {"ref": [], "sensors": [], "truth": False},
    "grading": None,
    "viewer": {"unlock": []},
}

# Viewer elements a chapter can unlock (chapter.yaml: viewer.unlock). Each one
# stays visible in every later chapter, so the viewer grows with the course.
# Always shown: the aircraft, the pitch and elevator plots, play/pause, reset.
# "Your signals" appears by itself once the controller calls self.log().
VIEWER_FEATURES = {
    "kick": "Kick buttons",
    "manual": "Fly by hand (slider and arrow keys)",
    "tunnel": "Wind tunnel panel, air arrow, angle of attack (side view, readout, pitch plot), tunnel plot",
    "theta_cmd": "Commanded pitch angle (plot trace and readout)",
    "sim_step": "Step button and playback speed",
    "pitch_rate": "Pitch rate plot and readout",
    "elevator_cmd": "Commanded vs actual elevator (plot trace and ghost surface)",
}


def normalize_id(chapter_id):
    """'1.2' -> '1.02', '1.02_proportional' -> '1.02'."""
    text = str(chapter_id).split("_")[0]
    try:
        part, num = text.split(".")
        return f"{int(part)}.{int(num):02d}"
    except ValueError:
        raise ValueError(f"Chapter ids look like 1.03, got '{chapter_id}'") from None


def student_filename(chapter_id):
    """'1.03' -> 'ch01_03.py'."""
    part, num = normalize_id(chapter_id).split(".")
    return f"ch{int(part):02d}_{int(num):02d}.py"


@dataclass
class Chapter:
    id: str
    title: str
    folder: Path
    config: dict = field(repr=False)

    def __getattr__(self, name):
        try:
            return self.__dict__["config"][name]
        except KeyError:
            raise AttributeError(name) from None

    @property
    def guide_path(self):
        return self.folder / "GUIDE.md"

    @property
    def graded(self):
        return bool(self.config.get("grading"))


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def all_chapters():
    """All chapters, sorted by id."""
    chapters = []
    for path in sorted(CHAPTERS_DIR.glob("*/chapter.yaml")):
        chapters.append(load_chapter_file(path))
    chapters.sort(key=lambda c: tuple(int(p) for p in c.id.split(".")))
    return chapters


def load_chapter_file(path):
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    config = _merge(DEFAULTS, raw)
    cid = normalize_id(raw.get("id", path.parent.name))
    unknown = set(config["viewer"]["unlock"]) - set(VIEWER_FEATURES)
    if unknown:
        raise ValueError(f"{path}: unknown viewer.unlock entries {sorted(unknown)}; "
                         f"known: {sorted(VIEWER_FEATURES)}")
    return Chapter(id=cid, title=raw.get("title", path.parent.name), folder=path.parent,
                   config=config)


def viewer_features(chapter):
    """Viewer elements unlocked by this chapter and every chapter before it."""
    key = tuple(int(p) for p in chapter.id.split("."))
    unlocked = set()
    for ch in all_chapters():
        if tuple(int(p) for p in ch.id.split(".")) <= key:
            unlocked.update(ch.config["viewer"]["unlock"])
    unlocked.update(chapter.config["viewer"]["unlock"])
    return sorted(unlocked)


def load_chapter(chapter_id):
    cid = normalize_id(chapter_id)
    for ch in all_chapters():
        if ch.id == cid:
            return ch
    available = ", ".join(c.id for c in all_chapters())
    raise ValueError(f"No chapter {cid}. Available: {available}")
