"""Headless grading: run a chapter's scenarios and check the pass criteria."""

import copy
import json
import time
from dataclasses import dataclass, field

import numpy as np

from flightlab.analysis.metrics import METRICS
from flightlab.loader import load_controller
from flightlab.paths import PROGRESS_FILE, RUNS_DIR
from flightlab.scenario.chapter import Chapter
from flightlab.sim.simulation import ControllerError, Simulation, SimulationError


@dataclass
class CheckResult:
    label: str
    metric: str
    units: str
    limit: float
    kind: str          # "max" or "min"
    value: float
    worst_run: str

    @property
    def passed(self):
        if self.value != self.value:      # NaN
            return False
        return self.value <= self.limit if self.kind == "max" else self.value >= self.limit


@dataclass
class GradeResult:
    chapter: str
    checks: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    run_folder: object = None

    @property
    def passed(self):
        return not self.errors and bool(self.checks) and all(c.passed for c in self.checks)


def _scenario_chapter(chapter, scenario):
    """A copy of the chapter with the scenario's overrides applied."""
    cfg = copy.deepcopy(chapter.config)
    for key in ("reference", "tunnel", "duration_s", "initial"):
        if key in scenario:
            if isinstance(scenario[key], dict) and isinstance(cfg.get(key), dict):
                cfg[key] = {**cfg[key], **scenario[key]}
            else:
                cfg[key] = scenario[key]
    return Chapter(id=chapter.id, title=chapter.title, folder=chapter.folder, config=cfg)


def _randomized_initial(scenario, seed):
    rng = np.random.default_rng(seed)
    initial = {}
    for key, (lo, hi) in (scenario.get("randomize") or {}).items():
        name = key[len("initial_"):] if key.startswith("initial_") else key
        initial[name] = float(rng.uniform(lo, hi))
    return initial


def grade(chapter, controller_path, save_runs=True, echo=print, record_progress=True):
    grading = chapter.config.get("grading")
    result = GradeResult(chapter=chapter.id)
    if not grading:
        echo(f"Chapter {chapter.id} has no graded checks. Run it with `flightlab run {chapter.id}`.")
        return result

    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = RUNS_DIR / f"{stamp}_{chapter.id}_grade"
    result.run_folder = folder if save_runs else None

    runs = []      # (label, sim_chapter, log)
    for scenario in grading["scenarios"]:
        sc_chapter = _scenario_chapter(chapter, scenario)
        for seed in range(1, int(scenario.get("seeds", 1)) + 1):
            label = f"{scenario['name']} (seed {seed})"
            try:
                controller = load_controller(controller_path)
                sim = Simulation(sc_chapter, controller, seed=seed,
                                 initial=_randomized_initial(scenario, seed),
                                 controller_path=controller_path)
                log = sim.run()
            except (ControllerError, SimulationError) as exc:
                result.errors.append(f"{label}: {exc}")
                continue
            except Exception as exc:  # loader errors etc.
                result.errors.append(f"{label}: {exc}")
                break
            if save_runs:
                slug = scenario["name"].lower().replace(" ", "_")
                log.save(folder / f"{slug}_seed{seed}")
            runs.append((label, sim, log))

    for check in grading["checks"]:
        fn, default_label, units = METRICS[check["metric"]]
        kind = "max" if "max" in check else "min"
        limit = float(check[kind])
        signal = check.get("signal", "theta")
        params = {k: v for k, v in check.items()
                  if k not in ("metric", "max", "min", "signal", "label")}
        worst_value, worst_run = None, ""
        for label, sim, log in runs:
            value = fn(log, signal, sim.references.get(signal), **params)
            worse = (worst_value is None or
                     (value > worst_value if kind == "max" else value < worst_value))
            if worse:
                worst_value, worst_run = value, label
        result.checks.append(CheckResult(
            label=check.get("label", default_label), metric=check["metric"], units=units,
            limit=limit, kind=kind,
            value=float("nan") if worst_value is None else worst_value, worst_run=worst_run))

    _print_report(chapter, result, len(runs), echo)
    if record_progress:
        _save_progress(chapter.id, result.passed)
    return result


def _print_report(chapter, result, n_runs, echo):
    echo(f"\nChapter {chapter.id}: {chapter.title}")
    echo(f"Ran {n_runs} scenario run(s).\n")
    for err in result.errors:
        echo("  ERROR " + err.replace("\n", "\n        "))
    if result.errors:
        echo("")
    for c in result.checks:
        mark = "PASS" if c.passed else "FAIL"
        op = "<=" if c.kind == "max" else ">="
        echo(f"  [{mark}] {c.label:<26} {c.value:8.2f} {c.units:<5} (need {op} {c.limit:g} {c.units})"
             + (f"   worst: {c.worst_run}" if not c.passed and c.worst_run else ""))
    echo("")
    if result.passed:
        echo(f"Chapter {chapter.id} passed!")
    else:
        echo(f"Chapter {chapter.id} not passed yet.")
    if result.run_folder:
        echo(f"Run logs: {result.run_folder}  (replay with `flightlab replay <folder>`)")


def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_progress(chapter_id, passed):
    progress = load_progress()
    entry = progress.get(chapter_id, {})
    entry["passed"] = entry.get("passed", False) or passed
    entry["last_result"] = "pass" if passed else "fail"
    entry["last_graded"] = time.strftime("%Y-%m-%d %H:%M:%S")
    progress[chapter_id] = entry
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2, sort_keys=True)
