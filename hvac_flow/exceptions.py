"""Custom exceptions for HVAC Flow Analysis."""


class HVACFlowError(Exception):
    """Base exception for all HVAC Flow Analysis errors."""
    pass


class ValidationError(HVACFlowError):
    """Raised when system configuration validation fails."""
    
    def __init__(self, message: str, node_id: str = None, node_name: str = None):
        super().__init__(message)
        self.node_id = node_id
        self.node_name = node_name


class SolverError(HVACFlowError):
    """Raised when the flow solver encounters an error."""
    
    def __init__(self, message: str, node_id: str = None, node_name: str = None):
        super().__init__(message)
        self.node_id = node_id
        self.node_name = node_name


class GraphError(HVACFlowError):
    """Raised when there's an issue with the flow graph structure."""
    pass


class CyclicGraphError(GraphError):
    """Raised when the flow graph contains a cycle."""
    pass


class DisconnectedGraphError(GraphError):
    """Raised when required nodes are disconnected."""
    pass


class NodeError(HVACFlowError):
    """Raised when a node computation fails."""
    
    def __init__(self, message: str, node_id: str = None, node_name: str = None):
        super().__init__(message)
        self.node_id = node_id
        self.node_name = node_name


class ParameterError(NodeError):
    """Raised when node parameters are invalid."""
    pass


class BoundaryConditionError(NodeError):
    """Raised when boundary conditions are violated."""
    pass


class PsychrometricError(HVACFlowError):
    """Raised when psychrometric calculations fail."""
    pass


class SerializationError(HVACFlowError):
    """Raised when project save/load fails."""
    pass
