"""Left-side equipment toolbox with drag-and-drop buttons."""

from PyQt5.QtCore import Qt, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QFont, QColor, QPalette, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                              QFrame, QSizePolicy, QScrollArea)


# Equipment types: (type_id, display_name, icon_char, color, category)
EQUIPMENT = [
    # — Sources & Sinks —
    ("source",              "Air Source",               "S",  "#43a047",  "Sources / Sinks"),
    ("air_sink",            "Air Sink / Exhaust",       "X",  "#78909c",  "Sources / Sinks"),
    # — Coils —
    ("cooling_coil",        "Cooling Coil",             "C",  "#1e88e5",  "Coils"),
    ("heating_coil",        "Heating Coil",             "H",  "#e53935",  "Coils"),
    # — Fans —
    ("fan",                 "Supply Fan",               "F",  "#fb8c00",  "Fans"),
    ("return_fan",          "Return / Exhaust Fan",     "R",  "#ef6c00",  "Fans"),
    # — Heat Recovery —
    ("enthalpy_wheel",      "Enthalpy Wheel",           "E",  "#8e24aa",  "Heat Recovery"),
    ("sensible_hr",         "Sensible Heat Recovery",   "P",  "#7b1fa2",  "Heat Recovery"),
    ("runaround_loop",      "Runaround Loop",           "L",  "#6a1b9a",  "Heat Recovery"),
    # — Mixing & Splitting —
    ("mixing_box",          "Mixing Box",               "M",  "#00897b",  "Mixing / Splitting"),
    ("duct_split",          "Duct Split",               "Y",  "#00796b",  "Mixing / Splitting"),
    # — Humidification —
    ("steam_humidifier",    "Steam Humidifier",         "W",  "#0277bd",  "Humidification"),
    ("adiabatic_humidifier","Evap Cooler / Humidifier", "A",  "#0288d1",  "Humidification"),
    # — Evaporative Cooling —
    ("indirect_evap_cooler","Indirect Evap Cooler",     "I",  "#0097a7",  "Evaporative Cooling"),
    # — Desiccant —
    ("desiccant_wheel",     "Desiccant Wheel",          "D",  "#5e35b1",  "Desiccant"),
    # — Zone —
    ("zone_process",        "Zone Process",             "Z",  "#6d4c41",  "Zone"),
]


def _make_icon(char: str, color: str, size: int = 32) -> QIcon:
    """Create a simple coloured-circle icon with a character label."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", int(size * 0.38), QFont.Bold))
    painter.drawText(pm.rect(), Qt.AlignCenter, char)
    painter.end()
    return QIcon(pm)


class EquipmentDragButton(QPushButton):
    """A button that initiates a drag carrying the equipment type id."""

    def __init__(self, type_id: str, display_name: str, icon_char: str,
                 color: str, parent=None):
        super().__init__(parent)
        self.type_id = type_id
        self.setText(f"  {display_name}")
        self.setIcon(_make_icon(icon_char, color))
        self.setIconSize(self.iconSize())
        self.setFixedHeight(38)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 4px 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background: #fafafa;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #e3f2fd;
                border-color: #90caf9;
            }
        """)
        self._drag_start: QPoint = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_start is not None
                and (event.pos() - self._drag_start).manhattanLength() > 10):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.type_id)
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)
            self._drag_start = None
        super().mouseMoveEvent(event)


class ToolboxPanel(QWidget):
    """Left panel containing draggable equipment buttons, grouped by category."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("Equipment Toolbox")
        header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        last_cat = None
        for type_id, name, icon_char, color, category in EQUIPMENT:
            if category != last_cat:
                cat_label = QLabel(category)
                cat_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
                cat_label.setStyleSheet("color: #666; margin-top: 6px;")
                layout.addWidget(cat_label)
                last_cat = category
            btn = EquipmentDragButton(type_id, name, icon_char, color)
            layout.addWidget(btn)

        layout.addStretch()

        hint = QLabel("Drag equipment onto\nthe canvas to add it.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        scroll.setWidget(inner)
