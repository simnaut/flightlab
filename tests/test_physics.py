"""Physics sanity checks: the plant matches hand calculations."""

import math

import numpy as np
import pytest

from flightlab.core.dynamics import Environment, f
from flightlab.core.integrator import rk4_step
from flightlab.core.rigs import make_rig
from flightlab.core.state import (IDX, N_COMMANDS, euler_to_quat, initial_state,
                                  quat_to_dcm, quat_to_euler)
from flightlab.models.aircraft import load_aircraft
from flightlab.models.atmosphere import G

DEG = math.pi / 180
V = 55.0
RHO = 1.225


@pytest.fixture(scope="module")
def ac():
    return load_aircraft("trainer")


def simulate_stand(ac, theta0, seconds, de=0.0, flow=0.0):
    rig = make_rig("pitch_gimbal")
    env = Environment(air_velocity_ned=np.array([V * math.cos(flow), 0, V * math.sin(flow)]),
                      rho=RHO)
    x = initial_state(ac, theta=theta0)
    x[IDX.de] = de
    u = np.zeros(N_COMMANDS)
    dt = 1 / 400
    thetas = []
    for _ in range(int(seconds / dt)):
        x = rk4_step(lambda s: rig.derivative(s, u, ac, env), x, dt)
        x[IDX.quat] /= np.linalg.norm(x[IDX.quat])
        thetas.append(quat_to_euler(x[IDX.quat])[1])
    return x, np.array(thetas), dt


def test_euler_quaternion_round_trip():
    for angles in [(0.1, -0.2, 0.3), (-1.0, 0.5, 2.5), (0.0, 1.2, -3.0)]:
        back = quat_to_euler(euler_to_quat(*angles))
        assert np.allclose(back, angles, atol=1e-9)


def test_dcm_is_rotation():
    R = quat_to_dcm(euler_to_quat(0.3, -0.4, 1.1))
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
    assert np.isclose(np.linalg.det(R), 1.0)


def test_stand_trims_where_moment_is_zero(ac):
    # Cm0 + Cm_alpha*alpha + Cm_de*de = 0  ->  alpha = -(Cm0 + Cm_de*de)/Cm_alpha
    a = ac.aero
    for de in (0.0, 2 * DEG, -3 * DEG):
        _, thetas, _ = simulate_stand(ac, 5 * DEG, 10.0, de=de)
        expected = -(a.Cm0 + a.Cm_de * de) / a.Cm_alpha
        assert thetas[-1] == pytest.approx(expected, abs=1e-4)


def test_upflow_shifts_trim_pitch(ac):
    # On the stand alpha = theta + flow, so up-flow lowers the trim pitch angle
    a = ac.aero
    flow = 5 * DEG
    _, thetas, _ = simulate_stand(ac, 0.0, 10.0, flow=flow)
    assert thetas[-1] == pytest.approx(-a.Cm0 / a.Cm_alpha - flow, abs=1e-4)


def test_stand_short_period_matches_hand_calculation(ac):
    a, g = ac.aero, ac.geometry
    qS_c = 0.5 * RHO * V ** 2 * g.S * g.c
    k = -qS_c * a.Cm_alpha                        # N m / rad
    c = -qS_c * a.Cm_q * g.c / (2 * V)            # N m s / rad
    wn = math.sqrt(k / ac.mass.Iyy)
    zeta = c / (2 * ac.mass.Iyy * wn)
    wd = wn * math.sqrt(1 - zeta ** 2)

    _, thetas, dt = simulate_stand(ac, 10 * DEG, 8.0)
    d = thetas - thetas[-1]
    crossings = np.nonzero(np.diff(np.sign(d)))[0]
    half_period = (crossings[1] - crossings[0]) * dt
    assert half_period == pytest.approx(math.pi / wd, rel=0.01)


def test_stand_locks_everything_but_pitch(ac):
    x, _, _ = simulate_stand(ac, 5 * DEG, 2.0)
    phi, _, psi = quat_to_euler(x[IDX.quat])
    assert phi == pytest.approx(0, abs=1e-12)
    assert psi == pytest.approx(0, abs=1e-12)
    assert np.allclose(x[IDX.pos], 0) and np.allclose(x[IDX.vel], 0)
    assert x[IDX.p] == 0 and x[IDX.r] == 0


def test_stand_end_stops_hold(ac):
    # A huge nose-up elevator drives the aircraft into the stop, which holds within a few degrees of 35
    _, thetas, _ = simulate_stand(ac, 0.0, 5.0, de=-40 * DEG)
    assert thetas.max() < 38 * DEG


def test_dynamics_is_pure(ac):
    x = initial_state(ac, theta=0.1, airspeed=50.0)
    x_copy = x.copy()
    u = np.array([0.01, 0.0, 0.0, 0.5, 0.0])
    env = Environment()
    a, b = f(x, u, ac, env), f(x, u, ac, env)
    assert np.array_equal(a, b)
    assert np.array_equal(x, x_copy)


def test_free_fall_without_air(ac):
    # Zero airspeed and no thrust: only gravity acts
    x = initial_state(ac, fuel_kg=0.0)
    xdot = f(x, np.zeros(N_COMMANDS), ac, Environment())
    assert xdot[IDX.w] == pytest.approx(G)
    assert xdot[IDX.u] == pytest.approx(0.0)


def test_cg_forward_increases_stability(ac):
    """Moving the CG ahead of the aero reference point makes Cm_alpha more negative."""
    import copy
    fwd = copy.deepcopy(ac)
    fwd.mass.cg_dry_x = 0.1
    fwd.fuel.tank_x = 0.1

    def pitch_moment_slope(aircraft):
        env = Environment(air_velocity_ned=np.array([V, 0, 0]), rho=RHO)
        moments = []
        for theta in (0.0, 1 * DEG):
            x = initial_state(aircraft, theta=theta)
            xdot = f(x, np.zeros(N_COMMANDS), aircraft, env)
            moments.append(xdot[IDX.q])
        return moments[1] - moments[0]

    assert pitch_moment_slope(fwd) < pitch_moment_slope(ac) < 0
