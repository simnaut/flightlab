"""FlightLab viewer: live simulation or replay of a saved run."""

import math
import sys
import time

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from flightlab.sim.simulation import ControllerError, SimulationError
from flightlab.viz.side_view import COLORS, SideView

DEG = math.pi / 180.0
PLOT_WINDOW_S = 20.0
FPS = 30
SPEEDS = ["0.1×", "0.25×", "0.5×", "1×", "2×", "4×"]


# ---------------------------------------------------------------- sources
class LiveSource:
    """Runs a Simulation as the viewer plays."""

    live = True

    def __init__(self, sim):
        self.sim = sim

    @property
    def log(self):
        return self.sim.log

    @property
    def t(self):
        return self.sim.t

    def advance(self, dt):
        self.sim.advance(self.sim.t + dt)

    def step_once(self):
        self.sim.advance(self.sim.t + self.sim.ctrl_dt)

    def reset(self):
        self.sim.reset()

    def value(self, name, default=math.nan):
        return self.log.last(name, default)

    def end_index(self):
        return self.log.n


class ReplaySource:
    """Plays back a saved RunLog."""

    live = False

    def __init__(self, log):
        self._log = log
        self._t = 0.0
        self.duration = float(log["t"][-1]) if log.n else 0.0

    @property
    def log(self):
        return self._log

    @property
    def t(self):
        return self._t

    def advance(self, dt):
        self._t = min(self.duration, self._t + dt)

    def step_once(self):
        self.advance(0.02)

    def reset(self):
        self._t = 0.0

    def value(self, name, default=math.nan):
        if name not in self._log:
            return default
        return self._log[name][self._log.index_at(self._t)]

    def end_index(self):
        return self._log.index_at(self._t) + 1


# ------------------------------------------------------------------ plots
TRACES = [
    # plot title, units, [(channel, label, color, dashed, scale)]
    ("Pitch angle", "deg", [("ref_theta", "θ cmd", "#ffffff", True, 1 / DEG),
                            ("theta", "θ", COLORS["theta"], False, 1 / DEG)]),
    ("Angle of attack & pitch rate", "deg, deg/s",
     [("alpha", "α (deg)", COLORS["alpha"], False, 1 / DEG),
      ("q", "q (deg/s)", "#ce93d8", False, 1 / DEG)]),
    ("Elevator", "deg", [("de_cmd", "δe cmd", "#ffffff", True, 1 / DEG),
                         ("de", "δe actual", COLORS["elevator"], False, 1 / DEG)]),
    ("Wind tunnel air", "m/s, deg",
     [("tunnel_airspeed", "airspeed (m/s)", COLORS["arrow"], False, 1.0),
      ("tunnel_flow", "flow angle (deg)", "#81c784", False, 1 / DEG)]),
]
STUDENT_COLORS = ["#ff8a80", "#b9f6ca", "#80d8ff", "#ffff8d", "#ea80fc", "#ffd180"]


