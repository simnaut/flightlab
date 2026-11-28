// Rolling time-history plots, drawn with uPlot. Preact mounts the container
// once; after that this class owns it and redraws from the Store each frame.

import uPlot from "uplot";
import { COLORS, DEG, STUDENT_COLORS } from "./theme.js";

export const WINDOW_S = 20;
const R2D = 1 / DEG;

/**
 * The plots to show, given the chapter's unlocked viewer features (a Set).
 * Returns [[title, [[channel, label, color, dashed, scale], ...]], ...].
 */
export function plotSpecs(features) {
  const has = (f) => features.has(f);
  // Later series draw on top. θ goes last: with level tunnel air α equals θ,
  // and α should only show once the air is tilted and the two separate.
  const pitch = [];
  if (has("theta_cmd")) pitch.push(["ref_theta", "θ cmd", COLORS.command, true, R2D]);
  if (has("tunnel")) pitch.push(["alpha", "α", COLORS.alpha, false, R2D]);
  pitch.push(["theta", "θ", COLORS.theta, false, R2D]);
  const elevator = has("elevator_cmd")
    ? [["de_cmd", "δe cmd", COLORS.command, true, R2D], ["de", "δe actual", COLORS.elevator, false, R2D]]
    : [["de", "δe", COLORS.elevator, false, R2D]];
  const specs = [[has("tunnel") ? "Pitch angle & angle of attack (deg)" : "Pitch angle (deg)", pitch]];
  if (has("pitch_rate")) specs.push(["Pitch rate (deg/s)", [["q", "q", COLORS.q, false, R2D]]]);
  specs.push(["Elevator (deg)", elevator]);
  if (has("tunnel")) {
    specs.push(["Wind tunnel air", [["tunnel_airspeed", "airspeed (m/s)", COLORS.arrow, false, 1],
                                    ["tunnel_flow", "flow angle (deg)", COLORS.flow, false, R2D]]]);
  }
  return specs;
}
const STUDENT_TITLE = "Your signals (self.log)";
const AXIS = { stroke: "#c8ccd0", grid: { stroke: "rgba(255,255,255,0.08)", width: 1 },
  ticks: { stroke: "rgba(255,255,255,0.15)", width: 1 }, font: "11px system-ui, sans-serif" };

// Auto-fit the y axis, but never tighter than +-0.5 around a flat line
// (uPlot's default turns an all-zero trace into a 0..100 axis).
function yRange(u, min, max) {
  if (min === null || max === null) return [-1, 1];
  if (max - min < 1) {
    const mid = (min + max) / 2;
    return [mid - 1, mid + 1];
  }
  return uPlot.rangeNum(min, max, 0.1, true);
}

function makeOpts(title, traces, width, height) {
  return {
    title, width, height,
    legend: { live: false },
    cursor: { drag: { x: false, y: false }, points: { show: false } },
    scales: { x: { time: false, auto: false }, y: { range: yRange } },
    axes: [{ ...AXIS, size: 28 }, { ...AXIS, size: 46, space: 18 }],
    series: [{ label: "t (s)" }, ...traces.map(([, label, color, dashed]) => ({
      label, stroke: color, width: dashed ? 1.5 : 2, dash: dashed ? [6, 4] : undefined,
      spanGaps: false, points: { show: false },
    }))],
  };
}

export class Plots {
  constructor(container, specs) {
    this.container = container;
    this.specs = specs;            // from plotSpecs()
    this.plots = [];               // [{u, traces}]
    this.student = [];             // selected student signal names
    this.size = [600, 120];
    this._build();
    this.ro = new ResizeObserver(() => this._resize());
    this.ro.observe(container);
  }

  _studentTraces() {
    return this.student.map((name, i) =>
      [`log.${name}`, name, STUDENT_COLORS[i % STUDENT_COLORS.length], false, 1]);
  }

  _build() {
    for (const p of this.plots) p.u.destroy();
    this.container.replaceChildren();
    this.plots = [];
    // The student plot appears once they log (and select) something
    const all = this.student.length ? [...this.specs, [STUDENT_TITLE, this._studentTraces()]] : this.specs;
    for (const [title, traces] of all) {
      const div = document.createElement("div");
      div.className = "plot";
      this.container.appendChild(div);
      const u = new uPlot(makeOpts(title, traces, ...this.size), [[], ...traces.map(() => [])], div);
      this.plots.push({ u, traces });
    }
    this._resize();
  }

  _resize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (!w || !h) return;
    // Each plot also has a title and a legend row (~44 px) outside its canvas.
    // Capped, so a chapter with only two plots doesn't get stretched ones.
    const ph = Math.min(220, Math.max(60, Math.floor(h / this.plots.length) - 44));
    this.size = [w, ph];
    for (const { u } of this.plots) u.setSize({ width: w, height: ph });
  }

  setStudentSignals(names) {
    const same = names.length === this.student.length && names.every((n, i) => n === this.student[i]);
    if (same) return;
    this.student = [...names];
    this._build();
  }

  /** Redraw from the store; tNow is the current sim time. */
  update(store, tNow) {
    const x0 = Math.max(0, tNow - WINDOW_S), x1 = Math.max(WINDOW_S, tNow);
    const start = store.indexAt(x0 - 0.05);
    const times = store.col("t") ? store.col("t").slice(start, store.n) : [];
    for (const { u, traces } of this.plots) {
      const data = [times];
      for (const [channel, , , , scale] of traces) {
        const col = store.col(channel);
        if (!col) {
          data.push(times.map(() => null));
          continue;
        }
        const out = new Array(times.length);
        for (let i = 0; i < times.length; i++) {
          const v = col[start + i];
          out[i] = v === null ? null : v * scale;
        }
        data.push(out);
      }
      u.batch(() => {
        u.setData(data);                          // re-fits the y axis

        u.setScale("x", { min: x0, max: x1 });
      });
    }
  }
}
