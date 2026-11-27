// Side view of the aircraft on the pitch stand, with the wind tunnel air.
//
// World coordinates: meters, x forward (right), y up, origin at the CG (the
// stand's pivot). The drawing lives in a <g> flipped with scale(1,-1), so a
// positive rotate() there is counterclockwise on screen: nose up for θ, and
// trailing edge down for the elevator. Text is drawn outside the flipped group.

import { COLORS, DEG } from "./theme.js";

const NS = "http://www.w3.org/2000/svg";
const ARROW_M_PER_MPS = 0.06;       // control-arrow length per m/s of airspeed
const PARTICLE_SPEED_SCALE = 0.12;  // wind particles move at this fraction of real airspeed
const ANCHOR = [4.4, 0.0];          // the air arrow's head

// Aircraft outline (side view of a high-wing trainer)
const FUSELAGE = [[2.7, 0.0], [2.55, 0.35], [1.6, 0.55], [0.95, 1.0], [-0.7, 1.0], [-1.3, 0.62],
  [-4.6, 0.38], [-4.95, 0.34], [-4.95, 0.06], [-4.5, -0.04], [-1.0, -0.45], [1.6, -0.5], [2.5, -0.3]];
const WINDOW = [[1.5, 0.55], [0.95, 0.95], [0.25, 0.95], [0.25, 0.55]];
const WING = [[0.75, 1.05], [0.55, 1.17], [0.0, 1.2], [-0.8, 1.1], [-0.8, 1.06], [0.0, 1.03]];
const VTAIL = [[-3.5, 0.45], [-4.3, 1.65], [-4.95, 1.65], [-4.95, 0.34]];
const HSTAB = [[-3.9, 0.3], [-4.0, 0.36], [-4.5, 0.34], [-4.5, 0.26], [-4.0, 0.25]];
const HINGE = [-4.5, 0.30];
const ELEVATOR = [[0.0, 0.05], [-0.55, 0.0], [0.0, -0.05]];   // relative to the hinge
const STRUT = [[-0.2, -0.45], [-0.55, -1.15]];
const NOSE_STRUT = [[2.0, -0.45], [2.0, -1.05]];
const PROP = [[2.78, -0.95], [2.78, 0.95]];

function el(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

const pts = (list) => list.map(([x, y]) => `${x},${y}`).join(" ");
const fmt = (v, digits = 1) => (v >= 0 ? "+" : "") + v.toFixed(digits);

function arcPoints(r, a0, a1, n = 40) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = a0 + ((a1 - a0) * i) / (n - 1);
    out.push(`${(r * Math.cos(a)).toFixed(4)},${(r * Math.sin(a)).toFixed(4)}`);
  }
  return out.join(" ");
}

// Small deterministic random numbers, so the particle pattern is the same each run.
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

