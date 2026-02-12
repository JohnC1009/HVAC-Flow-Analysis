"""Left-side equipment toolbox with drag-and-drop buttons."""

from PyQt5.QtCore import Qt, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QFont, QColor, QPalette, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                              QFrame, QSizePolicy)


# Equipment types: (type_id, display_name, icon_char, color)
EQUIPMENT = [
    ("source",         "Air Source",       "S", "#43a047"),
    ("cooling_coil",   "Cooling Coil",     "C", "#1e88e5"),
    ("heating_coil",   "Heating Coil",     "H", "#e53935"),
    ("fan",            "Supply Fan",       "F", "#fb8c00"),
    ("enthalpy_wheel", "Enthalpy Wheel",   "E", "#8e24aa"),
    ("mixing_box",     "Mixing Box",       "M", "#00897b"),
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
    """Left panel containing draggable equipment buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("Equipment Toolbox")
        header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        for type_id, name, icon_char, color in EQUIPMENT:
            btn = EquipmentDragButton(type_id, name, icon_char, color)
            layout.addWidget(btn)

        layout.addStretch()

        hint = QLabel("Drag equipment onto\nthe canvas to add it.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)
