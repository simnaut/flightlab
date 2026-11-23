"""Every chapter is passable, and each chapter's new idea is actually needed.

For each graded chapter, the reference solution must pass. The previous
chapter's solution must fail, which proves the chapter teaches something new.
"""

import pytest

from flightlab.grade import grade
from flightlab.paths import SOLUTIONS_DIR
from flightlab.scenario.chapter import all_chapters, load_chapter, student_filename

GRADED = [c.id for c in all_chapters() if c.graded]

# Solutions are kept out of the public repo; skip these checks where they're absent.
needs_solutions = pytest.mark.skipif(
    not any(SOLUTIONS_DIR.glob("ch*.py")),
    reason="reference solutions not present (solutions/ is not published)")


def _grade(chapter_id, solution_id):
    return grade(load_chapter(chapter_id), SOLUTIONS_DIR / student_filename(solution_id),
                 save_runs=False, echo=lambda *a: None, record_progress=False)


def test_every_chapter_loads():
    for ch in all_chapters():
        assert ch.guide_path.exists(), f"{ch.id} has no GUIDE.md"


@needs_solutions
@pytest.mark.parametrize("chapter_id", GRADED)
def test_reference_solution_passes(chapter_id):
    result = _grade(chapter_id, chapter_id)
    assert not result.errors
    assert result.passed, [(c.label, c.value) for c in result.checks]


@needs_solutions
@pytest.mark.parametrize("chapter_id", GRADED[1:])
def test_previous_solution_is_not_enough(chapter_id):
    previous = GRADED[GRADED.index(chapter_id) - 1]
    result = _grade(chapter_id, previous)
    assert not result.passed
