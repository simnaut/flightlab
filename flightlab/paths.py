"""Locations of the harness's data folders (relative to the repository root)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AIRCRAFT_DIR = REPO_ROOT / "aircraft"
CHAPTERS_DIR = REPO_ROOT / "chapters"
STUDENT_DIR = REPO_ROOT / "student"
SOLUTIONS_DIR = REPO_ROOT / "solutions"
RUNS_DIR = REPO_ROOT / "runs"
PROGRESS_FILE = REPO_ROOT / "progress.json"
