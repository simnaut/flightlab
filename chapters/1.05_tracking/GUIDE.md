# 1.05 — Step and ramp tracking

## What's new

A longer **test card**, like a real flight test: steps, a slow pitch-up ramp,
a hold, a pitch-down ramp, and a fast doublet (quick up-down-up steps). And a
new rule: an **elevator budget**. Real aircraft can only move the elevator so
far, so you must stay within **15°**.

This chapter is about **tuning**: trading tracking accuracy against how hard
the controller works.

## Physics you need

Nothing new. This is about engineering judgement:

- A step command is instant. A P term reacts with an instant elevator jump of
  $`K_p \times \text{step}`$. A 7° doublet with $`K_p = 3`$ asks for 21° of
  elevator, which is over budget.
- During a **ramp**, the command keeps moving. The controller needs a small
  error to keep the elevator moving with it. More gain means less lag, but more
  gain means bigger elevator jumps on steps.
- The grader measures **RMS error**, a sort of average size of the error over
  the whole card:

```math
e_{RMS} = \sqrt{\frac{1}{T}\int_0^T e^2\,dt}
```

## Observe first

```
flightlab new 1.05
flightlab run 1.05
flightlab grade 1.05
```

Your 1.04 controller probably tracks well but blows the elevator budget on the
doublet. Look at the **Elevator** plot.

## Your task

Retune $`K_p`$, $`K_i`$ and $`K_d`$ to pass all three checks. Keep a table of what you
tried: gains → RMS error, overshoot, max elevator. Plotting the trade-off is
part of the exercise.

Ideas beyond retuning, if you want to go further:

- **Feedforward:** you know the trim elevator for any θ_cmd from 1.01's
  equation. Add it directly to the command, so the PID only has to fix what's
  left.
- **Setpoint weighting:** apply $`K_p`$ to only part of the command
  (e.g., $`K_p\,(b\,\theta_{cmd} - \theta)`$ with $`b < 1`$), so steps cause a
  smaller elevator kick.

## Pass criteria

| Check | Need |
|---|---|
| RMS tracking error | ≤ 0.8° |
| Overshoot | ≤ 10 % |
| Max elevator used | ≤ 15° |

## Things to try

- Plot your error during the ramps. Is it constant? Why?
- Turn the controller rate down in your head: if `update` were called only 10
  times a second, which of your terms would suffer most? (Chapter 1.09 will
  find out for real.)

## Questions

1. Which of the three checks was hardest to satisfy, and what did you trade to
   get it?
2. During the ramp up, is the aircraft ahead of or behind the command? By about
   how much?
3. If you used feedforward or setpoint weighting, how much did it help?

**This is the end of milestone 1.** Next up (chapter 1.06): what happens when
the elevator physically can't go past its limit.
