"""Embedded ASHRAE-style psychrometric chart using matplotlib."""

import numpy as np
import psychrolib

from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg,
                                                  NavigationToolbar2QT)
from matplotlib.figure import Figure

from PyQt5.QtWidgets import QWidget, QVBoxLayout

from hvac_flow.engine.constants import UnitSystem, STD_ATM_PRESSURE_IP


class PsychroChartWidget(QWidget):
    """Bottom panel: psychrometric chart with dynamic state-point overlay."""

    def __init__(self, unit_system=UnitSystem.IP,
                 pressure=STD_ATM_PRESSURE_IP, parent=None):
        super().__init__(parent)
        self.unit_system = unit_system
        self.pressure = pressure

        psychrolib.SetUnitSystem(psychrolib.IP if unit_system == UnitSystem.IP
                                 else psychrolib.SI)

        self.figure = Figure(figsize=(10, 4), dpi=100)
        self.figure.subplots_adjust(left=0.08, right=0.95, top=0.92, bottom=0.15)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self._state_artists = []
        self._line_artists = []
        self._ax = None
        self._draw_base_chart()

    # ── Base chart (static background) ───────────────────────────────

    def _draw_base_chart(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        self._ax = ax

        t_range = np.arange(20, 125, 0.5)

        # Saturation curve (RH = 100%)
        w_sat = []
        for t in t_range:
            try:
                w_sat.append(psychrolib.GetSatHumRatio(t, self.pressure))
            except Exception:
                w_sat.append(np.nan)
        ax.plot(t_range, w_sat, 'k-', linewidth=1.5, label='Saturation')

        # Constant RH lines
        for rh in np.arange(0.1, 1.0, 0.1):
            w_rh = []
            for t in t_range:
                try:
                    w_rh.append(
                        psychrolib.GetHumRatioFromRelHum(t, rh, self.pressure)
                    )
                except Exception:
                    w_rh.append(np.nan)
            ax.plot(t_range, w_rh, 'k-', linewidth=0.3, alpha=0.4)
            # Label at right edge
            try:
                wl = psychrolib.GetHumRatioFromRelHum(120, rh, self.pressure)
                ax.text(121, wl, f"{int(rh*100)}%", fontsize=6,
                        va='center', color='#666')
            except Exception:
                pass

        # Constant wet-bulb lines
        for twb in np.arange(35, 90, 5):
            t_wb = []
            w_wb = []
            for t in t_range:
                if t >= twb:
                    try:
                        w = psychrolib.GetHumRatioFromTWetBulb(
                            t, twb, self.pressure
                        )
                        if w >= 0:
                            t_wb.append(t)
                            w_wb.append(w)
                    except Exception:
                        pass
            if t_wb:
                ax.plot(t_wb, w_wb, color='#2196f3', linewidth=0.25,
                        alpha=0.4)

        ax.set_xlim(20, 125)
        ax.set_ylim(0, 0.030)
        ax.set_xlabel("Dry-Bulb Temperature (°F)", fontsize=9)
        ax.set_ylabel("Humidity Ratio (lb_w / lb_da)", fontsize=9)
        ax.set_title("Psychrometric Chart", fontsize=10, fontweight='bold')
        ax.grid(True, alpha=0.15)
        ax.tick_params(labelsize=8)

        self.canvas.draw()

    # ── Plot state points ────────────────────────────────────────────

    def plot_states(self, states, process_lines=True):
        """Overlay state points (and optional process lines) on the chart.

        Args:
            states: list of AirState objects.
            process_lines: if True, draw lines connecting sequential states.
        """
        ax = self._ax
        if ax is None:
            return

        # Clear previous overlays
        for a in self._state_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._state_artists.clear()
        for a in self._line_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._line_artists.clear()

        prev = None
        for state in states:
            dot = ax.plot(state.dry_bulb, state.humidity_ratio,
                          'ro', markersize=7, zorder=10,
                          markeredgecolor='darkred', markeredgewidth=0.8)[0]
            self._state_artists.append(dot)

            if state.label:
                txt = ax.annotate(
                    state.label,
                    (state.dry_bulb, state.humidity_ratio),
                    textcoords="offset points", xytext=(8, 8),
                    fontsize=7, color='#333',
                    arrowprops=dict(arrowstyle='->', color='#999',
                                    lw=0.5),
                )
                self._state_artists.append(txt)

            if process_lines and prev is not None:
                line = ax.plot(
                    [prev.dry_bulb, state.dry_bulb],
                    [prev.humidity_ratio, state.humidity_ratio],
                    'r-', linewidth=1.2, alpha=0.6, zorder=5
                )[0]
                self._line_artists.append(line)

            prev = state

        self.canvas.draw()
