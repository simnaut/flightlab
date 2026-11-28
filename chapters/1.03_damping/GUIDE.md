# 1.03 — Damping

## What's new

The same pitch steps as 1.02, but now the grader also checks **overshoot** and
**settling time**. High-gain P control rings like a bell, and you'll add
**damping** to calm it down.

**New in the viewer:** a **pitch rate** plot (q, in deg/s) and `q` in the
readout.

## Physics you need

Put your P controller into the stand's equation of motion. Ignoring the
constant terms, it becomes a mass-spring-damper:

```math
I_{yy}\,\ddot{\theta} + \underbrace{c}_{\text{damping}}\,\dot{\theta} + \underbrace{k}_{\text{stiffness}}\,\theta = \ldots
```

```math
k = \bar{q}S\bar{c}\,\left(|C_{m_\alpha}| + |C_{m_{\delta_e}}|\,K_p\right), \qquad
c = \bar{q}S\bar{c}\,|C_{m_q}|\,\frac{\bar{c}}{2V}
```

The natural frequency and damping ratio are:

```math
\omega_n = \sqrt{k / I_{yy}}, \qquad \zeta = \frac{c}{2\sqrt{k\,I_{yy}}}
```

Raising $`K_p`$ raises the stiffness $`k`$, but the damping $`c`$ stays the
same. So $`\zeta`$ **drops**: more overshoot, more ringing. That's what you saw in
1.02.

The fix is to add damping **with the elevator**: push against the pitch
**rate**. That's **derivative (D) action**:

```math
\delta_e = -K_p\, e + K_d\, q
```

Why $`+K_d\,q`$? If the nose is rising ($`q > 0`$), you want nose-down, which is
positive elevator. You measure $`q`$ directly with a rate gyro
(`observations.sensors.q`), so there's no need to differentiate the error.

With D action, the damping becomes:

```math
c = \bar{q}S\bar{c}\left(|C_{m_q}|\,\frac{\bar{c}}{2V} + |C_{m_{\delta_e}}|\,K_d\right)
```

A damping ratio around $`\zeta \approx 0.7`$ gives a quick response with only
about 5 % overshoot.

## Observe first

```
flightlab new 1.03
flightlab grade 1.03
```

Your 1.02 controller probably passes the steady-state check but fails
overshoot and settling.

## Your task

Add the $`K_d\,q`$ term. Keep your $`K_p`$ from 1.02 (or raise it: now you can
afford more stiffness), and tune $`K_d`$ until the steps are crisp.

Try calculating $`K_d`$ for $`\zeta = 0.7`$ from the equations above, using the
values in `aircraft/trainer.yaml` ($`V`$ = 55 m/s, $`\rho`$ = 1.225 kg/m³). Then
check it in the sim.

## Pass criteria

| Check | Need |
|---|---|
| Steady-state error | ≤ 1.5° |
| Overshoot | ≤ 10 % |
| Settling time (within 5 % of the step) | ≤ 1.0 s |

## Things to try

- Way too much $`K_d`$: what does an **overdamped** response look like?
- Kick it with and without D. Compare how fast it stops.
- Plot the two parts separately: `self.log("p_term", ...)`,
  `self.log("d_term", ...)`. Which one does the work right after a step?

## Questions

1. What $`K_d`$ did you calculate for $`\zeta = 0.7`$? What did you end up using?
2. Did adding D change the steady-state error? Why or why not?
3. Real autopilots almost always use a rate gyro for damping instead of
   differentiating the error. Can you think of why? (Hint: what happens to
   $`de/dt`$ at the instant of a step command?)
