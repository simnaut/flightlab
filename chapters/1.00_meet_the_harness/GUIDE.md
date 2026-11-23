# 1.00 — Meet the harness

## What's new

Everything! In this Part the airplane sits on a **test stand in a wind
tunnel**. It is pinned at its center of gravity (CG) and can only **pitch**:
rotate nose-up or nose-down. The air blows past it at a constant 55 m/s. The
only control surface that matters is the **elevator**, the hinged flap at the
back of the horizontal tail.

No code to write in this chapter. The goal is to get a feel for the aircraft
before you try to control it.

## Physics you need

The stand removes every motion except pitch, so the whole plant is one
equation: rotational acceleration = pitching moment ÷ moment of inertia.

```math
I_{yy}\,\dot{q} = \bar{q}\,S\,\bar{c}\;C_m, \qquad \dot{\theta} = q
```

| Symbol | Meaning |
|---|---|
| $`\theta`$ | pitch angle: nose above the horizon (rad) |
| $`q`$ | pitch rate (rad/s) |
| $`I_{yy}`$ | moment of inertia about the pitch axis (kg m²) |
| $`\bar{q} = \tfrac{1}{2}\rho V^2`$ | dynamic pressure (Pa) |
| $`S,\ \bar{c}`$ | wing area (m²) and mean chord (m) |
| $`C_m`$ | pitching-moment coefficient (dimensionless) |

The pitching-moment coefficient is built from **stability derivatives**:

```math
C_m = C_{m_0} + C_{m_\alpha}\,\alpha + C_{m_q}\,\frac{q\,\bar{c}}{2V} + C_{m_{\delta_e}}\,\delta_e
```

- $`C_{m_\alpha} < 0`$: **static stability.** If the nose goes up, the angle of
  attack $`\alpha`$ goes up, and the tail pushes the nose back down. Like a
  weathervane.
- $`C_{m_q} < 0`$: **pitch damping.** Rotating makes the tail swing through the
  air, which resists the rotation.
- $`C_{m_{\delta_e}} < 0`$: **elevator power.** Positive elevator (trailing
  edge down) pushes the tail up, which pitches the **nose down**.
- $`C_{m_0}`$: the moment at zero α and zero elevator. Here it's slightly
  nose-up.

On the stand the air is horizontal, so **α = θ**, at least until you tilt the
air (see below).

Find these in `flightlab/models/aero.py` and the numbers in
`aircraft/trainer.yaml`. Read along in Beard & McLain ch. 4 or any flight
dynamics text under "longitudinal static stability".

## Observe

1. **Open loop.** No controller, elevator held at zero:

   ```
   flightlab run 1.00 --open-loop
   ```

   The aircraft starts 10° nose-up. Watch it swing down, overshoot, and settle.
   Where does it settle? (Not at 0°!)

2. **Kick it.** Press **Kick ▲** and **Kick ▼** a few times. How long does the
   wobble last? How many swings before it stops?

3. **Fly it by hand.**

   ```
   flightlab run 1.00 --manual
   ```

   Use the slider or the arrow keys (↓ = pull = nose up, ↑ = push = nose down).
   Try to hold the nose exactly level (θ = 0). Turn on **Elevator ×3** to see
   the elevator move.

4. **Play with the wind tunnel.** Drag the blue arrow or use the sliders:
   - Change the **airspeed**. Does the aircraft swing faster or slower after a
     kick at 25 m/s vs 70 m/s?
   - Tilt the air with the **flow angle** (up-flow is positive). Watch θ and α
     separate: α = θ + flow angle. This is what a gust does to an airplane.

## Your task

Just explore. Then look at `student/ch01_00.py`, the template your
controllers will start from, and run `flightlab new 1.01` when you're ready.

## Questions

Write short answers in `student/notes.md`:

1. With the elevator at zero, the aircraft settled at about +3.7°. Use the
   $`C_m`$ equation to explain why. (Hint: what is $`C_m`$ when it stops moving?)
2. After a kick, the aircraft oscillates and then stops. Which derivative makes
   it come back, and which makes it stop swinging?
3. At higher airspeed, does it swing faster or slower? Why? (Look at
   $`\bar{q}`$.)
4. Holding level by hand: what elevator angle did you end up using?
