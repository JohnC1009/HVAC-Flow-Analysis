"""QGraphicsScene for the flow diagram — handles drops, connector wiring, selection."""

from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtWidgets import (QGraphicsScene, QGraphicsSceneMouseEvent,
                              QGraphicsSceneDragDropEvent)

from hvac_flow.models import NodeFactory
from hvac_flow.models.connector import Connector
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.gui.canvas.node_item import NodeItem
from hvac_flow.gui.canvas.port_item import PortItem
from hvac_flow.gui.canvas.connector_item import ConnectorItem, TempConnectorItem


class FlowScene(QGraphicsScene):
    """Scene managing equipment nodes and connector wiring."""

    node_selected = pyqtSignal(object)   # emits BaseNode
    node_deselected = pyqtSignal()

    def __init__(self, graph: FlowGraph, parent=None):
        super().__init__(parent)
        self.graph = graph
        self._node_items: dict = {}        # node_id -> NodeItem
        self._connector_items: dict = {}   # connector_id -> ConnectorItem

        self._dragging_connector = False
        self._temp_connector: TempConnectorItem = None
        self._drag_source_port: PortItem = None

        self.setSceneRect(-2000, -2000, 6000, 6000)
        self.selectionChanged.connect(self._on_selection_changed)

    # ── Drop from toolbox ────────────────────────────────────────────

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        event.acceptProposedAction()

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        node_type = event.mimeData().text()
        try:
            node = NodeFactory.create(node_type)
        except ValueError:
            return

        pos = event.scenePos()
        node.position = (pos.x(), pos.y())
        self.graph.add_node(node)

        item = NodeItem(node)
        item.setPos(pos)
        self.addItem(item)
        self._node_items[node.id] = item

    # ── Connector wiring via port drag ───────────────────────────────

    def start_connector_drag(self, port_item: PortItem):
        """Begin drawing a temporary connector from an outlet port."""
        self._dragging_connector = True
        self._drag_source_port = port_item
        start = port_item.get_scene_center()
        self._temp_connector = TempConnectorItem(start)
        self.addItem(self._temp_connector)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_connector and self._temp_connector:
            self._temp_connector.update_end(event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_connector:
            self._finish_connector_drag(event.scenePos())
        super().mouseReleaseEvent(event)

    def _finish_connector_drag(self, end_pos: QPointF):
        # Clean up temp line
        if self._temp_connector:
            self.removeItem(self._temp_connector)
            self._temp_connector = None
        self._dragging_connector = False

        # Find target port under the cursor
        target_port = None
        for item in self.items(end_pos):
            if isinstance(item, PortItem) and item.port.direction == "inlet":
                target_port = item
                break

        if target_port is None or target_port == self._drag_source_port:
            self._drag_source_port = None
            return

        # Check not already connected
        if target_port.port.connected_to is not None:
            self._drag_source_port = None
            return

        # Create the model connector
        src_node = self._drag_source_port.parent_node_item.node
        tgt_node = target_port.parent_node_item.node
        connector = Connector(
            source_node_id=src_node.id,
            source_port_name=self._drag_source_port.port.name,
            target_node_id=tgt_node.id,
            target_port_name=target_port.port.name,
        )
        self.graph.add_connector(connector)

        # Create visual connector
        ci = ConnectorItem(connector, self._drag_source_port, target_port)
        self.addItem(ci)
        self._connector_items[connector.id] = ci

        self._drag_source_port = None

    # ── Connector path updates when nodes move ───────────────────────

    def update_connectors_for_node(self, node_id: str):
        for c in self.graph.connectors.values():
            if c.source_node_id == node_id or c.target_node_id == node_id:
                ci = self._connector_items.get(c.id)
                if ci:
                    ci.update_path()

    # ── Node display refresh after solve ─────────────────────────────

    def update_node_displays(self):
        for ni in self._node_items.values():
            ni.refresh()

    # ── Selection handling ───────────────────────────────────────────

    def _on_selection_changed(self):
        selected = self.selectedItems()
        node_items = [i for i in selected if isinstance(i, NodeItem)]
        if node_items:
            self.node_selected.emit(node_items[0].node)
        else:
            self.node_deselected.emit()

    # ── Deletion ─────────────────────────────────────────────────────

    def delete_selected(self):
        """Remove selected nodes and connectors from both scene and graph."""
        for item in list(self.selectedItems()):
            if isinstance(item, ConnectorItem):
                self.graph.remove_connector(item.connector.id)
                self._connector_items.pop(item.connector.id, None)
                self.removeItem(item)
            elif isinstance(item, NodeItem):
                # Remove attached connectors first
                attached = [
                    cid for cid, c in self.graph.connectors.items()
                    if c.source_node_id == item.node.id
                    or c.target_node_id == item.node.id
                ]
                for cid in attached:
                    ci = self._connector_items.pop(cid, None)
                    if ci:
                        self.removeItem(ci)
                self.graph.remove_node(item.node.id)
                self._node_items.pop(item.node.id, None)
                self.removeItem(item)

    # ── Rebuild from graph (after load) ──────────────────────────────

    def rebuild_from_graph(self):
        """Clear the scene and recreate all items from self.graph."""
        self.clear()
        self._node_items.clear()
        self._connector_items.clear()

        for node in self.graph.nodes.values():
            item = NodeItem(node)
            item.setPos(node.position[0], node.position[1])
            self.addItem(item)
            self._node_items[node.id] = item

        for c in self.graph.connectors.values():
            src_ni = self._node_items.get(c.source_node_id)
            tgt_ni = self._node_items.get(c.target_node_id)
            if src_ni and tgt_ni:
                sp = src_ni.get_port_item(c.source_port_name)
                tp = tgt_ni.get_port_item(c.target_port_name)
                if sp and tp:
                    ci = ConnectorItem(c, sp, tp)
                    self.addItem(ci)
                    self._connector_items[c.id] = ci
