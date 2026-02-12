"""Visual representation of an equipment node on the flow diagram canvas."""

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QLinearGradient)
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsTextItem

from hvac_flow.gui.canvas.port_item import PortItem

# Node colour palette by equipment type
NODE_COLORS = {
    "source":              ("#e8f5e9", "#43a047"),
    "cooling_coil":        ("#e3f2fd", "#1e88e5"),
    "heating_coil":        ("#fbe9e7", "#e53935"),
    "fan":                 ("#fff3e0", "#fb8c00"),
    "enthalpy_wheel":      ("#f3e5f5", "#8e24aa"),
    "mixing_box":          ("#e0f7fa", "#00897b"),
    "zone_process":        ("#efebe9", "#6d4c41"),
    "duct_split":          ("#e0f2f1", "#00796b"),
    "steam_humidifier":    ("#e1f5fe", "#0277bd"),
    "adiabatic_humidifier":("#e1f5fe", "#0288d1"),
    "sensible_hr":         ("#f3e5f5", "#7b1fa2"),
    "runaround_loop":      ("#ede7f6", "#6a1b9a"),
    "indirect_evap_cooler":("#e0f7fa", "#0097a7"),
    "desiccant_wheel":     ("#ede7f6", "#5e35b1"),
    "return_fan":          ("#fff3e0", "#ef6c00"),
    "air_sink":            ("#eceff1", "#78909c"),
}

WIDTH = 180
HEADER_H = 28
PORT_ROW_H = 22
BODY_PAD = 6
CORNER_R = 8


class NodeItem(QGraphicsItem):
    """Rounded-rectangle equipment node with header, ports, and status text."""

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptDrops(False)
        self.setZValue(1)

        self._port_items: dict = {}
        self._status_lines: list = []
        self._height = HEADER_H + BODY_PAD
        self._create_ports()
        self._update_status()

    # ── Port layout ──────────────────────────────────────────────────

    def _create_ports(self):
        inlets = [p for p in self.node.ports.values() if p.direction == "inlet"]
        outlets = [p for p in self.node.ports.values() if p.direction == "outlet"]

        max_ports = max(len(inlets), len(outlets), 1)
        body_h = max_ports * PORT_ROW_H + BODY_PAD * 2
        self._height = HEADER_H + body_h

        for i, port in enumerate(inlets):
            pi = PortItem(port, self)
            y = HEADER_H + BODY_PAD + i * PORT_ROW_H + PORT_ROW_H / 2
            pi.setPos(0, y)
            self._port_items[port.name] = pi

        for i, port in enumerate(outlets):
            pi = PortItem(port, self)
            y = HEADER_H + BODY_PAD + i * PORT_ROW_H + PORT_ROW_H / 2
            pi.setPos(WIDTH, y)
            self._port_items[port.name] = pi

    def get_port_item(self, port_name: str):
        return self._port_items.get(port_name)

    # ── Status display ───────────────────────────────────────────────

    def _update_status(self):
        self._status_lines.clear()
        for port in self.node.outlet_ports:
            if port.air_state is not None:
                s = port.air_state
                self._status_lines.append(
                    f"DB:{s.dry_bulb:.1f}°F  RH:{s.relative_humidity*100:.0f}%"
                )
        results = self.node.results
        if "total_load_tons" in results:
            self._status_lines.append(
                f"Load: {results['total_load_tons']:.1f} tons"
            )
        if "sensible_load_btuh" in results and "total_load_btuh" not in results:
            self._status_lines.append(
                f"Heat: {results['sensible_load_btuh']/1000:.1f} kBtu/h"
            )
        if "temp_rise_f" in results:
            self._status_lines.append(
                f"ΔT: +{results['temp_rise_f']:.1f}°F"
            )

        # Resize body to fit status lines
        inlets = [p for p in self.node.ports.values() if p.direction == "inlet"]
        outlets = [p for p in self.node.ports.values() if p.direction == "outlet"]
        max_ports = max(len(inlets), len(outlets), 1)
        port_h = max_ports * PORT_ROW_H + BODY_PAD * 2
        status_h = len(self._status_lines) * 16 + BODY_PAD if self._status_lines else 0
        self._height = HEADER_H + max(port_h, status_h + PORT_ROW_H)

    def refresh(self):
        """Call after solver to update visual state."""
        self.prepareGeometryChange()
        self._update_status()
        self.update()

    # ── Qt overrides ─────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, WIDTH + 4, self._height + 4)

    def paint(self, painter: QPainter, option, widget):
        bg, accent = NODE_COLORS.get(self.node.NODE_TYPE, ("#f5f5f5", "#757575"))

        # Body background
        rect = QRectF(0, 0, WIDTH, self._height)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(bg)))
        border_color = QColor(accent) if not self.isSelected() else QColor("#ff9800")
        painter.setPen(QPen(border_color, 2.5 if self.isSelected() else 1.5))
        painter.drawRoundedRect(rect, CORNER_R, CORNER_R)

        # Header bar
        header_rect = QRectF(0, 0, WIDTH, HEADER_H)
        grad = QLinearGradient(0, 0, 0, HEADER_H)
        grad.setColorAt(0, QColor(accent))
        grad.setColorAt(1, QColor(accent).darker(120))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(header_rect, CORNER_R, CORNER_R)
        # Square off bottom corners of header
        painter.drawRect(QRectF(0, HEADER_H - CORNER_R, WIDTH, CORNER_R))

        # Header text
        painter.setPen(QPen(QColor("white")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(header_rect.adjusted(8, 0, -8, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, self.node.name)

        # Port labels
        painter.setPen(QPen(QColor("#333")))
        painter.setFont(QFont("Segoe UI", 7))
        for pname, pi in self._port_items.items():
            y = pi.y()
            if pi.port.direction == "inlet":
                painter.drawText(QRectF(12, y - 8, WIDTH / 2 - 12, 16),
                                 Qt.AlignVCenter | Qt.AlignLeft, pname)
            else:
                painter.drawText(QRectF(WIDTH / 2, y - 8, WIDTH / 2 - 12, 16),
                                 Qt.AlignVCenter | Qt.AlignRight, pname)

        # Status text
        if self._status_lines:
            painter.setFont(QFont("Consolas", 7))
            painter.setPen(QPen(QColor("#555")))
            base_y = HEADER_H + max(
                len(self.node.inlet_ports), len(self.node.outlet_ports), 1
            ) * PORT_ROW_H + BODY_PAD
            for i, line in enumerate(self._status_lines):
                painter.drawText(QRectF(8, base_y + i * 16, WIDTH - 16, 16),
                                 Qt.AlignVCenter | Qt.AlignLeft, line)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.node.position = (self.pos().x(), self.pos().y())
            # Update any attached connectors
            scene = self.scene()
            if scene and hasattr(scene, 'update_connectors_for_node'):
                scene.update_connectors_for_node(self.node.id)
        return super().itemChange(change, value)