export class SideView {
  /**
   * @param container element to draw into
   * @param opts.onAirDragged(airspeed, flowRad) called when the student releases the arrow
   * @param opts.airspeedRange [lo, hi] m/s
   * @param opts.flowRange max |flow angle| (rad)
   */
  constructor(container, opts) {
    this.opts = opts;
    this.interactive = true;
    this.exaggerate = 1;
    this.target = [55, 0];
    this.dragging = false;

    const svg = el("svg", { class: "side-view", viewBox: "-6.5 -4.2 15.5 9.6",
      preserveAspectRatio: "xMidYMid meet" }, container);
    this.svg = svg;
    el("rect", { x: -60, y: -40, width: 120, height: 80, fill: COLORS.bg }, svg);
    const world = el("g", { transform: "scale(1,-1)" }, svg);
    this.world = world;
    const thin = { "vector-effect": "non-scaling-stroke" };

    // Wind particles (behind everything)
    this.particles = el("path", { ...thin, fill: "none", stroke: COLORS.particles,
      "stroke-width": 1.5 }, world);
    const rand = rng(3);
    this.lanes = Array.from({ length: 15 }, (_, i) => -9 + (18 * i) / 14);
    this.phase = this.lanes.map(() => Array.from({ length: 6 }, rand));
    this.airS = 0;
    this.lastT = null;

    // Ground, stand and horizon
    el("line", { ...thin, x1: -30, y1: -5, x2: 30, y2: -5, stroke: COLORS.stand, "stroke-width": 2 }, world);
    el("polygon", { points: pts([[-0.12, 0], [0.12, 0], [0.25, -5], [-0.25, -5]]), fill: COLORS.stand }, world);
    el("polygon", { points: pts([[-1.6, -5], [1.6, -5], [1.2, -4.75], [-1.2, -4.75]]), fill: COLORS.stand }, world);
    el("line", { ...thin, x1: -30, y1: 0, x2: 30, y2: 0, stroke: COLORS.horizon,
      "stroke-width": 1, "stroke-dasharray": "6 4" }, world);

    // Aircraft, rotated by θ about the pivot
    const ac = el("g", {}, world);
    this.aircraft = ac;
    const poly = (p, fill) => el("polygon", { ...thin, points: pts(p), fill,
      stroke: COLORS.outline, "stroke-width": 1 }, ac);
    poly(VTAIL, COLORS.airframe);
    poly(FUSELAGE, COLORS.airframe);
    poly(WINDOW, COLORS.window);
    poly(WING, COLORS.airframe2);
    poly(HSTAB, COLORS.airframe2);
    for (const [line, color] of [[STRUT, COLORS.outline], [NOSE_STRUT, COLORS.outline], [PROP, "#8a949e"]]) {
      el("polyline", { ...thin, points: pts(line), fill: "none", stroke: color, "stroke-width": 2 }, ac);
    }
    for (const [cx, cy, r] of [[-0.55, -1.15, 0.22], [2.0, -1.05, 0.18]]) {
      el("circle", { ...thin, cx, cy, r, fill: "#2b2f33", stroke: COLORS.outline, "stroke-width": 1 }, ac);
    }
    const elevPts = pts(ELEVATOR.map(([x, y]) => [HINGE[0] + x, HINGE[1] + y]));
    this.elevatorGhost = el("polygon", { ...thin, points: elevPts, fill: "none",
      stroke: COLORS.ghost, "stroke-width": 1, "stroke-dasharray": "3 2" }, ac);
    this.elevator = el("polygon", { ...thin, points: elevPts, fill: COLORS.elevator,
      stroke: COLORS.elevator, "stroke-width": 1 }, ac);

    el("circle", { ...thin, cx: 0, cy: 0, r: 0.14, fill: "#2b2f33", stroke: COLORS.text,
      "stroke-width": 1 }, world);

    // Body axis, relative wind, and the θ / α arcs
    const dotted = (color) => el("line", { ...thin, stroke: color, "stroke-width": 1,
      "stroke-dasharray": "2 3" }, world);
    this.bodyAxis = dotted(COLORS.theta);
    this.windAxis = dotted(COLORS.alpha);
    this.thetaArc = el("polyline", { ...thin, fill: "none", stroke: COLORS.theta, "stroke-width": 2 }, world);
    this.alphaArc = el("polyline", { ...thin, fill: "none", stroke: COLORS.alpha, "stroke-width": 2 }, world);

    // Air control arrow and its drag handle
    this.arrowLine = el("line", { ...thin, stroke: COLORS.arrow, "stroke-width": 3 }, world);
    this.arrowHead = el("polygon", { points: "0,0 -0.45,0.17 -0.45,-0.17", fill: COLORS.arrow }, world);
    this.handle = el("circle", { ...thin, r: 0.22, fill: COLORS.bg, stroke: COLORS.arrow,
      "stroke-width": 2, class: "air-handle" }, world);

    // Text (unflipped: world (x, y) is drawn at (x, -y))
    const text = (color, anchor) => el("text", { fill: color, "text-anchor": anchor,
      "dominant-baseline": "middle", class: "view-label" }, svg);
    this.thetaLabel = text(COLORS.theta, "start");
    this.alphaLabel = text(COLORS.alpha, "start");
    this.airLabel = text(COLORS.arrow, "middle");

    this._bindDrag();
    this.setAirTarget(55, 0);
  }

  // ------------------------------------------------------------------ air
  setInteractive(on) {
    this.interactive = on;
    this.handle.style.display = on ? "" : "none";
  }

  setAirTarget(airspeed, flow) {
    if (this.dragging) return;
    this.target = [airspeed, flow];
    const len = airspeed * ARROW_M_PER_MPS;
    this._drawArrow([ANCHOR[0] + len * Math.cos(flow), ANCHOR[1] - len * Math.sin(flow)], airspeed, flow);
  }

  _drawArrow(tail, airspeed, flow) {
    const set = (node, attrs) => { for (const k in attrs) node.setAttribute(k, attrs[k]); };
    set(this.arrowLine, { x1: tail[0], y1: tail[1], x2: ANCHOR[0], y2: ANCHOR[1] });
    // Head points from the tail toward the anchor: direction angle = -flow + 180°
    set(this.arrowHead, { transform: `translate(${ANCHOR[0]},${ANCHOR[1]}) rotate(${180 - flow / DEG})` });
    set(this.handle, { cx: tail[0], cy: tail[1] });
    // Keep the label inside the view (the right edge is at x = 9)
    set(this.airLabel, { x: Math.min(tail[0], 7.2), y: -(Math.min(tail[1], ANCHOR[1]) - 0.45) });
    this.airLabel.textContent = `air ${airspeed.toFixed(0)} m/s, ${fmt(flow / DEG)}°`;
  }

