"""Flow solver — propagates air states through the equipment graph.

Supports three modes of operation:
1. Single-pass DAG traversal (no cycles, no control loops)
2. Cycle-breaking iteration (two-stream devices with downstream feedback)
3. Control loop iteration (setpoint-actuator bisection)
"""

from collections import deque
from typing import Dict, List, Optional, Set

from hvac_flow.engine.air_state import AirState
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.solver.control_loop import ControlLoop

# Default initial guess for cycle-breaking (typical return air)
_DEFAULT_GUESS_DB_IP = 75.0
_DEFAULT_GUESS_RH = 0.50

# Convergence thresholds for cycle-breaking iteration
_CYCLE_DB_TOL = 0.1    # °F
_CYCLE_W_TOL = 0.0001  # lb_w/lb_da
_CYCLE_MAX_ITER = 30


class FlowSolver:
    """Traverses the flow graph in topological order, computing each node.

    After a successful ``solve()`` call:
    * ``self.all_states`` — every resolved outlet AirState (for the chart).
    * ``self.node_errors`` — per-node computation error messages.
    * ``self.node_warnings`` — per-node boundary-condition warnings.
    * ``self.errors`` / ``self.warnings`` — aggregate lists.
    """

    def __init__(self, graph: FlowGraph, calc: PsychroCalc):
        self.graph = graph
        self.calc = calc
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.all_states: List[AirState] = []
        self.node_errors: Dict[str, List[str]] = {}   # node_id -> errors
        self.node_warnings: Dict[str, List[str]] = {}  # node_id -> warnings
        self.control_loops: List[ControlLoop] = []

    def solve(self) -> bool:
        """Run a full solve pass.

        Returns True on success, False if errors occurred.
        """
        self._clear_state()

        # Validate (skip cycle check — we handle cycles ourselves)
        validation = self._validate_no_cycle_check()
        if validation:
            self.errors = validation
            return False

        # Determine solve strategy
        try:
            order = self.graph.topological_order()
            has_cycle = False
        except ValueError:
            has_cycle = True
            order = None

        active_loops = [cl for cl in self.control_loops if cl.enabled]

        if not has_cycle and not active_loops:
            # Fast path: single-pass DAG
            return self._solve_pass(order)

        if has_cycle:
            # Find tear edges to break cycles
            tear_connector_ids = self._find_tear_edges()
            if not tear_connector_ids:
                self.errors.append(
                    "Graph contains a cycle that cannot be automatically "
                    "resolved. Ensure two-stream devices (wheels, heat "
                    "recovery) have get_iterable_inlet() defined."
                )
                return False
            order = self._topological_order_ignoring(tear_connector_ids)
            if order is None:
                return False
        else:
            tear_connector_ids = set()

        return self._solve_iterative(order, tear_connector_ids, active_loops)

    # ── Single-pass solve ────────────────────────────────────────────

    def _solve_pass(self, order) -> bool:
        """Execute one forward pass through the graph."""
        self.all_states.clear()
        for node in self.graph.nodes.values():
            node.capacity_warnings.clear()

        for node in order:
            try:
                self._propagate_inlets(node)
                node.compute(self.calc)
                self._check_boundary_conditions(node)
                self._collect_states(node)
            except Exception as e:
                err_msg = str(e)
                if err_msg.startswith(f"[{node.name}]"):
                    self.errors.append(err_msg)
                else:
                    self.errors.append(f"[{node.name}] Error: {err_msg}")
                self.node_errors.setdefault(node.id, []).append(err_msg)
                return False
        return True

    # ── Iterative solve (cycles + control loops) ─────────────────────

    def _solve_iterative(self, order, tear_connector_ids, active_loops):
        """Iterate to resolve cycles and/or converge control loops."""
        max_iter = _CYCLE_MAX_ITER
        if active_loops:
            max_iter = max(max_iter, max(cl.max_iterations for cl in active_loops))

        # Initialize control loop bisection state
        for cl in active_loops:
            cl.converged = False
            cl.iterations_used = 0
            cl._lo = cl.actuator_min
            cl._hi = cl.actuator_max
            cl._direction_known = False
            cl._sensor_at_lo = None
            cl._sensor_at_hi = None

        prev_tear_states: Dict[str, AirState] = {}

        # Seed initial guess for torn inlets
        if tear_connector_ids:
            self._seed_tear_inlets(tear_connector_ids)

        for iteration in range(max_iter):
            # Apply control loop actuator values
            if active_loops:
                self._apply_control_actuators(active_loops, iteration)

            # Clear and run one pass
            self._clear_pass_state()
            if not self._solve_pass(order):
                return False

            # Check cycle convergence
            cycles_converged = True
            if tear_connector_ids:
                cycles_converged = self._check_tear_convergence(
                    tear_connector_ids, prev_tear_states
                )
                self._update_tear_inlets(tear_connector_ids)

            # Check control loop convergence
            loops_converged = True
            if active_loops:
                loops_converged = self._update_control_loops(active_loops, iteration)

            if cycles_converged and loops_converged:
                break

        # Report non-converged control loops
        for cl in active_loops:
            if not cl.converged:
                self.warnings.append(
                    f"[Control: {cl.name}] Did not converge after "
                    f"{cl.iterations_used} iterations "
                    f"(error={cl.final_error:.2f}, tol={cl.tolerance})"
                )

        return True

    # ── Cycle-breaking helpers ───────────────────────────────────────

    def _find_tear_edges(self) -> Set[str]:
        """Find connector IDs that should be 'torn' to break graph cycles.

        Uses Kahn's algorithm to find stuck nodes, then identifies connectors
        feeding iterable inlets on those nodes.
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for c in self.graph.connectors.values():
            in_degree[c.target_node_id] += 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        visited = set()
        while queue:
            nid = queue.popleft()
            visited.add(nid)
            for c in self.graph.get_connectors_from(nid):
                in_degree[c.target_node_id] -= 1
                if in_degree[c.target_node_id] == 0:
                    queue.append(c.target_node_id)

        stuck_ids = set(self.graph.nodes.keys()) - visited
        if not stuck_ids:
            return set()

        tear_ids = set()
        for nid in stuck_ids:
            node = self.graph.nodes[nid]
            iterable_port = node.get_iterable_inlet()
            if iterable_port is None:
                continue
            connector = self.graph.get_connector_to(nid, iterable_port)
            if connector is not None:
                tear_ids.add(connector.id)

        return tear_ids

    def _topological_order_ignoring(self, tear_ids: Set[str]):
        """Topological sort ignoring torn connectors."""
        in_degree: Dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for c in self.graph.connectors.values():
            if c.id not in tear_ids:
                in_degree[c.target_node_id] += 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order = []
        while queue:
            nid = queue.popleft()
            order.append(self.graph.nodes[nid])
            for c in self.graph.get_connectors_from(nid):
                if c.id in tear_ids:
                    continue
                in_degree[c.target_node_id] -= 1
                if in_degree[c.target_node_id] == 0:
                    queue.append(c.target_node_id)

        if len(order) != len(self.graph.nodes):
            self.errors.append(
                "Graph still contains a cycle after tearing iterable inlets. "
                "Check that all two-stream devices in the cycle define "
                "get_iterable_inlet()."
            )
            return None
        return order

    def _seed_tear_inlets(self, tear_ids: Set[str]):
        """Provide an initial-guess air state for torn inlet ports."""
        guess = self.calc.from_db_rh(
            _DEFAULT_GUESS_DB_IP, _DEFAULT_GUESS_RH,
            label="Initial guess"
        )
        for cid in tear_ids:
            c = self.graph.connectors[cid]
            target_node = self.graph.nodes[c.target_node_id]
            port = target_node.ports[c.target_port_name]
            port.air_state = guess
            # Estimate mass flow from the other inlet if available
            other_mass = None
            for p in target_node.inlet_ports:
                if p.name != c.target_port_name and p.mass_flow is not None:
                    other_mass = p.mass_flow
                    break
            port.mass_flow = other_mass or 750.0  # ~10000 CFM default

    def _check_tear_convergence(self, tear_ids, prev_states):
        """Check if torn inlet states have converged between iterations."""
        converged = True
        for cid in tear_ids:
            c = self.graph.connectors[cid]
            # The upstream node has now been computed — read its outlet
            upstream = self.graph.nodes.get(c.source_node_id)
            if upstream is None:
                converged = False
                continue
            upstream_port = upstream.ports.get(c.source_port_name)
            if upstream_port is None or upstream_port.air_state is None:
                converged = False
                continue

            new_state = upstream_port.air_state
            old_state = prev_states.get(cid)

            if old_state is None:
                # First iteration — no comparison possible, not converged
                converged = False
            else:
                db_err = abs(new_state.dry_bulb - old_state.dry_bulb)
                w_err = abs(new_state.humidity_ratio - old_state.humidity_ratio)
                if db_err > _CYCLE_DB_TOL or w_err > _CYCLE_W_TOL:
                    converged = False

            prev_states[cid] = new_state

        return converged

    def _update_tear_inlets(self, tear_ids):
        """Copy actual upstream states into torn inlet ports for next iteration."""
        for cid in tear_ids:
            c = self.graph.connectors[cid]
            upstream = self.graph.nodes.get(c.source_node_id)
            if upstream is None:
                continue
            upstream_port = upstream.ports.get(c.source_port_name)
            if upstream_port is None or upstream_port.air_state is None:
                continue
            target_node = self.graph.nodes[c.target_node_id]
            port = target_node.ports[c.target_port_name]
            state = c.apply_duct_loss(
                upstream_port.air_state, upstream_port.mass_flow, self.calc
            )
            port.air_state = state
            port.mass_flow = upstream_port.mass_flow

    # ── Control loop helpers ─────────────────────────────────────────

    def _apply_control_actuators(self, loops, iteration):
        """Set actuator parameter values for this iteration."""
        for cl in loops:
            if cl.converged:
                continue
            if not cl._direction_known:
                # First two iterations: probe endpoints to determine direction
                if iteration == 0:
                    val = cl.actuator_min
                elif iteration == 1:
                    val = cl.actuator_max
                else:
                    val = (cl._lo + cl._hi) / 2.0
            else:
                val = (cl._lo + cl._hi) / 2.0

            node = self.graph.nodes.get(cl.actuator_node_id)
            if node is not None:
                node.parameters[cl.actuator_parameter] = val

    def _update_control_loops(self, loops, iteration):
        """Read sensors, update bisection bounds. Returns True if all converged."""
        all_converged = True
        for cl in loops:
            if cl.converged:
                continue

            sensor_val = self._read_sensor(cl)
            if sensor_val is None:
                all_converged = False
                continue

            error = sensor_val - cl.setpoint
            cl.final_error = error
            cl.iterations_used = iteration + 1

            node = self.graph.nodes.get(cl.actuator_node_id)
            if node:
                cl.final_actuator_value = node.parameters.get(cl.actuator_parameter, 0)

            # Direction detection phase
            if not cl._direction_known:
                if iteration == 0:
                    cl._sensor_at_lo = sensor_val
                    all_converged = False
                    continue
                elif iteration == 1:
                    cl._sensor_at_hi = sensor_val
                    # Determine direction: does increasing actuator increase sensor?
                    if cl._sensor_at_lo is not None and cl._sensor_at_hi is not None:
                        cl._increasing = cl._sensor_at_hi > cl._sensor_at_lo
                        cl._direction_known = True
                        # Check if setpoint is reachable
                        lo_val = min(cl._sensor_at_lo, cl._sensor_at_hi)
                        hi_val = max(cl._sensor_at_lo, cl._sensor_at_hi)
                        if cl.setpoint < lo_val - cl.tolerance or cl.setpoint > hi_val + cl.tolerance:
                            self.warnings.append(
                                f"[Control: {cl.name}] Setpoint {cl.setpoint:.1f} "
                                f"is outside achievable range "
                                f"[{lo_val:.1f}, {hi_val:.1f}]"
                            )
                            cl.converged = True
                            continue
                    all_converged = False
                    continue

            # Convergence check
            if abs(error) <= cl.tolerance:
                cl.converged = True
                continue

            all_converged = False

            # Bisection update
            mid = cl.final_actuator_value
            if cl._increasing:
                # Increasing actuator increases sensor
                if error > 0:
                    cl._hi = mid  # sensor too high → decrease actuator
                else:
                    cl._lo = mid  # sensor too low → increase actuator
            else:
                # Increasing actuator decreases sensor
                if error > 0:
                    cl._lo = mid  # sensor too high → increase actuator
                else:
                    cl._hi = mid  # sensor too low → decrease actuator

        return all_converged

    def _read_sensor(self, cl: ControlLoop) -> Optional[float]:
        """Read the sensor value from the solved graph."""
        node = self.graph.nodes.get(cl.sensor_node_id)
        if node is None:
            return None
        port = node.ports.get(cl.sensor_port_name)
        if port is None or port.air_state is None:
            return None
        return getattr(port.air_state, cl.sensor_property, None)

    # ── Validation (cycle-tolerant) ──────────────────────────────────

    def _validate_no_cycle_check(self) -> List[str]:
        """Run graph validation but skip the cycle check (we handle it)."""
        errors = []
        if not self.graph.nodes:
            errors.append("Graph is empty — add at least one node.")
            return errors

        for node in self.graph.nodes.values():
            for port in node.inlet_ports:
                if port.connected_to is None:
                    errors.append(
                        f"[{node.name}] Inlet port '{port.name}' "
                        f"is not connected."
                    )

            for port in node.outlet_ports:
                if port.connected_to is None:
                    from hvac_flow.models.air_sink import AirSinkNode
                    if not isinstance(node, AirSinkNode):
                        has_any_connected_outlet = any(
                            p.connected_to is not None
                            for p in node.outlet_ports
                        )
                        if not has_any_connected_outlet:
                            errors.append(
                                f"[{node.name}] No outlet ports are "
                                f"connected — node output is unused."
                            )
                            break
        return errors

    # ── Internal plumbing ────────────────────────────────────────────

    def _clear_state(self):
        """Reset all solver state for a fresh solve."""
        self.errors.clear()
        self.warnings.clear()
        self.all_states.clear()
        self.node_errors.clear()
        self.node_warnings.clear()

    def _clear_pass_state(self):
        """Reset per-pass state for a new iteration.

        Clears warnings too so only the final iteration's warnings survive.
        Control loop non-convergence warnings are added after the loop.
        """
        self.all_states.clear()
        self.warnings.clear()
        self.node_errors.clear()
        self.node_warnings.clear()

    def _propagate_inlets(self, node, skip_ports: Optional[Set[str]] = None):
        """Copy upstream outlet states through connectors into inlet ports."""
        for port in node.inlet_ports:
            if skip_ports and port.name in skip_ports:
                continue
            connector = self.graph.get_connector_to(node.id, port.name)
            if connector is None:
                continue
            upstream_node = self.graph.nodes.get(connector.source_node_id)
            if upstream_node is None:
                continue
            upstream_port = upstream_node.ports.get(connector.source_port_name)
            if upstream_port is None or upstream_port.air_state is None:
                msg = (
                    f"[{node.name}] Upstream port "
                    f"'{connector.source_port_name}' on "
                    f"'{upstream_node.name}' has no air state."
                )
                self.warnings.append(msg)
                self.node_warnings.setdefault(node.id, []).append(msg)
                continue
            state = connector.apply_duct_loss(
                upstream_port.air_state, upstream_port.mass_flow, self.calc
            )
            port.air_state = state
            port.mass_flow = upstream_port.mass_flow

    def _check_boundary_conditions(self, node):
        """Run boundary-condition checks and collect any warnings."""
        bc_warnings = node.check_boundary_conditions()
        if bc_warnings:
            self.warnings.extend(bc_warnings)
            self.node_warnings.setdefault(node.id, []).extend(bc_warnings)

    def _collect_states(self, node):
        """Gather all resolved outlet air states for the psychrometric chart."""
        for port in node.outlet_ports:
            if port.air_state is not None:
                self.all_states.append(port.air_state)
