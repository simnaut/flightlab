"""Load aircraft parameter files (aircraft/*.yaml)."""

from types import SimpleNamespace

import yaml

from flightlab.paths import AIRCRAFT_DIR


def _to_namespace(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    return obj


def load_aircraft(name="trainer"):
    """Return the aircraft parameters as nested attribute objects.

    Example: ``ac.aero.Cm_alpha``, ``ac.geometry.S``.
    """
    path = AIRCRAFT_DIR / f"{name}.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return _to_namespace(data)
