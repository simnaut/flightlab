"""Run logs: named time series plus metadata and interactive events.

A run is saved as a folder:

    runs/<timestamp>_<chapter>_<label>/
        data.npz     one array per channel (all the same length)
        meta.json    chapter, seed, mode, events, resolved config, notes
"""

import json
import math
import time
from pathlib import Path

import numpy as np

from flightlab.paths import RUNS_DIR


class Channel:
    """A growable float array."""

    def __init__(self, n_backfill=0):
        self.data = np.full(max(256, n_backfill * 2), np.nan)
        self.n = n_backfill

    def append(self, value):
        if self.n >= len(self.data):
            self.data = np.concatenate([self.data, np.full(len(self.data), np.nan)])
        self.data[self.n] = value
        self.n += 1

    def array(self):
        return self.data[: self.n]


class RunLog:
    def __init__(self, meta=None):
        self.channels = {}
        self.n = 0
        self.meta = dict(meta or {})
        self.events = []

    def record(self, row):
        """Append one row (a dict of channel -> value)."""
        for name, value in row.items():
            if name not in self.channels:
                self.channels[name] = Channel(n_backfill=self.n)
            self.channels[name].append(value)
        self.n += 1
        for ch in self.channels.values():      # channels missing from this row
            if ch.n < self.n:
                ch.append(math.nan)

    def event(self, t, kind, **data):
        self.events.append({"t": round(float(t), 6), "kind": kind, **data})

    def __getitem__(self, name):
        return self.channels[name].array()

    def __contains__(self, name):
        return name in self.channels

    def names(self):
        return list(self.channels)

    def last(self, name, default=math.nan):
        ch = self.channels.get(name)
        if ch is None or ch.n == 0:
            return default
        return ch.data[ch.n - 1]

    def index_at(self, t):
        """Index of the last row with time <= t."""
        times = self["t"]
        return max(0, int(np.searchsorted(times, t, side="right")) - 1)

    def save(self, folder=None, label="run"):
        if folder is None:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            cid = self.meta.get("chapter", "x")
            folder = RUNS_DIR / f"{stamp}_{cid}_{label}"
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(folder / "data.npz", **{k: c.array() for k, c in self.channels.items()})
        meta = dict(self.meta, events=self.events, rows=self.n)
        with open(folder / "meta.json", "w") as f:
            json.dump(meta, f, indent=2, default=str)
        return folder

    @classmethod
    def load(cls, folder):
        folder = Path(folder)
        with open(folder / "meta.json") as f:
            meta = json.load(f)
        log = cls(meta={k: v for k, v in meta.items() if k not in ("events", "rows")})
        log.events = meta.get("events", [])
        with np.load(folder / "data.npz") as data:
            for name in data.files:
                arr = data[name]
                ch = Channel()
                ch.data = arr.astype(float).copy()
                ch.n = len(arr)
                log.channels[name] = ch
                log.n = len(arr)
        return log
