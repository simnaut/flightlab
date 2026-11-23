"""Side view of the aircraft on the pitch stand, with wind tunnel air.

Drawing coordinates: meters, x forward (to the right), y up, origin at the CG
(the stand's pivot).
"""

import math

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

DEG = math.pi / 180.0

# Visual scales
ARROW_M_PER_MPS = 0.06      # control-arrow length per m/s of airspeed
PARTICLE_SPEED_SCALE = 0.12  # wind particles move at this fraction of real airspeed

# --- Aircraft outline (side view of a high-wing trainer) -------------------
FUSELAGE = [(2.7, 0.0), (2.55, 0.35), (1.6, 0.55), (0.95, 1.0), (-0.7, 1.0), (-1.3, 0.62),
            (-4.6, 0.38), (-4.95, 0.34), (-4.95, 0.06), (-4.5, -0.04), (-1.0, -0.45),
            (1.6, -0.5), (2.5, -0.3)]
WINDOW = [(1.5, 0.55), (0.95, 0.95), (0.25, 0.95), (0.25, 0.55)]
WING = [(0.75, 1.05), (0.55, 1.17), (0.0, 1.2), (-0.8, 1.1), (-0.8, 1.06), (0.0, 1.03)]
VTAIL = [(-3.5, 0.45), (-4.3, 1.65), (-4.95, 1.65), (-4.95, 0.34)]
HSTAB = [(-3.9, 0.3), (-4.0, 0.36), (-4.5, 0.34), (-4.5, 0.26), (-4.0, 0.25)]
HINGE = (-4.5, 0.30)
ELEVATOR = [(0.0, 0.05), (-0.55, 0.0), (0.0, -0.05)]       # relative to the hinge
STRUT = [(-0.2, -0.45), (-0.55, -1.15)]
NOSE_STRUT = [(2.0, -0.45), (2.0, -1.05)]
PROP = [(2.78, -0.95), (2.78, 0.95)]

COLORS = {
    "bg": "#0f1419",
    "airframe": "#d9dee5",
    "outline": "#5c6773",
    "window": "#6fa8dc",
    "elevator": "#ff9f43",
    "ghost": "#ffffff",
    "particles": (120, 180, 255, 110),
    "arrow": "#4fc3f7",
    "theta": "#ffd54f",
    "alpha": "#4dd0e1",
    "horizon": "#56606b",
    "stand": "#3d4650",
    "text": "#e6e6e6",
}


def _poly(points, color, outline=COLORS["outline"], parent=None):
    item = QtWidgets.QGraphicsPolygonItem(
        QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in points]), parent)
    item.setBrush(pg.mkBrush(color))
    item.setPen(pg.mkPen(outline, width=0))
    return item


def _line(points, color, width=2, parent=None, style=QtCore.Qt.PenStyle.SolidLine):
    path = QtGui.QPainterPath(QtCore.QPointF(*points[0]))
    for p in points[1:]:
        path.lineTo(QtCore.QPointF(*p))
    item = QtWidgets.QGraphicsPathItem(path, parent)
    pen = pg.mkPen(color, width=width, style=style)
    pen.setCosmetic(True)
    item.setPen(pen)
    return item


def _arc(radius, a0, a1, n=40):
    a = np.linspace(a0, a1, n)
    return radius * np.cos(a), radius * np.sin(a)


