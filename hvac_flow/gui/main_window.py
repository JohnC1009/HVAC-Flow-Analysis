"""Main application window — assembles toolbox, canvas, property panel, and chart."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtWidgets import (QMainWindow, QSplitter, QToolBar, QAction,
                              QMessageBox, QFileDialog, QStatusBar, QLabel)

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.engine.constants import UnitSystem
from hvac_flow.models.project import Project
from hvac_flow.solver.flow_solver import FlowSolver
from hvac_flow.gui.toolbox_panel import ToolboxPanel
from hvac_flow.gui.canvas.flow_scene import FlowScene
from hvac_flow.gui.canvas.flow_view import FlowView
from hvac_flow.gui.property_panel import PropertyPanel
from hvac_flow.gui.psychro_chart_widget import PsychroChartWidget
from hvac_flow.serialization.project_io import ProjectIO


class MainWindow(QMainWindow):
    """
    Layout:
    ┌─────────────────────────────────────────────────────────┐
    │  Toolbar: [Run] [Save] [Open] [Clear] [Delete]         │
    ├──────────┬────────────────────────────┬─────────────────┤
    │ Toolbox  │     Flow Diagram Canvas    │  Property       │
    │  Panel   │     (drag & drop nodes,    │  Editor         │
    │          │      wire connectors)      │  Panel          │
    ├──────────┴────────────────────────────┴─────────────────┤
    │              Psychrometric Chart (matplotlib)           │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        self.project = Project()
        self.calc = PsychroCalc(self.project.unit_system, self.project.pressure)
        self.solver = FlowSolver(self.project.graph, self.calc)

        self._setup_ui()
        self._create_toolbar()
        self._create_statusbar()
        self._connect_signals()

    # ── UI setup ─────────────────────────────────────────────────────

    def _setup_ui(self):
        # Panels
        self.toolbox = ToolboxPanel()
        self.canvas_scene = FlowScene(self.project.graph)
        self.canvas_view = FlowView()
        self.canvas_view.setScene(self.canvas_scene)
        self.property_panel = PropertyPanel()
        self.psychro_chart = PsychroChartWidget(
            self.project.unit_system, self.project.pressure
        )

        # Horizontal splitter: toolbox | canvas | property editor
        h_split = QSplitter(Qt.Horizontal)
        h_split.addWidget(self.toolbox)
        h_split.addWidget(self.canvas_view)
        h_split.addWidget(self.property_panel)
        h_split.setSizes([200, 800, 280])
        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)
        h_split.setStretchFactor(2, 0)

        # Vertical splitter: top row | psychrometric chart
        v_split = QSplitter(Qt.Vertical)
        v_split.addWidget(h_split)
        v_split.addWidget(self.psychro_chart)
        v_split.setSizes([550, 300])
        v_split.setStretchFactor(0, 1)
        v_split.setStretchFactor(1, 0)

        self.setCentralWidget(v_split)

    def _create_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar { spacing: 6px; padding: 4px; }")
        self.addToolBar(toolbar)

        run_act = QAction("Solve", self)
        run_act.setShortcut(QKeySequence("F5"))
        run_act.setToolTip("Run the flow solver (F5)")
        run_act.triggered.connect(self._on_solve)
        toolbar.addAction(run_act)

        toolbar.addSeparator()

        save_act = QAction("Save", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self._on_save)
        toolbar.addAction(save_act)

        open_act = QAction("Open", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self._on_open)
        toolbar.addAction(open_act)

        toolbar.addSeparator()

        del_act = QAction("Delete Selected", self)
        del_act.setShortcut(QKeySequence.Delete)
        del_act.triggered.connect(self._on_delete)
        toolbar.addAction(del_act)

        clear_act = QAction("Clear All", self)
        clear_act.triggered.connect(self._on_clear)
        toolbar.addAction(clear_act)

    def _create_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("Ready")
        self._statusbar.addWidget(self._status_label)

    def _connect_signals(self):
        self.canvas_scene.node_selected.connect(self.property_panel.show_node)
        self.canvas_scene.node_deselected.connect(
            self.property_panel.clear_selection
        )

    # ── Actions ──────────────────────────────────────────────────────

    def _on_solve(self):
        success = self.solver.solve()
        if success:
            self.canvas_scene.update_node_displays()
            self.psychro_chart.plot_states(self.solver.all_states)
            # Refresh property panel if something is selected
            selected = self.canvas_scene.selectedItems()
            from hvac_flow.gui.canvas.node_item import NodeItem
            node_items = [i for i in selected if isinstance(i, NodeItem)]
            if node_items:
                self.property_panel.show_node(node_items[0].node)

            # Show capacity warnings if any
            n_states = len(self.solver.all_states)
            n_warnings = len(self.solver.warnings)
            suffix = f" | {n_warnings} warning(s)" if n_warnings else ""
            self._status_label.setText(f"Solved — {n_states} state points{suffix}")
            if self.solver.warnings:
                QMessageBox.information(
                    self, "Solver Warnings — Boundary Conditions Exceeded",
                    "The system solved successfully, but the following "
                    "boundary conditions were exceeded:\n\n"
                    + "\n".join(self.solver.warnings)
                )
        else:
            QMessageBox.warning(
                self, "Solver Errors",
                "\n".join(self.solver.errors)
            )
            self._status_label.setText("Solve failed")

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "HVAC Project (*.hvac);;All Files (*)"
        )
        if path:
            try:
                ProjectIO.save(self.project, path)
                self._status_label.setText(f"Saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "HVAC Project (*.hvac);;All Files (*)"
        )
        if path:
            try:
                self.project = ProjectIO.load(path)
                self.calc = PsychroCalc(self.project.unit_system,
                                        self.project.pressure)
                self.solver = FlowSolver(self.project.graph, self.calc)
                self.canvas_scene.graph = self.project.graph
                self.canvas_scene.rebuild_from_graph()
                self.property_panel.clear_selection()
                self._status_label.setText(f"Loaded: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Open Error", str(e))

    def _on_delete(self):
        self.canvas_scene.delete_selected()
        self.property_panel.clear_selection()

    def _on_clear(self):
        reply = QMessageBox.question(
            self, "Clear All",
            "Remove all nodes and connectors from the canvas?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.project.graph.nodes.clear()
            self.project.graph.connectors.clear()
            self.canvas_scene.rebuild_from_graph()
            self.property_panel.clear_selection()
            self._status_label.setText("Canvas cleared")