class Plots(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setBackground(COLORS["bg"])
        self.curves = []
        self.plots = []
        first = None
        for row, (title, units, traces) in enumerate(TRACES + [("Your signals (self.log)", "", [])]):
            p = self.addPlot(row=row, col=0)
            p.setTitle(f"<span style='color:#c8ccd0'>{title}</span>", size="9pt")
            p.showGrid(x=True, y=True, alpha=0.15)
            p.setMouseEnabled(x=False, y=False)
            p.hideButtons()
            p.getAxis("left").setWidth(42)
            legend = p.addLegend(offset=(5, 5), labelTextSize="8pt",
                                 brush=pg.mkBrush(15, 20, 25, 180))
            legend.setColumnCount(2)
            if first is None:
                first = p
            else:
                p.setXLink(first)
            for channel, label, color, dashed, scale in traces:
                pen = pg.mkPen(color, width=2 if not dashed else 1.5,
                               style=QtCore.Qt.PenStyle.DashLine if dashed
                               else QtCore.Qt.PenStyle.SolidLine)
                curve = p.plot(pen=pen, name=label)
                self.curves.append((curve, channel, scale))
            self.plots.append(p)
        self.student_plot = self.plots[-1]
        self.student_curves = {}
        self.selected_student = set()

    def set_student_selection(self, names):
        self.selected_student = set(names)
        for name in list(self.student_curves):
            if name not in self.selected_student:
                curve = self.student_curves.pop(name)
                self.student_plot.removeItem(curve)
                self.student_plot.legend.removeItem(curve)

    def update_from(self, source):
        log = source.log
        if log.n == 0:
            return
        end = source.end_index()
        t_now = source.t
        start = log.index_at(t_now - PLOT_WINDOW_S)
        times = log["t"][start:end]
        for curve, channel, scale in self.curves:
            if channel in log:
                curve.setData(times, log[channel][start:end] * scale)
            else:
                curve.setData([], [])
        for i, name in enumerate(sorted(self.selected_student)):
            channel = f"log.{name}"
            if channel not in log:
                continue
            curve = self.student_curves.get(name)
            if curve is None:
                color = STUDENT_COLORS[i % len(STUDENT_COLORS)]
                curve = self.student_plot.plot(pen=pg.mkPen(color, width=2), name=name)
                self.student_curves[name] = curve
            curve.setData(times, log[channel][start:end], connect="finite")
        self.plots[0].setXRange(max(0.0, t_now - PLOT_WINDOW_S), max(PLOT_WINDOW_S, t_now),
                                padding=0)


# ---------------------------------------------------------------- window
def _slider(lo, hi, value, orientation=QtCore.Qt.Orientation.Horizontal):
    s = QtWidgets.QSlider(orientation)
    s.setRange(lo, hi)
    s.setValue(value)
    return s


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, source, chapter, title_extra=""):
        super().__init__()
        self.source = source
        self.chapter = chapter
        self.paused = False
        self.speed = 1.0
        self.error_text = ""
        self._last_wall = None
        self._syncing = False
        self.saved_folder = None

        mode = ""
        if source.live:
            mode = {"controller": "", "manual": " — manual", "open_loop": " — open loop"}[
                source.sim.mode]
        self.setWindowTitle(f"FlightLab {chapter.id}: {chapter.title}{mode}{title_extra}")
        self.resize(1500, 900)

        tunnel = chapter.config["tunnel"]
        self.view = SideView()
        self.view.set_air_target(tunnel["airspeed_mps"], tunnel["flow_angle_deg"] * DEG)
        self.view.airDragged.connect(self._on_air_dragged)
        self.view.set_interactive_air(source.live)
        self.plots = Plots()

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.view, stretch=3)
        left_layout.addWidget(self._build_controls(), stretch=0)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.plots, stretch=1)
        right_layout.addWidget(self._build_signal_picker(), stretch=0)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([820, 680])
        self.setCentralWidget(splitter)
        self.status = self.statusBar()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000 / FPS))
        self._refresh()

    # ------------------------------------------------------------ controls
    def _build_controls(self):
        panel = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(panel)
        grid.setContentsMargins(8, 4, 8, 4)
        live = self.source.live

        # Simulation
        sim_box = QtWidgets.QGroupBox("Simulation")
        h = QtWidgets.QHBoxLayout(sim_box)
        self.play_btn = QtWidgets.QPushButton("❚❚ Pause")
        self.play_btn.clicked.connect(self._toggle_pause)
        step_btn = QtWidgets.QPushButton("Step")
        step_btn.setToolTip("Advance one controller update (while paused)")
        step_btn.clicked.connect(self._step)
        reset_btn = QtWidgets.QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        self.speed_box = QtWidgets.QComboBox()
        self.speed_box.addItems(SPEEDS)
        self.speed_box.setCurrentText("1×")
        self.speed_box.currentTextChanged.connect(
            lambda s: setattr(self, "speed", float(s.rstrip("×"))))
        for w in (self.play_btn, step_btn, reset_btn, QtWidgets.QLabel("Speed"), self.speed_box):
            h.addWidget(w)
        grid.addWidget(sim_box, 0, 0)

        # Disturbances + view options
        dist_box = QtWidgets.QGroupBox("Disturb / view")
        h = QtWidgets.QHBoxLayout(dist_box)
        kick_up = QtWidgets.QPushButton("Kick ▲")
        kick_up.setToolTip("Short nose-up push on the aircraft")
        kick_up.clicked.connect(lambda: self._kick(+1))
        kick_dn = QtWidgets.QPushButton("Kick ▼")
        kick_dn.setToolTip("Short nose-down push on the aircraft")
        kick_dn.clicked.connect(lambda: self._kick(-1))
        self.exag = QtWidgets.QCheckBox("Elevator ×3")
        self.exag.setToolTip("Draw the elevator deflection 3× larger so small moves are visible")
        self.exag.toggled.connect(lambda on: setattr(self.view, "exaggerate", 3.0 if on else 1.0))
        for w in (kick_up, kick_dn, self.exag):
            h.addWidget(w)
        kick_up.setEnabled(live)
        kick_dn.setEnabled(live)
        grid.addWidget(dist_box, 0, 1)

        # Manual
        man_box = QtWidgets.QGroupBox("Manual control  (keys: ↑ push, ↓ pull, space = center)")
        h = QtWidgets.QHBoxLayout(man_box)
        self.manual_chk = QtWidgets.QCheckBox("Fly by hand")
        self.manual_chk.toggled.connect(self._toggle_manual)
        self.elev_slider = _slider(-250, 250, 0)
        self.elev_slider.setToolTip("Elevator deflection. Right = trailing edge down = nose DOWN")
        self.elev_slider.valueChanged.connect(self._on_elevator_slider)
        self.elev_label = QtWidgets.QLabel("δe  +0.0°")
        self.elev_label.setMinimumWidth(70)
        h.addWidget(self.manual_chk)
        h.addWidget(QtWidgets.QLabel("nose up"))
        h.addWidget(self.elev_slider, stretch=1)
        h.addWidget(QtWidgets.QLabel("nose down"))
        h.addWidget(self.elev_label)
        man_box.setEnabled(live)
        if live and self.source.sim.mode == "manual":
            self.manual_chk.setChecked(True)
        grid.addWidget(man_box, 1, 0, 1, 2)

        # Wind tunnel
        air_box = QtWidgets.QGroupBox("Wind tunnel  (or drag the blue arrow)")
        g = QtWidgets.QGridLayout(air_box)
        tunnel = self.chapter.config["tunnel"]
        self.speed_slider = _slider(15, 70, int(tunnel["airspeed_mps"]))
        self.flow_slider = _slider(-30, 30, int(round(tunnel["flow_angle_deg"] * 2)))
        self.speed_label = QtWidgets.QLabel()
        self.flow_label = QtWidgets.QLabel()
        for lbl in (self.speed_label, self.flow_label):
            lbl.setMinimumWidth(80)
        self.speed_slider.valueChanged.connect(self._on_air_slider)
        self.flow_slider.valueChanged.connect(self._on_air_slider)
        self.smooth_radio = QtWidgets.QRadioButton("Smooth")
        self.step_radio = QtWidgets.QRadioButton("Step")
        self.smooth_radio.setChecked(True)
        self.smooth_radio.setToolTip("Changes ramp in over 1 second")
        self.step_radio.setToolTip("Changes apply instantly, like a sharp-edged gust")
        reset_air = QtWidgets.QPushButton("Reset air")
        reset_air.clicked.connect(self._reset_air)
        g.addWidget(QtWidgets.QLabel("Airspeed"), 0, 0)
        g.addWidget(self.speed_slider, 0, 1)
        g.addWidget(self.speed_label, 0, 2)
        g.addWidget(self.smooth_radio, 0, 3)
        g.addWidget(QtWidgets.QLabel("Flow angle"), 1, 0)
        g.addWidget(self.flow_slider, 1, 1)
        g.addWidget(self.flow_label, 1, 2)
        g.addWidget(self.step_radio, 1, 3)
        g.addWidget(reset_air, 0, 4, 2, 1)
        air_box.setEnabled(live)
        grid.addWidget(air_box, 2, 0, 1, 2)
        self._update_air_labels()
        return panel

    def _build_signal_picker(self):
        box = QtWidgets.QGroupBox("Your signals: call self.log(\"name\", value) in your controller")
        h = QtWidgets.QHBoxLayout(box)
        self.signal_list = QtWidgets.QListWidget()
        self.signal_list.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.signal_list.setWrapping(True)
        self.signal_list.setMaximumHeight(60)
        self.signal_list.itemChanged.connect(self._on_signal_toggled)
        h.addWidget(self.signal_list)
        self._known_signals = set()
        return box

    def _sync_signal_list(self):
        names = {n[4:] for n in self.source.log.names() if n.startswith("log.")}
        for name in sorted(names - self._known_signals):
            item = QtWidgets.QListWidgetItem(name)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Checked)
            self.signal_list.addItem(item)
            self._known_signals.add(name)
            self._on_signal_toggled()

    def _on_signal_toggled(self, *_):
        selected = [self.signal_list.item(i).text() for i in range(self.signal_list.count())
                    if self.signal_list.item(i).checkState() == QtCore.Qt.CheckState.Checked]
        self.plots.set_student_selection(selected)

    # ------------------------------------------------------------- actions
    def _toggle_pause(self):
        if self.error_text:
            return
        self.paused = not self.paused
        self.play_btn.setText("▶ Play" if self.paused else "❚❚ Pause")
        self._last_wall = None

    def _step(self):
        if not self.paused:
            self._toggle_pause()
        self._run_guarded(self.source.step_once)
        self._refresh()

    def _reset(self):
        self.save_log()
        self.error_text = ""
        self._run_guarded(self.source.reset)
        if self.source.live:
            tunnel = self.chapter.config["tunnel"]
            self._syncing = True
            self.speed_slider.setValue(int(tunnel["airspeed_mps"]))
            self.flow_slider.setValue(int(round(tunnel["flow_angle_deg"] * 2)))
            self._syncing = False
            self._update_air_labels()
            self.view.set_air_target(tunnel["airspeed_mps"], tunnel["flow_angle_deg"] * DEG)
            if self.manual_chk.isChecked():
                self.source.sim.set_manual(True)
                self.source.sim.set_manual_elevator(self.elev_slider.value() / 10 * DEG)
        if self.paused:
            self._toggle_pause()
        self._refresh()

    def _kick(self, sign):
        if self.source.live:
            self.source.sim.kick(sign)

    def _toggle_manual(self, on):
        if self.source.live:
            self.source.sim.set_manual(on)
            if on:
                self.source.sim.set_manual_elevator(self.elev_slider.value() / 10 * DEG)

    def _on_elevator_slider(self, value):
        self.elev_label.setText(f"δe {value / 10:+.1f}°")
        if self.source.live:
            self.source.sim.set_manual_elevator(value / 10 * DEG)

    def _air_values(self):
        return self.speed_slider.value(), self.flow_slider.value() / 2 * DEG

    def _update_air_labels(self):
        airspeed, flow = self._air_values()
        self.speed_label.setText(f"{airspeed:.0f} m/s")
        self.flow_label.setText(f"{flow / DEG:+.1f}°")

    def _on_air_slider(self, *_):
        self._update_air_labels()
        if self._syncing or not self.source.live:
            return
        airspeed, flow = self._air_values()
        self.view.set_air_target(airspeed, flow)
        self.source.sim.set_air(airspeed, flow, smooth=self.smooth_radio.isChecked())

    def _on_air_dragged(self, airspeed, flow):
        if not self.source.live:
            return
        self._syncing = True
        self.speed_slider.setValue(int(round(airspeed)))
        self.flow_slider.setValue(int(round(flow / DEG * 2)))
        self._syncing = False
        self._update_air_labels()
        self.source.sim.set_air(airspeed, flow, smooth=self.smooth_radio.isChecked())

    def _reset_air(self):
        if not self.source.live:
            return
        tunnel = self.chapter.config["tunnel"]
        self._syncing = True
        self.speed_slider.setValue(int(tunnel["airspeed_mps"]))
        self.flow_slider.setValue(int(round(tunnel["flow_angle_deg"] * 2)))
        self._syncing = False
        self._update_air_labels()
        self.view.set_air_target(tunnel["airspeed_mps"], tunnel["flow_angle_deg"] * DEG)
        self.source.sim.reset_air(smooth=self.smooth_radio.isChecked())

    def keyPressEvent(self, event):
        key = event.key()
        if key in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Space):
            if not self.manual_chk.isChecked():
                self.manual_chk.setChecked(True)
            v = self.elev_slider.value()
            if key == QtCore.Qt.Key.Key_Up:
                v += 5           # push: nose down
            elif key == QtCore.Qt.Key.Key_Down:
                v -= 5           # pull: nose up
            else:
                v = 0
            self.elev_slider.setValue(v)
            return
        if key == QtCore.Qt.Key.Key_P:
            self._toggle_pause()
            return
        super().keyPressEvent(event)

    # ---------------------------------------------------------------- loop
    def _run_guarded(self, fn, *args):
        try:
            fn(*args)
            return True
        except (ControllerError, SimulationError) as exc:
            self._show_error(exc)
            return False

    def _show_error(self, exc):
        self.error_text = str(exc)
        self.paused = True
        self.play_btn.setText("▶ Play")
        print("\n" + self.error_text, file=sys.stderr)
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        box.setWindowTitle("Controller error")
        box.setText(getattr(exc, "message", str(exc)))
        details = getattr(exc, "details", "")
        if details:
            box.setInformativeText("<pre>" + details.replace("<", "&lt;") + "</pre>")
        box.setInformativeText(box.informativeText() +
                               "<br>Fix your file, then press Reset to run again."
                               if details else "Press Reset to run again.")
        box.open()

    def _tick(self):
        now = time.perf_counter()
        if self._last_wall is None:
            self._last_wall = now
        wall_dt = min(now - self._last_wall, 0.1)
        self._last_wall = now
        if not self.paused and not self.error_text:
            self._run_guarded(self.source.advance, wall_dt * self.speed)
        self._refresh()

    def _refresh(self):
        s = self.source
        theta = s.value("theta", 0.0)
        alpha = s.value("alpha", 0.0)
        de = s.value("de", 0.0)
        de_cmd = s.value("de_cmd", 0.0)
        airspeed = s.value("tunnel_airspeed", 55.0)
        flow = s.value("tunnel_flow", 0.0)
        manual = s.value("manual", 0.0) > 0.5
        mode = "MANUAL" if manual else ("REPLAY" if not s.live else
                                         {"controller": "YOUR CONTROLLER",
                                          "manual": "MANUAL",
                                          "open_loop": "OPEN LOOP"}[s.sim.mode])
        info = (f"t = {s.t:6.2f} s    {mode}\n"
                f"θ  {theta / DEG:+6.2f}°   cmd {s.value('ref_theta', 0.0) / DEG:+6.2f}°\n"
                f"α  {alpha / DEG:+6.2f}°\n"
                f"δe {de / DEG:+6.2f}°\n"
                f"V  {airspeed:5.1f} m/s   flow {flow / DEG:+5.1f}°")
        banner = ""
        if s.value("kick", 0.0) != 0.0:
            banner = "KICK!"
        if self.error_text:
            banner = "CONTROLLER ERROR: see message"
        self.view.set_frame(s.t, theta, alpha, de, de_cmd, airspeed, flow, info, banner)
        self.plots.update_from(s)
        self._sync_signal_list()
        duration = self.chapter.config["duration_s"]
        extra = "" if s.t <= duration else "   (scenario finished, free play)"
        self.status.showMessage(f"{'Paused' if self.paused else 'Running'}   "
                                f"speed {self.speed:g}×{extra}")

    # -------------------------------------------------------------- saving
    def save_log(self):
        if self.source.live and self.source.t > 1.0:
            self.saved_folder = self.source.log.save(label="live")
            print(f"Run saved to {self.saved_folder}")

    def closeEvent(self, event):
        self.timer.stop()
        self.save_log()
        super().closeEvent(event)


