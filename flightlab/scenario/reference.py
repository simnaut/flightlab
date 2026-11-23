"""Reference (command) schedules.

A schedule is a list of ``[time, value]`` points, interpolated linearly.
Repeating a time makes a step:

    [[0, 0], [3, 0], [3, 5], [10, 5], [15, -5]]
      hold 0 until t=3, step to 5, hold until t=10, ramp to -5 by t=15

The value is held after the last point.
"""

import bisect


class Schedule:
    def __init__(self, points, scale=1.0):
        if not points:
            points = [[0.0, 0.0]]
        self.points = [(float(t), float(v) * scale) for t, v in points]
        for (t0, _), (t1, _) in zip(self.points, self.points[1:]):
            if t1 < t0:
                raise ValueError(f"Schedule times must not decrease: {points}")
        self.times = [p[0] for p in self.points]

    def __call__(self, t):
        pts = self.points
        if t <= pts[0][0]:
            return pts[0][1]
        # Last point with time <= t (for a step, the one after the jump)
        i = bisect.bisect_right(self.times, t) - 1
        if i >= len(pts) - 1:
            return pts[-1][1]
        (t0, v0), (t1, v1) = pts[i], pts[i + 1]
        if t1 == t0:
            return v1
        return v0 + (v1 - v0) * (t - t0) / (t1 - t0)

    def flat_windows(self, t_end):
        """Intervals where the command is constant.

        Returns a list of (t_start, t_end, value, step) where ``step`` is the
        size of the jump that started the window (None for the first window or
        a window that starts at the end of a ramp).
        """
        pts = [p for p in self.points if p[0] < t_end] or [self.points[0]]
        if pts[0][0] > 0.0:
            pts = [(0.0, pts[0][1])] + pts
        # Hold the last value until the end of the run
        pts = pts + [(t_end, pts[-1][1])]
        windows = []
        for i in range(len(pts) - 1):
            (t0, v0), (t1, v1) = pts[i], pts[i + 1]
            if t1 <= t0 or v1 != v0:
                continue
            step = None
            if i > 0 and pts[i - 1][0] == t0 and pts[i - 1][1] != v0:
                step = v0 - pts[i - 1][1]
            windows.append((t0, t1, v0, step))
        return windows
