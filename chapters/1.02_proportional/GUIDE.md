# 1.02 — Proportional control

## What's new

**Feedback.** From now on, the commanded pitch angle changes: hold level,
step to +5° at t = 4 s, then step to −3° at t = 12 s. A constant elevator can't
follow that. Your controller has to **look at the error** and react.

**New in the viewer:** the commanded pitch angle (dashed white in the pitch
plot, and `cmd` in the readout), a **Step** button that advances one
controller update, a **Speed** box to slow time down, and **Kick** buttons
that give the aircraft a short push, so you can see your controller fight
back. Anything you `self.log()` gets its own plot.

## Physics you need

The **error** is how far you are from where you want to be:

```math
e = \theta_{cmd} - \theta
```

A **proportional (P) controller** sets the elevator in proportion to the error:

```math
\delta_e = -K_p\, e
```

**Why the minus sign?** If the nose is too low, $`e > 0`$. You need nose-up,
which is **negative** elevator (trailing edge up). Get this sign wrong and the
controller pushes the nose the wrong way: the aircraft runs away until it hits
the stand's stop. (Try it! Every control engineer has done this.)

**Steady-state error.** Once things settle, a P controller usually doesn't land
exactly on the command. The aircraft settles where the elevator moment balances
the aircraft's own moments, and that elevator needs a nonzero error to
produce it. Setting $`C_m = 0`$ with your control law gives:

```math
|e_{ss}| = \frac{\left|\,C_{m_0} + C_{m_\alpha}\,\theta_{cmd}\,\right|}{|C_{m_\alpha}| + |C_{m_{\delta_e}}|\,K_p}
```

Bigger $`K_p`$ gives smaller error. But watch what else happens when you raise
it.

## Observe first

```
flightlab new 1.02
flightlab run 1.02
```

Your trim controller from 1.01 holds level until t = 4 s, then ignores the steps
completely.

## Your task

Replace the constant elevator with a P controller:

```python
error = observations.ref.theta - observations.sensors.theta
self.log("error_deg", error / DEG)      # plot it!
return Command(elevator=-KP * error)
```

Start with `KP = 0.5` and work upward. Watch the **Pitch angle** plot after
each change.

## Pass criteria

| Check | Need |
|---|---|
| Steady-state error (each hold, last 3 s) | ≤ 1.5° |
| Overshoot | ≤ 50 % |

## Things to try

- $`K_p`$ = 0.5, 1, 2, 4, 8. For each, note the steady-state error and how much
  it overshoots and oscillates after a step. Make a table.
- Flip the sign on purpose and watch it run away.
- Kick it with a high $`K_p`$, then a low one. Compare with the open-loop
  swing in 1.00.
- Run `flightlab replay latest` to watch your last run again, at slow speed
  if you like (use the Speed box).

## Questions

1. Using the formula above, what $`K_p`$ do you need for the steady-state error
   at θ_cmd = −3° to be under 1°? Does the sim agree?
2. As $`K_p`$ grows, the error shrinks, but what gets worse?
3. Why can't a P controller alone ever get the error to exactly zero here?