# --------------------------------------------------------------- entry points
def _app():
    pg.setConfigOptions(antialias=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    for role, color in ((QtGui.QPalette.ColorRole.Window, "#1b2026"),
                        (QtGui.QPalette.ColorRole.WindowText, "#e6e6e6"),
                        (QtGui.QPalette.ColorRole.Base, "#12161b"),
                        (QtGui.QPalette.ColorRole.Text, "#e6e6e6"),
                        (QtGui.QPalette.ColorRole.Button, "#2a3038"),
                        (QtGui.QPalette.ColorRole.ButtonText, "#e6e6e6"),
                        (QtGui.QPalette.ColorRole.Highlight, "#4fc3f7"),
                        (QtGui.QPalette.ColorRole.ToolTipBase, "#2a3038"),
                        (QtGui.QPalette.ColorRole.ToolTipText, "#e6e6e6")):
        palette.setColor(role, QtGui.QColor(color))
    app.setPalette(palette)
    return app


def show(source, chapter, screenshot=None, until=None, actions=None):
    """Open the viewer. With ``screenshot``, render at sim time ``until`` and exit."""
    app = _app()
    win = MainWindow(source, chapter)
    if screenshot:
        win.timer.stop()
        for t_action, fn in sorted(actions or [], key=lambda a: a[0]):
            if t_action > source.t:
                win._run_guarded(source.advance, t_action - source.t)
            fn(win)
        if until is not None and until > source.t:
            win._run_guarded(source.advance, until - source.t)
        win.show()
        win._refresh()
        app.processEvents()
        QtCore.QTimer.singleShot(300, lambda: (win._refresh(), win.grab().save(str(screenshot)),
                                               app.quit()))
        app.exec()
        return win
    win.show()
    app.exec()
    return win
