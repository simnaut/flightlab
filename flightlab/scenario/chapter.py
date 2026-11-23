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
    return Chapter(id=cid, title=raw.get("title", path.parent.name), folder=path.parent,
                   config=config)


def load_chapter(chapter_id):
    cid = normalize_id(chapter_id)
    for ch in all_chapters():
        if ch.id == cid:
            return ch
    available = ", ".join(c.id for c in all_chapters())
    raise ValueError(f"No chapter {cid}. Available: {available}")
