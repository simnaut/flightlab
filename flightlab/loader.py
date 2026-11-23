"""Load the student's controller file."""

import importlib.util
import sys
import traceback
from pathlib import Path

from flightlab.paths import STUDENT_DIR


class ControllerLoadError(Exception):
    pass


def load_controller(path):
    """Import ``path`` and return an instance of its ``Controller`` class."""
    path = Path(path).resolve()
    if not path.exists():
        raise ControllerLoadError(f"Controller file not found: {path}")
    # Let student files import helpers from student/lib and their own folder
    for folder in (str(STUDENT_DIR), str(path.parent)):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    module_name = f"student_controller_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        raise ControllerLoadError(
            f"Could not load {path.name}:\n{traceback.format_exc(limit=-3)}") from None
    cls = getattr(module, "Controller", None)
    if cls is None:
        raise ControllerLoadError(f"{path.name} must define a class named Controller.")
    try:
        return cls()
    except Exception:
        raise ControllerLoadError(
            f"Creating Controller() from {path.name} failed:\n{traceback.format_exc(limit=-3)}"
        ) from None
