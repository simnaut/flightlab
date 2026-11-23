import pytest

from flightlab.scenario.reference import Schedule


def test_steps_and_ramps():
    s = Schedule([[0, 0], [3, 0], [3, 5], [10, 5], [15, -5]])
    assert s(0) == 0
    assert s(2.999) == 0
    assert s(3) == 5
    assert s(12.5) == pytest.approx(0)
    assert s(15) == -5
    assert s(100) == -5


def test_flat_windows_detect_steps():
    s = Schedule([[0, 0], [4, 0], [4, 5], [12, 5], [12, -3]])
    windows = s.flat_windows(20)
    assert windows == [(0, 4, 0, None), (4, 12, 5, 5), (12, 20, -3, -8)]


def test_flat_window_after_ramp_has_no_step():
    s = Schedule([[0, 0], [5, 10], [8, 10]])
    assert s.flat_windows(10) == [(5, 8, 10, None), (8, 10, 10, None)]


def test_decreasing_times_rejected():
    with pytest.raises(ValueError):
        Schedule([[0, 0], [5, 1], [4, 2]])
