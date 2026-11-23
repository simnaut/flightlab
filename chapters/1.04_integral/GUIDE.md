# 1.04 — Integral action

## What's new

The steady-state error check gets strict: **0.2°**. Your PD controller can't
get there without enormous gain. You'll add an **integral (I) term** that
removes the error entirely.

## Physics you need

The **integral** of the error adds up how much error there has been, and for
how long:

```math
I(t) = \int_0^t e\,dt \quad\approx\quad I_{k} = I_{k-1} + e_k\,\Delta t
```

The full PID law:

```math
\delta_e = -\left(K_p\,e + K_i \int e\,dt\right) + K_d\,q
```

**Why it works:** suppose the aircraft settles with a small error. The integral
keeps growing, which keeps moving the elevator. So the aircraft *can't* stay
settled until the error is exactly zero. The integrator automatically finds the
trim elevator you calculated by hand in 1.01, at every pitch angle.

**Memory.** This is the first controller that needs to remember something
between calls. Store the integral on `self`, and reset it in `reset()` so each
run starts fresh:

```python
def reset(self, info):
    self.integral = 0.0

def update(self, observations, dt):
    error = ...
    self.integral += error * dt
```

## Observe first

```
flightlab new 1.04
flightlab grade 1.04
```

Your 1.03 controller fails the steady-state check.

## Your task

Add the integral term. Start with a small $`K_i`$ (about 1) and increase it.
Log the integral with `self.log("integral", self.integral)` and watch it
settle to a constant. Once the error and $`q`$ are zero, the elevator is just
$`-K_i \times`$ that constant: the integrator has found the trim elevator!

## Pass criteria

| Check | Need |
|---|---|
| Steady-state error | ≤ 0.2° |
| Overshoot | ≤ 10 % |
| Settling time | ≤ 1.0 s |

## Things to try

- Very large $`K_i`$: what happens to overshoot?
- Kick the aircraft and watch the integral. Does it change?
- Change the airspeed mid-run with the wind tunnel slider. The trim elevator
  doesn't depend on airspeed here, but does the response look the same at
  30 m/s and 70 m/s? (Keep this in mind for chapter 1.14.)
- Tilt the air with a flow angle step. With P or PD, a flow angle change left
  a lasting pitch error. With PID?

## Questions

1. After the step to +5°, what value did your integral settle to? Multiply by
   $`-K_i`$ and compare with the trim elevator from 1.01's equation at
   θ = +5°.
2. Why does integral action make overshoot worse as $`K_i`$ grows?
3. What do you think happens to the integral if the elevator can't move far
   enough to fix the error? (You'll find out in chapter 1.06.)