class SideView(pg.PlotWidget):
    """Aircraft on the pitch stand. Emits ``airDragged(airspeed, flow_rad)``."""

    airDragged = QtCore.pyqtSignal(float, float)

    def __init__(self, airspeed_range=(15.0, 70.0), flow_range_deg=15.0, parent=None):
        super().__init__(parent=parent, background=COLORS["bg"])
        self.airspeed_range = airspeed_range
        self.flow_max = flow_range_deg * DEG
        self.exaggerate = 1.0
        self.interactive_air = True

        p = self.getPlotItem()
        p.hideAxis("left")
        p.hideAxis("bottom")
        p.setMouseEnabled(False, False)
        p.hideButtons()
        p.setMenuEnabled(False)
        self.setAspectLocked(True)
        self.setRange(xRange=(-6.5, 9.0), yRange=(-5.4, 4.2), padding=0)

        # Ground and stand (fixed)
        self.addItem(_line([(-30, -5.0), (30, -5.0)], COLORS["stand"], 2))
        stand = _poly([(-0.12, 0), (0.12, 0), (0.25, -5.0), (-0.25, -5.0)], COLORS["stand"],
                      COLORS["stand"])
        stand.setZValue(-5)
        self.addItem(stand)
        self.addItem(_poly([(-1.6, -5.0), (1.6, -5.0), (1.2, -4.75), (-1.2, -4.75)],
                           COLORS["stand"], COLORS["stand"]))

        # Horizon line through the pivot
        self.addItem(_line([(-30, 0), (30, 0)], COLORS["horizon"], 1,
                           style=QtCore.Qt.PenStyle.DashLine))

        # Wind particles (one item, drawn as arrow segments)
        self.particles = pg.PlotDataItem(pen=pg.mkPen(COLORS["particles"], width=1.5),
                                         connect="pairs")
        self.particles.setZValue(-10)
        self.addItem(self.particles)
        rng = np.random.default_rng(3)
        self._lanes = np.linspace(-9, 9, 15)
        self._phase = rng.uniform(0, 1, size=(len(self._lanes), 6))
        self._air_s = 0.0           # distance the air has travelled (visual)
        self._last_t = None

        # Aircraft (a group rotated by theta)
        self.aircraft = QtWidgets.QGraphicsRectItem(0, 0, 0, 0)
        self.aircraft.setPen(pg.mkPen(None))
        self.addItem(self.aircraft)
        for pts, color in ((VTAIL, COLORS["airframe"]), (FUSELAGE, COLORS["airframe"]),
                           (WINDOW, COLORS["window"]), (WING, "#c3cad3"),
                           (HSTAB, "#c3cad3")):
            _poly(pts, color, parent=self.aircraft)
        _line(STRUT, COLORS["outline"], 2, parent=self.aircraft)
        _line(NOSE_STRUT, COLORS["outline"], 2, parent=self.aircraft)
        _line(PROP, "#8a949e", 2, parent=self.aircraft)
        for cx, cy, r in ((-0.55, -1.15, 0.22), (2.0, -1.05, 0.18)):
            wheel = QtWidgets.QGraphicsEllipseItem(cx - r, cy - r, 2 * r, 2 * r, self.aircraft)
            wheel.setBrush(pg.mkBrush("#2b2f33"))
            wheel.setPen(pg.mkPen(COLORS["outline"]))

        hinge = QtCore.QPointF(*HINGE)
        ghost_pts = [(HINGE[0] + x, HINGE[1] + y) for x, y in ELEVATOR]
        self.elevator_ghost = _poly(ghost_pts, (0, 0, 0, 0), parent=self.aircraft)
        ghost_pen = pg.mkPen(COLORS["ghost"], width=1, style=QtCore.Qt.PenStyle.DashLine)
        ghost_pen.setCosmetic(True)
        self.elevator_ghost.setPen(ghost_pen)
        self.elevator_ghost.setTransformOriginPoint(hinge)
        self.elevator = _poly(ghost_pts, COLORS["elevator"], COLORS["elevator"],
                              parent=self.aircraft)
        self.elevator.setTransformOriginPoint(hinge)

        # Pivot marker
        pivot = QtWidgets.QGraphicsEllipseItem(-0.14, -0.14, 0.28, 0.28)
        pivot.setBrush(pg.mkBrush("#2b2f33"))
        pivot.setPen(pg.mkPen(COLORS["text"], width=0))
        pivot.setZValue(5)
        self.addItem(pivot)

        # Body axis, relative-wind line and the theta / alpha arcs
        self.body_axis = pg.PlotDataItem(pen=pg.mkPen(COLORS["theta"], width=1,
                                                      style=QtCore.Qt.PenStyle.DotLine))
        self.wind_axis = pg.PlotDataItem(pen=pg.mkPen(COLORS["alpha"], width=1,
                                                      style=QtCore.Qt.PenStyle.DotLine))
        self.theta_arc = pg.PlotDataItem(pen=pg.mkPen(COLORS["theta"], width=2))
        self.alpha_arc = pg.PlotDataItem(pen=pg.mkPen(COLORS["alpha"], width=2))
        for item in (self.body_axis, self.wind_axis, self.theta_arc, self.alpha_arc):
            item.setZValue(6)
            self.addItem(item)
        self.theta_label = pg.TextItem(color=COLORS["theta"], anchor=(0, 0.5))
        self.alpha_label = pg.TextItem(color=COLORS["alpha"], anchor=(0, 0.5))
        for item in (self.theta_label, self.alpha_label):
            item.setZValue(7)
            self.addItem(item)

        # Air control arrow + draggable handle
        self.anchor = np.array([4.4, 0.0])
        self.arrow_line = pg.PlotDataItem(pen=pg.mkPen(COLORS["arrow"], width=3))
        self.arrow_head = pg.ArrowItem(angle=180, headLen=18, tipAngle=35,
                                       brush=COLORS["arrow"], pen=None)
        self.addItem(self.arrow_line)
        self.addItem(self.arrow_head)
        self.handle = pg.TargetItem(pos=(0, 0), size=16, symbol="o", movable=True,
                                    pen=pg.mkPen(COLORS["arrow"], width=2),
                                    brush=pg.mkBrush(COLORS["bg"]),
                                    hoverBrush=pg.mkBrush(COLORS["arrow"]))
        self.handle.setZValue(10)
        self.addItem(self.handle)
        self._updating_handle = False
        self.handle.sigPositionChanged.connect(self._on_handle_moved)
        self.handle.sigPositionChangeFinished.connect(self._on_handle_released)
        self.air_label = pg.TextItem(color=COLORS["arrow"], anchor=(0.5, 0))
        self.addItem(self.air_label)

        # Info text
        self.info = pg.TextItem(color=COLORS["text"], anchor=(0, 0),
                                fill=pg.mkBrush(15, 20, 25, 220))
        self.info.setZValue(20)
        self.info.setPos(-6.3, 4.0)
        self.addItem(self.info)
        self.banner = pg.TextItem(color="#ff6b6b", anchor=(1, 0))
        self.banner.setZValue(20)
        self.banner.setPos(8.8, 4.0)
        self.addItem(self.banner)

        self.set_air_target(55.0, 0.0)

    # ------------------------------------------------------------------ air
    def set_air_target(self, airspeed, flow):
        """Place the control arrow for a target air vector."""
        self._target = (airspeed, flow)
        length = airspeed * ARROW_M_PER_MPS
        tail = self.anchor + length * np.array([math.cos(flow), -math.sin(flow)])
        self._updating_handle = True
        self.handle.setPos(*tail)
        self._updating_handle = False
        self._draw_arrow(tail, airspeed, flow)

    def _draw_arrow(self, tail, airspeed, flow):
        self.arrow_line.setData([tail[0], self.anchor[0]], [tail[1], self.anchor[1]])
        self.arrow_head.setPos(*self.anchor)
        self.arrow_head.setStyle(angle=180 - flow / DEG)
        self.air_label.setPos(tail[0], min(tail[1], self.anchor[1]) - 0.3)
        self.air_label.setText(f"air {airspeed:.0f} m/s, {flow / DEG:+.1f}°")

    def _handle_to_air(self, pos):
        d = np.array([pos.x(), pos.y()]) - self.anchor
        airspeed = np.clip(np.hypot(*d) / ARROW_M_PER_MPS, *self.airspeed_range)
        flow = np.clip(math.atan2(-d[1], max(d[0], 1e-6)), -self.flow_max, self.flow_max)
        return float(airspeed), float(flow)

    def _on_handle_moved(self):
        if self._updating_handle:
            return
        airspeed, flow = self._handle_to_air(self.handle.pos())
        tail = np.array([self.handle.pos().x(), self.handle.pos().y()])
        self._draw_arrow(tail, airspeed, flow)

    def _on_handle_released(self):
        if self._updating_handle:
            return
        airspeed, flow = self._handle_to_air(self.handle.pos())
        self.set_air_target(airspeed, flow)       # snap to the clamped value
        self.airDragged.emit(airspeed, flow)

    def set_interactive_air(self, enabled):
        self.interactive_air = enabled
        self.handle.movable = enabled
        self.handle.setVisible(enabled)

    # ---------------------------------------------------------------- frame
    def _update_particles(self, t, airspeed, flow):
        if self._last_t is not None:
            self._air_s += max(0.0, t - self._last_t) * airspeed * PARTICLE_SPEED_SCALE
        if self._last_t is not None and t < self._last_t:
            self._air_s = 0.0
        self._last_t = t
        d = np.array([-math.cos(flow), math.sin(flow)])    # air moves this way
        n = np.array([math.sin(flow), math.cos(flow)])
        span = 24.0
        seg = 0.25 + 0.012 * airspeed
        head = 0.18
        xs, ys = [], []
        for i, lane in enumerate(self._lanes):
            for ph in self._phase[i]:
                s = ((ph * span + self._air_s) % span) - span / 2
                p0 = lane * n + s * d
                p1 = p0 + seg * d
                xs += [p0[0], p1[0]]
                ys += [p0[1], p1[1]]
                for side in (1, -1):
                    back = p1 - head * d + side * 0.5 * head * n
                    xs += [p1[0], back[0]]
                    ys += [p1[1], back[1]]
        self.particles.setData(xs, ys)

    def set_frame(self, t, theta, alpha, de, de_cmd, airspeed, flow, info_text="", banner=""):
        self.aircraft.setRotation(theta / DEG)
        self.elevator.setRotation(de * self.exaggerate / DEG)
        self.elevator_ghost.setRotation(de_cmd * self.exaggerate / DEG)
        self._update_particles(t, airspeed, flow)

        # Relative wind direction (where the aircraft "flies" relative to the air)
        wind_angle = theta - alpha
        r = 3.8
        self.body_axis.setData([0, 4.6 * math.cos(theta)], [0, 4.6 * math.sin(theta)])
        self.wind_axis.setData([0, 5.4 * math.cos(wind_angle)], [0, 5.4 * math.sin(wind_angle)])
        self.theta_arc.setData(*_arc(r, 0.0, theta))
        self.alpha_arc.setData(*_arc(r + 0.7, wind_angle, theta))
        # Labels sit beside the arcs: theta below, alpha above, so they never overlap
        low = min(0.0, theta, wind_angle)
        high = max(0.0, theta, wind_angle)
        self.theta_label.setPos(r * math.cos(low) - 0.4, r * math.sin(low) - 0.45)
        self.theta_label.setText(f"θ {theta / DEG:+.1f}°")
        self.alpha_label.setPos((r + 0.7) * math.cos(high) - 0.4,
                                (r + 0.7) * math.sin(high) + 0.45)
        self.alpha_label.setText(f"α {alpha / DEG:+.1f}°")
        self.info.setText(info_text)
        self.banner.setText(banner)
