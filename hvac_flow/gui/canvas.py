"""Enhanced canvas with zoom, pan, grid, and visual feedback."""

from PyQt5.QtCore import Qt, QRectF, QLineF, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QFont, QTransform
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem
)


class GridItem(QGraphicsItem):
    """Custom grid item for the canvas background."""

    def __init__(self, grid_size: int = 20, parent=None):
        super().__init__(parent)
        self.grid_size = grid_size
        self.pen = QPen(QColor(200, 200, 200))
        self.pen.setWidth(1)
        self.visible = True
        self.snap_enabled = True

    def boundingRect(self):
        return QRectF(-10000, -10000, 20000, 20000)

    def paint(self, painter: QPainter, option, widget):
        if not self.visible:
            return

        # Get the visible area
        rect = painter.viewport()
        transform = painter.transform()
        
        # Calculate grid bounds
        left = int(transform.dx() / transform.m11()) - 100
        top = int(transform.dy() / transform.m11()) - 100
        right = left + int(rect.width() / transform.m11()) + 200
        bottom = top + int(rect.height() / transform.m11()) + 200

        # Snap to grid
        left = (left // self.grid_size) * self.grid_size
        top = (top // self.grid_size) * self.grid_size

        painter.setPen(self.pen)

        # Draw vertical lines
        for x in range(left, right, self.grid_size):
            painter.drawLine(QLineF(x, top, x, bottom))

        # Draw horizontal lines
        for y in range(top, bottom, self.grid_size):
            painter.drawLine(QLineF(left, y, right, y))

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        """Snap a position to the nearest grid point."""
        if not self.snap_enabled:
            return pos
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)


class FlowGraphScene(QGraphicsScene):
    """Scene for the flow graph with enhanced features."""

    node_selected = pyqtSignal(object)
    node_moved = pyqtSignal(object, QPointF)
    connection_requested = pyqtSignal(object, str, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = GridItem()
        self.addItem(self.grid)
        
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.setBackgroundBrush(QBrush(QColor(245, 245, 245)))
        
        self._nodes = {}
        self._connections = []
        self._selected_node = None

    def add_node_item(self, node, x: float, y: float):
        """Add a node to the scene."""
        from hvac_flow.gui.node_item import NodeItem
        
        item = NodeItem(node)
        item.setPos(x, y)
        item.setFlag(QGraphicsItem.ItemIsMovable)
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        item.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        self.addItem(item)
        self._nodes[node.id] = item
        
        # Connect signals
        item.position_changed.connect(self._on_node_moved)
        item.selection_changed.connect(self._on_node_selected)
        
        return item

    def remove_node_item(self, node_id: str):
        """Remove a node from the scene."""
        if node_id in self._nodes:
            item = self._nodes[node_id]
            self.removeItem(item)
            del self._nodes[node_id]

    def _on_node_moved(self, item, new_pos: QPointF):
        """Handle node movement."""
        # Snap to grid
        snapped_pos = self.grid.snap_to_grid(new_pos)
        if snapped_pos != new_pos:
            item.setPos(snapped_pos)
        
        self.node_moved.emit(item.node, snapped_pos)

    def _on_node_selected(self, item, selected: bool):
        """Handle node selection."""
        if selected:
            self._selected_node = item.node
            self.node_selected.emit(item.node)
        else:
            if self._selected_node == item.node:
                self._selected_node = None

    def toggle_grid(self):
        """Toggle grid visibility."""
        self.grid.visible = not self.grid.visible
        self.update()

    def toggle_snap(self):
        """Toggle grid snapping."""
        self.grid.snap_enabled = not self.grid.snap_enabled

    def clear_selection(self):
        """Clear all selections."""
        for item in self.selectedItems():
            item.setSelected(False)
        self._selected_node = None


class EnhancedCanvas(QGraphicsView):
    """Enhanced canvas with zoom, pan, and visual feedback."""

    zoom_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Setup scene
        self.scene = FlowGraphScene(self)
        self.setScene(self.scene)
        
        # Rendering options
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # Zoom settings
        self._zoom_factor = 1.15
        self._current_zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        
        # Pan settings
        self._panning = False
        self._last_pan_point = None
        
        # Visual feedback
        self._show_flow_animation = False
        self._animation_timer = None
        
        # Set initial transform
        self.resetTransform()

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming."""
        # Get the position before zoom
        old_pos = self.mapToScene(event.pos())
        
        # Calculate zoom
        zoom_in = event.angleDelta().y() > 0
        if zoom_in:
            zoom_factor = self._zoom_factor
        else:
            zoom_factor = 1.0 / self._zoom_factor
        
        # Apply zoom limits
        new_zoom = self._current_zoom * zoom_factor
        if new_zoom < self._min_zoom or new_zoom > self._max_zoom:
            return
        
        # Apply zoom
        self.scale(zoom_factor, zoom_factor)
        self._current_zoom = new_zoom
        
        # Adjust to keep mouse position stable
        new_pos = self.mapToScene(event.pos())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
        self.zoom_changed.emit(self._current_zoom)

    def mousePressEvent(self, event):
        """Handle mouse press for panning."""
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for panning."""
        if self._panning:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            
            # Pan the view
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release for panning."""
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)

    def zoom_in(self):
        """Zoom in by one step."""
        self._apply_zoom(self._zoom_factor)

    def zoom_out(self):
        """Zoom out by one step."""
        self._apply_zoom(1.0 / self._zoom_factor)

    def zoom_fit(self):
        """Zoom to fit all items."""
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        # Update current zoom level
        transform = self.transform()
        self._current_zoom = transform.m11()
        self.zoom_changed.emit(self._current_zoom)

    def zoom_reset(self):
        """Reset zoom to 100%."""
        self.resetTransform()
        self._current_zoom = 1.0
        self.zoom_changed.emit(self._current_zoom)

    def _apply_zoom(self, factor: float):
        """Apply zoom factor with limits."""
        new_zoom = self._current_zoom * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self.scale(factor, factor)
            self._current_zoom = new_zoom
            self.zoom_changed.emit(self._current_zoom)

    def get_zoom_percent(self) -> int:
        """Get current zoom as percentage."""
        return int(self._current_zoom * 100)

    def toggle_grid(self):
        """Toggle grid visibility."""
        self.scene.toggle_grid()

    def toggle_snap(self):
        """Toggle grid snapping."""
        self.scene.toggle_snap()

    def enable_flow_animation(self, enabled: bool = True):
        """Enable/disable flow animation."""
        self._show_flow_animation = enabled
        # TODO: Implement actual animation
