# 1.01 — Trim

## What's new

You write your first controller. It's the simplest possible one: a
**constant** elevator angle. Finding the control setting that holds the
aircraft steady is called **trimming**, and every aircraft and every control
system starts from a trim point.

## Physics you need

The aircraft stops rotating when the pitching moment is zero:

```math
C_m = C_{m_0} + C_{m_\alpha}\,\alpha + C_{m_{\delta_e}}\,\delta_e = 0
```

(The $`C_{m_q}`$ term is zero once $`q = 0`$.) You want θ = 0, and on the stand
α = θ. So there's exactly one elevator angle that makes the moment zero at
θ = 0. That's the **trim elevator**.

## Observe first

```
flightlab new 1.01
flightlab run 1.01
```

Your new file `student/ch01_01.py` returns zero elevator. The aircraft settles
at about +3.7°, not level.

## Your task

Make `update` return a constant elevator that holds θ = 0. Find the value two
ways:

1. **By experiment:** `flightlab run 1.01 --manual`, and adjust the slider until
   the nose stays level.
2. **By calculation:** solve the $`C_m`$ equation above for $`\delta_e`$, using
   the numbers in `aircraft/trainer.yaml`.

Do they agree? Then put it in your controller:

```python
return Command(elevator=2.0 * DEG)   # your value here
```

Check your result:

```
flightlab grade 1.01
```

## Pass criteria

| Check | Need |
|---|---|
| Pitch error, averaged over the last 5 s | ≤ 0.5° |

The grader starts the aircraft at three different random pitch angles between
−5° and +5°.

## Things to try

- Change the airspeed with the wind tunnel slider while your trim controller
  runs. Does the aircraft stay level? (Look at the $`C_m`$ equation: does
  airspeed appear in it?)
- Tilt the air with the flow angle slider. Now what happens, and why?
- Kick it. Does your controller help it recover? (It can't: it doesn't even
  look at the observations. That's next chapter.)

## Questions

1. What trim elevator did you calculate? What did you find by hand?
2. Is the trim elevator positive or negative? Which way does the elevator
   trailing edge point?
3. Your controller is **open loop**: it never checks what the aircraft is doing.
   What could go wrong with an open-loop controller on a real airplane?
