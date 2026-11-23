# FlightLab

Learn flight control one chapter at a time. You write a controller in Python;
FlightLab supplies the airplane, the physics, a live visualization, and a
grader.

The journey starts with an airplane pinned on a wind-tunnel stand that can only
pitch. It ends (in later milestones) with a full 6DOF aircraft flying from one
airport to another. See [HARNESS_DESIGN.md](HARNESS_DESIGN.md) for the whole
plan.

**Available now:** Part I, chapters 1.00–1.05 (trim → P → PD → PID → tuning).

## Setup

Requires Python 3.11+.

With [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra dev
uv run flightlab list
```

Or with plain pip:

```sh
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
flightlab list
```

(On WSL, the viewer window needs WSLg, which is included in Windows 11.)

## How it works

Each chapter adds **one** new idea. For each chapter:

```sh
flightlab guide 1.01        # read what's new and what to do
flightlab new 1.01          # creates student/ch01_01.py from your previous chapter
flightlab run 1.01          # watch your controller live
flightlab grade 1.01        # check the pass criteria
```

The guides are easier to read on GitHub, where the equations render:
[`chapters/`](chapters/).

Your controller is one class with one method:

```python
from flightlab import DEG, Command, ControllerBase

class Controller(ControllerBase):
    def update(self, observations, dt):
        error = observations.ref.theta - observations.sensors.theta
        self.log("error_deg", error / DEG)       # shows up in the live plots
        return Command(elevator=-2.0 * error)
```

## Other commands

```sh
flightlab run 1.00 --open-loop     # no controller: see the bare airplane
flightlab run 1.00 --manual        # fly it yourself (slider or ↑/↓ keys)
flightlab replay latest            # replay your most recent run
flightlab list                     # chapters and your progress
```

In the viewer you can **kick** the airplane, change the **wind tunnel** air
(drag the blue arrow, or use the sliders), slow down time, and single-step your
controller.

## For instructors

- `solutions/` has reference controllers for each chapter. The test suite
  checks that each one passes its chapter and that the previous chapter's
  solution does *not*, so every chapter needs its new idea.
- Run the tests with `pytest`.
- Chapter setup and pass thresholds live in `chapters/<id>/chapter.yaml`.
- Aircraft parameters live in `aircraft/trainer.yaml`.
