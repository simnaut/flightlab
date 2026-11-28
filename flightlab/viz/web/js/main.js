// FlightLab viewer. Preact renders the layout and controls; the side view and
// plots are plain classes that Preact mounts once and that redraw themselves
// from the Store on each animation frame.

import { h, render } from "preact";
import { useEffect, useRef } from "preact/hooks";
import { signal, computed, effect, batch } from "@preact/signals";
import htm from "htm";

import { Connection } from "./connection.js";
import { Store } from "./store.js";
import { SideView } from "./side_view.js";
import { Plots, plotSpecs } from "./plots.js";
import { DEG } from "./theme.js";

const html = htm.bind(h);
const SPEEDS = [0.1, 0.25, 0.5, 1, 2, 4];
const ELEVATOR_KEY_STEP = 0.5;     // degrees per ↑/↓ key press

// ------------------------------------------------------------------ state
const store = new Store();
const conn = signal("connecting");          // connecting | open | closed
const everConnected = signal(false);
const hello = signal(null);                 // the server's hello message
const run = signal(null);                   // latest frame state
const studentSignals = signal([]);          // names seen in self.log()
const selected = signal([]);                // names shown in the plot

// Control values (the browser's side of the controls; synced from the server
// on connect and after a reset)
const manual = signal(false);
const elevatorDeg = signal(0);
const airspeed = signal(55);
const flowDeg = signal(0);
const smooth = signal(true);

const live = computed(() => !!hello.value?.live);

// Viewer elements unlocked up to this chapter (chapter.yaml: viewer.unlock).
// Running with --manual always shows the manual controls.
const features = computed(() => {
  const f = new Set(hello.value?.features ?? []);
  if (hello.value?.mode === "manual") f.add("manual");
  return f;
});
const has = (name) => features.value.has(name);

let sideView = null;
let plots = null;
let infoBox = null;
let dirty = false;
let lastGeneration = null;

// ----------------------------------------------------------- connection
const connection = new Connection({
  onStatus(status) {
    conn.value = status;
    if (status === "open") everConnected.value = true;
  },
  onMessage(msg) {
    if (msg.type === "hello") onHello(msg);
    else if (msg.type === "frame") onFrame(msg);
  },
});

const send = (type, fields = {}) => connection.send({ type, ...fields });

function onHello(msg) {
  hello.value = msg;
  lastGeneration = null;
  const mode = { controller: "", manual: " (manual)", open_loop: " (open loop)", replay: " (replay)" }[msg.mode] ?? "";
  document.title = `FlightLab ${msg.chapter.id}: ${msg.chapter.title}${mode}`;
}

function onFrame(msg) {
  const st = msg.state;
  if (msg.rows) store.ingest(msg.rows, msg.reset);
  batch(() => {
    if (st.generation !== lastGeneration) {
      lastGeneration = st.generation;
      if (st.air_target) {
        airspeed.value = st.air_target.airspeed;
        flowDeg.value = st.air_target.flow_angle / DEG;
      }
      if (st.manual !== undefined) {
        manual.value = st.manual;
        elevatorDeg.value = st.elevator / DEG;
      }
    }
    run.value = st;
    const names = store.studentSignals();
    const known = studentSignals.value;
    if (names.join("\n") !== known.join("\n")) {
      const fresh = names.filter((n) => !known.includes(n));
      studentSignals.value = names;
      selected.value = [...selected.value.filter((n) => names.includes(n)), ...fresh].sort();
    }
  });
  dirty = true;
}

// --------------------------------------------------------------- actions
function togglePause() {
  const st = run.value;
  if (!st || st.error) return;
  send(st.run === "paused" ? "resume" : "pause");
}

function setManual(on) {
  manual.value = on;
  send("manual", { enabled: on });
  if (on) send("elevator", { value: elevatorDeg.value * DEG });
}

function setElevator(deg) {
  const range = (hello.value?.elevator_range ?? 25 * DEG) / DEG;
  elevatorDeg.value = Math.min(Math.max(deg, -range), range);
  send("elevator", { value: elevatorDeg.value * DEG });
}

