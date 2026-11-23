"""Fixed-step Runge-Kutta 4 integrator."""


def rk4_step(fun, x, dt):
    """Advance x by one step of size dt, where fun(x) returns xdot."""
    k1 = fun(x)
    k2 = fun(x + 0.5 * dt * k1)
    k3 = fun(x + 0.5 * dt * k2)
    k4 = fun(x + dt * k3)
    return x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
