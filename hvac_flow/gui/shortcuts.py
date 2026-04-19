"""Keyboard shortcuts and actions for the main window."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QMessageBox


class KeyboardShortcuts:
    """Manages keyboard shortcuts and actions for the HVAC Flow Analysis GUI."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Set up all keyboard shortcuts."""
        # File operations
        self._create_action("New Project", "Ctrl+N", self.main_window.new_project)
        self._create_action("Open Project", "Ctrl+O", self.main_window.open_project)
        self._create_action("Save Project", "Ctrl+S", self.main_window.save_project)
        self._create_action("Save As", "Ctrl+Shift+S", self.main_window.save_project_as)
        self._create_action("Export Report", "Ctrl+E", self.main_window.export_report)
        
        # Edit operations
        self._create_action("Undo", "Ctrl+Z", self.main_window.undo)
        self._create_action("Redo", "Ctrl+Y", self.main_window.redo)
        self._create_action("Cut", "Ctrl+X", self.main_window.cut_selected)
        self._create_action("Copy", "Ctrl+C", self.main_window.copy_selected)
        self._create_action("Paste", "Ctrl+V", self.main_window.paste)
        self._create_action("Delete", "Delete", self.main_window.delete_selected)
        self._create_action("Select All", "Ctrl+A", self.main_window.select_all)
        
        # View operations
        self._create_action("Zoom In", "Ctrl++", self.main_window.zoom_in)
        self._create_action("Zoom Out", "Ctrl+-", self.main_window.zoom_out)
        self._create_action("Zoom Fit", "Ctrl+0", self.main_window.zoom_fit)
        self._create_action("Toggle Grid", "Ctrl+G", self.main_window.toggle_grid)
        self._create_action("Toggle Snap", "Ctrl+Shift+G", self.main_window.toggle_snap)
        
        # Solve operations
        self._create_action("Solve System", "F5", self.main_window.solve_system)
        self._create_action("Auto Solve", "Ctrl+F5", self.main_window.toggle_auto_solve)
        
        # Help
        self._create_action("Help", "F1", self.main_window.show_help)
        self._create_action("Shortcuts", "Ctrl+?", self.main_window.show_shortcuts)

    def _create_action(self, name: str, shortcut: str, callback):
        """Create a keyboard shortcut action."""
        action = QAction(name, self.main_window)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        self.main_window.addAction(action)
        return action


class UndoManager:
    """Manages undo/redo stack for the canvas."""

    def __init__(self, max_history: int = 50):
        self.history: list = []
        self.redo_stack: list = []
        self.max_history = max_history
        self.current_state: dict = None

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.history) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0

    def save_state(self, state: dict, description: str = "") -> None:
        """Save the current state to history."""
        if self.current_state is not None:
            self.history.append({
                'state': self.current_state,
                'description': description
            })
            # Trim history if too long
            if len(self.history) > self.max_history:
                self.history.pop(0)
        
        self.current_state = state.copy()
        # Clear redo stack when new action is performed
        self.redo_stack.clear()

    def undo(self) -> dict:
        """Undo the last action and return the previous state."""
        if not self.can_undo():
            return None
        
        # Save current state to redo stack
        if self.current_state is not None:
            self.redo_stack.append(self.current_state)
        
        # Pop and restore previous state
        entry = self.history.pop()
        self.current_state = entry['state']
        return self.current_state

    def redo(self) -> dict:
        """Redo the last undone action."""
        if not self.can_redo():
            return None
        
        # Save current state to history
        if self.current_state is not None:
            self.history.append({
                'state': self.current_state,
                'description': 'redo'
            })
        
        # Restore state from redo stack
        self.current_state = self.redo_stack.pop()
        return self.current_state

    def get_undo_description(self) -> str:
        """Get description of next undo action."""
        if not self.can_undo():
            return ""
        return self.history[-1].get('description', '')

    def get_redo_description(self) -> str:
        """Get description of next redo action."""
        if not self.can_redo():
            return ""
        return "Redo"