function setAir(speed, flow) {
  batch(() => { airspeed.value = speed; flowDeg.value = flow; });
  send("set_air", { airspeed: speed, flow_angle: flow * DEG, smooth: smooth.value });
}

function resetAir() {
  const t = hello.value.tunnel;
  batch(() => { airspeed.value = t.airspeed; flowDeg.value = t.flow_angle / DEG; });
  send("reset_air", { smooth: smooth.value });
}

// Keyboard: ↑ push (nose down), ↓ pull (nose up), space centers; P pauses.
window.addEventListener("keydown", (ev) => {
  if (!hello.value || ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (ev.target instanceof HTMLSelectElement) return;
  const key = ev.key;
  if (key === "p" || key === "P") {
    togglePause();
    ev.preventDefault();
    return;
  }
  if (!live.value || !has("manual") || !["ArrowUp", "ArrowDown", " "].includes(key)) return;
  ev.preventDefault();
  if (!manual.value) setManual(true);
  if (key === "ArrowUp") setElevator(elevatorDeg.value + ELEVATOR_KEY_STEP);
  else if (key === "ArrowDown") setElevator(elevatorDeg.value - ELEVATOR_KEY_STEP);
  else setElevator(0);
});

// --------------------------------------------------------------- drawing
const fmt = (v, digits = 2, width = 6) => ((v >= 0 ? "+" : "") + v.toFixed(digits)).padStart(width);

function modeLabel(manualNow) {
  if (manualNow) return "MANUAL";
  const mode = hello.value?.mode;
  return { controller: "YOUR CONTROLLER", manual: "MANUAL", open_loop: "OPEN LOOP", replay: "REPLAY" }[mode] ?? "";
}

function draw() {
  requestAnimationFrame(draw);
  if (!dirty || !sideView || !plots || store.n === 0) return;
  dirty = false;
  const st = run.value;
  const t = st ? st.t : store.last("t", 0);
  const v = (name, fallback = 0) => store.last(name, fallback);
  const theta = v("theta"), alpha = v("alpha"), de = v("de"), deCmd = v("de_cmd");
  const air = v("tunnel_airspeed", 55), flow = v("tunnel_flow");
  sideView.update({ t, theta, alpha, de, deCmd, airspeed: air, flow });
  if (infoBox) {
    const lines = [`t = ${t.toFixed(2).padStart(6)} s    ${hello.value?.live ? modeLabel(v("manual") > 0.5) : "REPLAY"}`];
    lines.push(`θ  ${fmt(theta / DEG)}°` + (has("theta_cmd") ? `   cmd ${fmt(v("ref_theta") / DEG)}°` : ""));
    if (has("tunnel")) lines.push(`α  ${fmt(alpha / DEG)}°`);
    if (has("pitch_rate")) lines.push(`q  ${fmt(v("q") / DEG)}°/s`);
    lines.push(`δe ${fmt(de / DEG)}°`);
    if (has("tunnel")) lines.push(`V  ${air.toFixed(1).padStart(5)} m/s   flow ${fmt(flow / DEG, 1, 5)}°`);
    infoBox.textContent = lines.join("\n");
  }
  plots.setStudentSignals(selected.value);
  plots.update(store, t);
  document.body.dataset.ready = "1";
}
requestAnimationFrame(draw);

effect(() => { if (sideView) sideView.setAirTarget(airspeed.value, flowDeg.value * DEG); });
effect(() => { selected.value; dirty = true; });

// ------------------------------------------------------------ components
function ViewPanel() {
  const ref = useRef(null);
  const info = useRef(null);
  useEffect(() => {
    const t = hello.value.tunnel;
    sideView = new SideView(ref.current, {
      airspeedRange: t.airspeed_range,
      flowRange: t.flow_range,
      onAirDragged: (speed, flow) => setAir(speed, flow / DEG),
    });
    sideView.setFeatures(features.value);
    sideView.setInteractive(live.value);
    sideView.setAirTarget(airspeed.value, flowDeg.value * DEG);
    infoBox = info.current;
    dirty = true;
    return () => { sideView = null; infoBox = null; ref.current.replaceChildren(); };
  }, []);
  const st = run.value;
  const kicking = store.last("kick", 0) !== 0;
  return html`
    <section class="view">
      <div class="view-canvas" ref=${ref}></div>
      <pre class="info" ref=${info}></pre>
      ${st?.error ? html`<div class="banner error">CONTROLLER ERROR: see message</div>`
        : st?.busy ? html`<div class="banner busy">Waiting for your code (stopped at a breakpoint?)</div>`
        : kicking ? html`<div class="banner">KICK!</div>` : null}
      ${st?.error && html`<${ErrorPanel} error=${st.error} />`}
    </section>`;
}

function ErrorPanel({ error }) {
  return html`
    <div class="error-panel" role="alert">
      <h2>Controller error</h2>
      <p>${error.message}</p>
      ${error.details && html`<pre>${error.details}</pre>`}
      <p class="hint">${error.details ? "Fix your file, then press Reset to run again." : "Press Reset to run again."}</p>
      <button onClick=${() => send("reset")}>Reset</button>
    </div>`;
}

function SimControls() {
  const st = run.value;
  const paused = !st || st.run !== "running";
  return html`
    <fieldset class="box">
      <legend>Simulation</legend>
      <button class="primary" onClick=${togglePause} disabled=${!!st?.error}>
        ${paused ? "▶ Play" : "❚❚ Pause"}</button>
      ${has("sim_step") && html`
        <button onClick=${() => send("step")} title="Advance one controller update (pauses)">Step</button>`}
      <button onClick=${() => send("reset")}>Reset</button>
      ${has("sim_step") && html`
        <label class="inline">Speed
          <select value=${String(st?.speed ?? 1)}
            onChange=${(e) => send("speed", { value: Number(e.currentTarget.value) })}>
            ${SPEEDS.map((s) => html`<option value=${String(s)}>${s}×</option>`)}
          </select>
        </label>`}
    </fieldset>`;
}

function DisturbControls() {
  if (!has("kick")) return null;
  return html`
    <fieldset class="box">
      <legend>Disturb</legend>
      <button disabled=${!live.value} title="Short nose-up push on the aircraft"
        onClick=${() => send("kick", { sign: 1 })}>Kick ▲</button>
      <button disabled=${!live.value} title="Short nose-down push on the aircraft"
        onClick=${() => send("kick", { sign: -1 })}>Kick ▼</button>
    </fieldset>`;
}

function ManualControls() {
  if (!has("manual")) return null;
  const range = (hello.value.elevator_range ?? 25 * DEG) / DEG;
  return html`
    <fieldset class="box wide" disabled=${!live.value}>
      <legend>Manual control <span class="muted">(keys: ↑ push, ↓ pull, space = center)</span></legend>
      <label class="inline">
        <input type="checkbox" checked=${manual.value}
          onChange=${(e) => setManual(e.currentTarget.checked)} /> Fly by hand
      </label>
      <span class="muted">nose up</span>
      <input type="range" class="grow" min=${-range} max=${range} step="0.1"
        value=${elevatorDeg.value}
        title="Elevator deflection. Right = trailing edge down = nose DOWN"
        onInput=${(e) => setElevator(Number(e.currentTarget.value))} />
      <span class="muted">nose down</span>
      <output class="readout">δe ${fmt(elevatorDeg.value, 1, 5)}°</output>
    </fieldset>`;
}

function TunnelControls() {
  if (!has("tunnel")) return null;
  const t = hello.value.tunnel;
  const [lo, hi] = t.airspeed_range;
  const flowMax = t.flow_range / DEG;
  return html`
    <fieldset class="box wide tunnel" disabled=${!live.value}>
      <legend>Wind tunnel <span class="muted">(or drag the blue arrow)</span></legend>
      <label>Airspeed</label>
      <input type="range" min=${lo} max=${hi} step="1" value=${airspeed.value}
        onInput=${(e) => setAir(Number(e.currentTarget.value), flowDeg.value)} />
      <output class="readout">${airspeed.value.toFixed(0)} m/s</output>
      <label class="inline" title="Changes ramp in over 1 second">
        <input type="radio" name="ramp" checked=${smooth.value}
          onChange=${() => { smooth.value = true; }} /> Smooth</label>
      <button class="reset-air" onClick=${resetAir}>Reset air</button>
      <label>Flow angle</label>
      <input type="range" min=${-flowMax} max=${flowMax} step="0.5" value=${flowDeg.value}
        onInput=${(e) => setAir(airspeed.value, Number(e.currentTarget.value))} />
      <output class="readout">${fmt(flowDeg.value, 1, 5)}°</output>
      <label class="inline" title="Changes apply instantly, like a sharp-edged gust">
        <input type="radio" name="ramp" checked=${!smooth.value}
          onChange=${() => { smooth.value = false; }} /> Step</label>
    </fieldset>`;
}

function PlotsPanel() {
  const ref = useRef(null);
  useEffect(() => {
    plots = new Plots(ref.current, plotSpecs(features.value));
    dirty = true;
    return () => { plots.ro.disconnect(); plots = null; };
  }, []);
  return html`<div class="plots" ref=${ref}></div>`;
}

function SignalPicker() {
  const names = studentSignals.value;
  const toggle = (name, on) => {
    const set = new Set(selected.value);
    if (on) set.add(name); else set.delete(name);
    selected.value = [...set].sort();
  };
  if (names.length === 0) return null;     // appears once the controller logs something
  return html`
    <fieldset class="box signals">
      <legend>Your signals <span class="muted">(from <code>self.log()</code>)</span></legend>
      ${names.map((name) => html`
          <label class="inline">
            <input type="checkbox" checked=${selected.value.includes(name)}
              onChange=${(e) => toggle(name, e.currentTarget.checked)} /> ${name}
          </label>`)}
    </fieldset>`;
}

function StatusBar() {
  const st = run.value;
  if (!st) return html`<footer class="status">Waiting for the simulation…</footer>`;
  const label = { running: "Running", paused: "Paused", finished: "Finished", error: "Stopped: controller error" }[st.run];
  const dur = hello.value.chapter.duration;
  let extra = hello.value.live && st.t > dur ? "   (scenario finished, free play)" : "";
  if (st.run === "running" && st.actual_speed !== null && st.actual_speed < 0.9 * st.speed) {
    extra += `   (the sim can only keep up with ${st.actual_speed.toFixed(1)}× on this computer)`;
  }
  return html`<footer class="status">${label}   speed ${st.speed}×   t = ${st.t.toFixed(2)} s${extra}</footer>`;
}

function ConnectionOverlay() {
  if (conn.value === "open") return null;
  const lost = everConnected.value;
  return html`
    <div class="overlay">
      <div class="card">
        ${lost ? html`
          <h2>Lost connection to FlightLab</h2>
          <p>The run has ended, or <code>flightlab</code> was stopped in the terminal.
            Trying to reconnect…</p>
          <p class="muted">If you started a new run, use the new link it printed and close this tab.</p>`
        : html`<h2>Connecting to FlightLab…</h2>
          <p class="muted">Start a run from the terminal, e.g. <code>flightlab run 1.00</code>,
            and open the link it prints.</p>`}
      </div>
    </div>`;
}

function App() {
  const hi = hello.value;
  if (!hi) return html`<${ConnectionOverlay} />`;
  const mode = { controller: "", manual: "manual", open_loop: "open loop", replay: "replay" }[hi.mode];
  return html`
    <div class="app">
      <header>
        <h1>FlightLab <span class="chapter">${hi.chapter.id}</span> ${hi.chapter.title}</h1>
        ${mode && html`<span class="tag">${mode}</span>`}
      </header>
      <main>
        <div class="left">
          <${ViewPanel} />
          <div class="controls">
            <${SimControls} />
            <${DisturbControls} />
            <${ManualControls} />
            <${TunnelControls} />
          </div>
        </div>
        <div class="right">
          <${PlotsPanel} />
          <${SignalPicker} />
        </div>
      </main>
      <${StatusBar} />
      <${ConnectionOverlay} />
    </div>`;
}

render(html`<${App} />`, document.getElementById("app"));
connection.open();