  _handleToAir([x, y]) {
    const { airspeedRange: [lo, hi], flowRange } = this.opts;
    const dx = x - ANCHOR[0], dy = y - ANCHOR[1];
    const airspeed = Math.min(Math.max(Math.hypot(dx, dy) / ARROW_M_PER_MPS, lo), hi);
    const flow = Math.min(Math.max(Math.atan2(-dy, Math.max(dx, 1e-6)), -flowRange), flowRange);
    return [airspeed, flow];
  }

  _toWorld(ev) {
    const m = this.world.getScreenCTM().inverse();
    const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(m);
    return [p.x, p.y];
  }

  _bindDrag() {
    const h = this.handle;
    h.addEventListener("pointerdown", (ev) => {
      if (!this.interactive) return;
      this.dragging = true;
      h.setPointerCapture(ev.pointerId);
      ev.preventDefault();
    });
    h.addEventListener("pointermove", (ev) => {
      if (!this.dragging) return;
      const p = this._toWorld(ev);
      const [airspeed, flow] = this._handleToAir(p);
      this._drawArrow(p, airspeed, flow);
    });
    const release = (ev) => {
      if (!this.dragging) return;
      this.dragging = false;
      const [airspeed, flow] = this._handleToAir(this._toWorld(ev));
      this.setAirTarget(airspeed, flow);          // snap to the clamped value
      this.opts.onAirDragged(airspeed, flow);
    };
    h.addEventListener("pointerup", release);
    h.addEventListener("pointercancel", release);
  }

  // ---------------------------------------------------------------- frame
  _updateParticles(t, airspeed, flow) {
    if (this.lastT !== null) {
      if (t < this.lastT) this.airS = 0;
      else this.airS += (t - this.lastT) * airspeed * PARTICLE_SPEED_SCALE;
    }
    this.lastT = t;
    const d = [-Math.cos(flow), Math.sin(flow)];     // the air moves this way
    const n = [Math.sin(flow), Math.cos(flow)];
    const span = 24, seg = 0.25 + 0.012 * airspeed, head = 0.18;
    const parts = [];
    const p = (x, y) => `${x.toFixed(3)} ${y.toFixed(3)}`;
    this.lanes.forEach((lane, i) => {
      for (const ph of this.phase[i]) {
        const s = (((ph * span + this.airS) % span) + span) % span - span / 2;
        const x0 = lane * n[0] + s * d[0], y0 = lane * n[1] + s * d[1];
        const x1 = x0 + seg * d[0], y1 = y0 + seg * d[1];
        parts.push(`M${p(x0, y0)}L${p(x1, y1)}`);
        for (const side of [1, -1]) {
          const bx = x1 - head * d[0] + side * 0.5 * head * n[0];
          const by = y1 - head * d[1] + side * 0.5 * head * n[1];
          parts.push(`M${p(x1, y1)}L${p(bx, by)}`);
        }
      }
    });
    this.particles.setAttribute("d", parts.join(""));
  }

  /** Draw one frame. Angles in radians. */
  update({ t, theta, alpha, de, deCmd, airspeed, flow }) {
    const ex = this.exaggerate;
    this.aircraft.setAttribute("transform", `rotate(${theta / DEG})`);
    const hinge = `${HINGE[0]} ${HINGE[1]}`;
    this.elevator.setAttribute("transform", `rotate(${(de * ex) / DEG} ${hinge})`);
    this.elevatorGhost.setAttribute("transform", `rotate(${(deCmd * ex) / DEG} ${hinge})`);
    this._updateParticles(t, airspeed, flow);

    const wind = theta - alpha;           // relative wind direction
    const r = 3.8;
    const line = (node, len, a) => {
      node.setAttribute("x1", 0); node.setAttribute("y1", 0);
      node.setAttribute("x2", len * Math.cos(a)); node.setAttribute("y2", len * Math.sin(a));
    };
    line(this.bodyAxis, 4.6, theta);
    line(this.windAxis, 5.4, wind);
    this.thetaArc.setAttribute("points", arcPoints(r, 0, theta));
    this.alphaArc.setAttribute("points", arcPoints(r + 0.7, wind, theta));
    // Labels beside the arcs: θ below, α above, so they never overlap
    const low = Math.min(0, theta, wind), high = Math.max(0, theta, wind);
    const place = (node, x, y, label) => {
      node.setAttribute("x", x); node.setAttribute("y", -y); node.textContent = label;
    };
    place(this.thetaLabel, r * Math.cos(low) - 0.4, r * Math.sin(low) - 0.45, `θ ${fmt(theta / DEG)}°`);
    place(this.alphaLabel, (r + 0.7) * Math.cos(high) - 0.4, (r + 0.7) * Math.sin(high) + 0.45,
      `α ${fmt(alpha / DEG)}°`);
  }
}
