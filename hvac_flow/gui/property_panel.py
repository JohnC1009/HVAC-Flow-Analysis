"""Right-side property editor for selected equipment nodes."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFormLayout,
                              QDoubleSpinBox, QComboBox, QGroupBox,
                              QScrollArea, QFrame)

from hvac_flow.engine.air_state import AirState


class PropertyPanel(QWidget):
    """Dynamically builds a form for the selected node's parameters and results."""

    parameter_changed = pyqtSignal(str, str, object)  # node_id, param, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self._current_node = None
        self._editors = {}  # param_name -> widget

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        self._title = QLabel("No Selection")
        self._title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._title.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(8)
        scroll.setWidget(self._inner)

    # ── Public API ───────────────────────────────────────────────────

    def show_node(self, node):
        """Rebuild the form for the given node."""
        self._clear()
        self._current_node = node
        self._title.setText(f"{node.DISPLAY_NAME}")

        # Parameters group
        param_group = QGroupBox("Parameters")
        param_form = QFormLayout()
        param_group.setLayout(param_form)

        definitions = {d["name"]: d for d in node.get_param_definitions()}

        for pname, pval in node.parameters.items():
            defn = definitions.get(pname, {})
            widget = self._make_editor(pname, pval, defn, node)
            if widget:
                label_text = pname.replace("_", " ").title()
                unit = defn.get("unit", "")
                if unit:
                    label_text += f" ({unit})"
                param_form.addRow(label_text, widget)
                self._editors[pname] = widget

        self._layout.addWidget(param_group)

        # Results group
        if node.results:
            res_group = QGroupBox("Results")
            res_form = QFormLayout()
            res_group.setLayout(res_form)

            for rname, rval in node.results.items():
                if isinstance(rval, AirState):
                    self._add_airstate_row(res_form, rname, rval)
                elif isinstance(rval, float):
                    lbl = QLabel(f"{rval:.4f}")
                    lbl.setFont(QFont("Consolas", 9))
                    res_form.addRow(rname.replace("_", " ").title(), lbl)

            self._layout.addWidget(res_group)

        self._layout.addStretch()

    def clear_selection(self):
        self._clear()
        self._title.setText("No Selection")

    # ── Internal ─────────────────────────────────────────────────────

    def _clear(self):
        self._current_node = None
        self._editors.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _make_editor(self, pname, pval, defn, node):
        ptype = defn.get("type", "")

        if ptype == "choice":
            cb = QComboBox()
            for ch in defn.get("choices", []):
                cb.addItem(ch)
            cb.setCurrentText(str(pval))
            cb.currentTextChanged.connect(
                lambda v, n=pname: self._on_param_changed(n, v)
            )
            return cb

        if isinstance(pval, float) or ptype == "float":
            sb = QDoubleSpinBox()
            sb.setDecimals(4)
            sb.setRange(defn.get("min", -1e9), defn.get("max", 1e9))
            if pval is not None:
                sb.setValue(pval)
            sb.valueChanged.connect(
                lambda v, n=pname: self._on_param_changed(n, v)
            )
            return sb

        if isinstance(pval, str):
            cb = QComboBox()
            cb.setEditable(True)
            cb.setCurrentText(pval)
            cb.currentTextChanged.connect(
                lambda v, n=pname: self._on_param_changed(n, v)
            )
            return cb

        return None

    def _on_param_changed(self, param_name, value):
        if self._current_node is None:
            return
        self._current_node.parameters[param_name] = value
        self.parameter_changed.emit(
            self._current_node.id, param_name, value
        )

    def _add_airstate_row(self, form, label, state: AirState):
        """Add a multi-line read-only display for an AirState."""
        text = (
            f"DB: {state.dry_bulb:.1f}°F\n"
            f"WB: {state.wet_bulb:.1f}°F\n"
            f"DP: {state.dew_point:.1f}°F\n"
            f"RH: {state.relative_humidity * 100:.1f}%\n"
            f"W:  {state.humidity_ratio:.5f} lb/lb\n"
            f"h:  {state.enthalpy:.2f} Btu/lb\n"
            f"v:  {state.specific_volume:.3f} ft³/lb"
        )
        lbl = QLabel(text)
        lbl.setFont(QFont("Consolas", 8))
        lbl.setStyleSheet("background: #f9f9f9; padding: 4px; border-radius: 3px;")
        form.addRow(label.replace("_", " ").title(), lbl)
