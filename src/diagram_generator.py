"""
BPMN Diagram Generator for SAP CPI iFlow Technical Specifications.

Generates clean, professional diagrams from SAP CPI iFlow data:
- Integration Flow Diagram (process steps)

Uses matplotlib for vector graphics output.
"""

import io
import logging
from collections import deque
from pathlib import Path
import textwrap
from typing import Dict, List, Any, Optional, Tuple
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch, Rectangle

logger = logging.getLogger(__name__)


class BPMNDiagramGenerator:
    """Generates clean BPMN-style diagrams for SAP CPI iFlows."""
    
    # Color scheme
    BLUE = '#0052A2'
    LIGHT_BLUE = '#E3F2FD'
    GREEN = '#2E7D32'
    LIGHT_GREEN = '#E8F5E9'
    ORANGE = '#E65100'
    LIGHT_ORANGE = '#FFF3E0'
    GRAY = '#616161'
    LIGHT_GRAY = '#F5F5F5'
    WHITE = '#FFFFFF'

    BPMN_NS = {
        'bpmn2': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
        'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
        'di': 'http://www.omg.org/spec/DD/20100524/DI',
        'dc': 'http://www.omg.org/spec/DD/20100524/DC',
        'ifl': 'http:///com.sap.ifl.model/Ifl.xsd',
    }
    
    def __init__(self, iflow_name: str, dpi: int = 220):
        self.iflow_name = iflow_name
        self.dpi = dpi

    @staticmethod
    def _truncate_label(value: str, max_len: int = 22) -> str:
        """Truncate labels to keep node text readable."""
        return value if len(value) <= max_len else f"{value[:max_len - 3]}..."

    def _wrap_label(self, value: str, width: int = 14, max_lines: int = 2) -> str:
        """Wrap labels into at most two lines for task boxes."""
        trimmed = self._truncate_label(value, max_len=(width * max_lines) + 3)
        lines = textwrap.wrap(trimmed, width=width) or [trimmed]
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self._truncate_label(lines[-1], max_len=width)
        return "\n".join(lines)

    def _order_nodes(self, sequence_flows: List[Tuple[str, str, str]], nodes: List[str]) -> List[str]:
        """Use topological ordering when possible to produce a readable left-to-right flow."""
        if not sequence_flows or not nodes:
            return nodes

        adjacency = {node: [] for node in nodes}
        indegree = {node: 0 for node in nodes}
        order_hint = {name: i for i, name in enumerate(nodes)}

        for src, tgt, _ in sequence_flows:
            adjacency.setdefault(src, [])
            adjacency.setdefault(tgt, [])
            indegree.setdefault(src, 0)
            indegree.setdefault(tgt, 0)
            if tgt not in adjacency[src]:
                adjacency[src].append(tgt)
                indegree[tgt] += 1

        queue = deque(sorted(
            [node for node, degree in indegree.items() if degree == 0],
            key=lambda name: order_hint.get(name, 10_000)
        ))

        ordered = []
        while queue:
            node = queue.popleft()
            ordered.append(node)
            for neighbor in adjacency.get(node, []):
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        # Fallback when graph contains cycles or disconnected references.
        return ordered if len(ordered) == len(indegree) else nodes

    @staticmethod
    def _local_name(tag: str) -> str:
        """Get local XML tag name without namespace."""
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    @staticmethod
    def _get_attr_by_suffix(attributes: Dict[str, str], suffix: str) -> str:
        """Read XML attribute by suffix to handle namespaced attributes."""
        for key, value in attributes.items():
            if key.endswith(suffix):
                return value
        return ""

    @staticmethod
    def _draw_collapsed_marker(ax, center_x: float, bottom_y: float, width: float):
        """Draw BPMN collapsed marker (+) for call activities/subprocesses."""
        marker_w = min(12.0, max(8.0, width * 0.1))
        marker_h = marker_w * 0.75
        marker_x = center_x - marker_w / 2
        marker_y = bottom_y - marker_h

        marker = Rectangle(
            (marker_x, marker_y), marker_w, marker_h,
            facecolor='#FFFFFF', edgecolor='#666666', linewidth=0.8, zorder=7
        )
        ax.add_patch(marker)
        ax.plot([center_x - marker_w * 0.2, center_x + marker_w * 0.2], [marker_y + marker_h / 2] * 2,
                color='#666666', linewidth=0.8, zorder=8)
        ax.plot([center_x, center_x], [marker_y + marker_h * 0.3, marker_y + marker_h * 0.7],
                color='#666666', linewidth=0.8, zorder=8)

    def _collect_element_metadata(self, root: ET.Element) -> Dict[str, Dict[str, str]]:
        """Collect BPMN element type/name keyed by element id."""
        metadata: Dict[str, Dict[str, str]] = {}
        for elem in root.iter():
            element_id = elem.attrib.get('id')
            if not element_id:
                continue
            metadata[element_id] = {
                'type': self._local_name(elem.tag),
                'name': elem.attrib.get('name', ''),
            }
        return metadata

    def _collect_participants(self, root: ET.Element) -> Dict[str, Dict[str, str]]:
        """Collect participant metadata for pool/lane rendering."""
        participants: Dict[str, Dict[str, str]] = {}
        for participant in root.findall('.//bpmn2:participant', self.BPMN_NS):
            participant_id = participant.attrib.get('id')
            if not participant_id:
                continue
            participants[participant_id] = {
                'name': participant.attrib.get('name', participant_id),
                'process_ref': participant.attrib.get('processRef', ''),
                'participant_type': self._get_attr_by_suffix(participant.attrib, 'type'),
            }
        return participants

    def _collect_bpmndi_shapes(self, root: ET.Element) -> Dict[str, Dict[str, float]]:
        """Collect BPMNShape bounds keyed by bpmnElement id."""
        shapes: Dict[str, Dict[str, float]] = {}
        for shape in root.findall('.//bpmndi:BPMNShape', self.BPMN_NS):
            element_id = shape.attrib.get('bpmnElement')
            bounds = shape.find('dc:Bounds', self.BPMN_NS)
            if not element_id or bounds is None:
                continue
            try:
                shapes[element_id] = {
                    'x': float(bounds.attrib.get('x', '0')),
                    'y': float(bounds.attrib.get('y', '0')),
                    'w': float(bounds.attrib.get('width', '0')),
                    'h': float(bounds.attrib.get('height', '0')),
                }
            except ValueError:
                continue
        return shapes

    def _collect_bpmndi_edges(self, root: ET.Element) -> Dict[str, List[Tuple[float, float]]]:
        """Collect BPMNEdge waypoints keyed by bpmnElement id."""
        edges: Dict[str, List[Tuple[float, float]]] = {}
        for edge in root.findall('.//bpmndi:BPMNEdge', self.BPMN_NS):
            flow_id = edge.attrib.get('bpmnElement')
            if not flow_id:
                continue
            points: List[Tuple[float, float]] = []
            for waypoint in edge.findall('di:waypoint', self.BPMN_NS):
                try:
                    x = float(waypoint.attrib.get('x', '0'))
                    y = float(waypoint.attrib.get('y', '0'))
                    points.append((x, y))
                except ValueError:
                    continue
            if len(points) >= 2:
                edges[flow_id] = points
        return edges

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        """Convert value to float safely."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _collect_data_with_bpmn_python(self, parser) -> Optional[Dict[str, Any]]:
        """Collect BPMN metadata using bpmn_python when available."""
        try:
            import networkx as nx
            from bpmn_python import bpmn_diagram_rep, bpmn_diagram_import
            from bpmn_python import bpmn_python_consts as bpmn_consts
        except Exception as exc:
            logger.debug(f"bpmn_python import unavailable: {exc}")
            return None

        try:
            # bpmn_python expects legacy networkx node/edge accessors.
            if not hasattr(nx.Graph, 'node'):
                setattr(nx.Graph, 'node', property(lambda self: self._node))
            if not hasattr(nx.DiGraph, 'node'):
                setattr(nx.DiGraph, 'node', property(lambda self: self._node))
            if not hasattr(nx.Graph, 'edge'):
                setattr(nx.Graph, 'edge', property(lambda self: self._adj))
            if not hasattr(nx.DiGraph, 'edge'):
                setattr(nx.DiGraph, 'edge', property(lambda self: self._adj))

            if not getattr(bpmn_diagram_import.BpmnDiagramGraphImport, '_sap_safe_shape_patch', False):
                def safe_import_shape_di(participants_dict, diagram_graph, shape_element):
                    element_id = shape_element.getAttribute(bpmn_consts.Consts.bpmn_element)
                    bounds_nodes = shape_element.getElementsByTagNameNS('*', 'Bounds')
                    if not bounds_nodes:
                        return
                    bounds = bounds_nodes[0]

                    if diagram_graph.has_node(element_id):
                        node = diagram_graph.node[element_id]
                        node[bpmn_consts.Consts.width] = bounds.getAttribute(bpmn_consts.Consts.width)
                        node[bpmn_consts.Consts.height] = bounds.getAttribute(bpmn_consts.Consts.height)
                        if node.get(bpmn_consts.Consts.type) == bpmn_consts.Consts.subprocess:
                            node[bpmn_consts.Consts.is_expanded] = (
                                shape_element.getAttribute(bpmn_consts.Consts.is_expanded)
                                if shape_element.hasAttribute(bpmn_consts.Consts.is_expanded)
                                else 'false'
                            )
                        node[bpmn_consts.Consts.x] = bounds.getAttribute(bpmn_consts.Consts.x)
                        node[bpmn_consts.Consts.y] = bounds.getAttribute(bpmn_consts.Consts.y)

                    if element_id in participants_dict:
                        participant_attr = participants_dict[element_id]
                        participant_attr[bpmn_consts.Consts.is_horizontal] = shape_element.getAttribute(
                            bpmn_consts.Consts.is_horizontal
                        )
                        participant_attr[bpmn_consts.Consts.width] = bounds.getAttribute(bpmn_consts.Consts.width)
                        participant_attr[bpmn_consts.Consts.height] = bounds.getAttribute(bpmn_consts.Consts.height)
                        participant_attr[bpmn_consts.Consts.x] = bounds.getAttribute(bpmn_consts.Consts.x)
                        participant_attr[bpmn_consts.Consts.y] = bounds.getAttribute(bpmn_consts.Consts.y)

                bpmn_diagram_import.BpmnDiagramGraphImport.import_shape_di = staticmethod(safe_import_shape_di)
                setattr(bpmn_diagram_import.BpmnDiagramGraphImport, '_sap_safe_shape_patch', True)

            diagram = bpmn_diagram_rep.BpmnDiagramGraph()
            diagram.load_diagram_from_xml_file(str(parser.iflow_path))

            graph = diagram.diagram_graph
            element_meta: Dict[str, Dict[str, str]] = {}
            shapes: Dict[str, Dict[str, float]] = {}
            edges: Dict[str, List[Tuple[float, float]]] = {}
            participants: Dict[str, Dict[str, str]] = {}

            for node_id, attrs in graph.nodes(data=True):
                node_name = str(attrs.get('node_name', ''))
                node_type = str(attrs.get('type', ''))
                element_meta[str(node_id)] = {'type': node_type, 'name': node_name}

                x = self._to_float(attrs.get('x'))
                y = self._to_float(attrs.get('y'))
                w = self._to_float(attrs.get('width'))
                h = self._to_float(attrs.get('height'))
                if x is not None and y is not None and w is not None and h is not None:
                    shapes[str(node_id)] = {'x': x, 'y': y, 'w': w, 'h': h}

            collaboration = getattr(diagram, 'collaboration', {}) or {}
            participant_data = collaboration.get('participants', {}) if isinstance(collaboration, dict) else {}
            if isinstance(participant_data, dict):
                for participant_id, info in participant_data.items():
                    p_name = str(info.get('name', participant_id))
                    p_ref = str(info.get('processRef', ''))
                    participants[str(participant_id)] = {
                        'name': p_name,
                        'process_ref': p_ref,
                        'participant_type': '',
                    }

                    x = self._to_float(info.get('x'))
                    y = self._to_float(info.get('y'))
                    w = self._to_float(info.get('width'))
                    h = self._to_float(info.get('height'))
                    if x is not None and y is not None and w is not None and h is not None:
                        shapes[str(participant_id)] = {'x': x, 'y': y, 'w': w, 'h': h}

            for src, tgt, attrs in graph.edges(data=True):
                flow_id = str(attrs.get('id', '')).strip()
                if not flow_id:
                    continue

                waypoints = attrs.get('waypoints')
                if not isinstance(waypoints, list):
                    continue

                points: List[Tuple[float, float]] = []
                for waypoint in waypoints:
                    if not isinstance(waypoint, (list, tuple)) or len(waypoint) < 2:
                        continue
                    x = self._to_float(waypoint[0])
                    y = self._to_float(waypoint[1])
                    if x is None or y is None:
                        continue
                    points.append((x, y))

                if len(points) >= 2:
                    edges[flow_id] = points

            if not shapes:
                return None

            return {
                'element_meta': element_meta,
                'participants': participants,
                'shapes': shapes,
                'edges': edges,
            }

        except Exception as exc:
            logger.warning(f"bpmn_python parsing failed, using XML parser path: {exc}")
            return None

    @staticmethod
    def _draw_open_arrow_head(
        ax,
        tail: Tuple[float, float],
        tip: Tuple[float, float],
        color: str,
        size: float = 8.0,
        width: float = 1.1,
    ):
        """Draw an open (unfilled) arrow head, BPMN message-flow style."""
        dx = tip[0] - tail[0]
        dy = tip[1] - tail[1]
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length <= 0:
            return

        ux = dx / length
        uy = dy / length
        px = -uy
        py = ux

        base_x = tip[0] - (ux * size)
        base_y = tip[1] - (uy * size)
        wing = size * 0.55

        left_x = base_x + (px * wing)
        left_y = base_y + (py * wing)
        right_x = base_x - (px * wing)
        right_y = base_y - (py * wing)

        ax.plot([tip[0], left_x], [tip[1], left_y], color=color, linewidth=width, zorder=5)
        ax.plot([tip[0], right_x], [tip[1], right_y], color=color, linewidth=width, zorder=5)

    def _draw_sequence_flow(self, ax, points: List[Tuple[float, float]], color: str):
        """Draw BPMN sequence flow (solid with filled arrow)."""
        if len(points) < 2:
            return
        xs = [pt[0] for pt in points]
        ys = [pt[1] for pt in points]
        ax.plot(xs, ys, color=color, linewidth=1.6, linestyle='-', zorder=3)

        arrow = FancyArrowPatch(
            points[-2],
            points[-1],
            arrowstyle='-|>',
            mutation_scale=13,
            linewidth=1.6,
            color=color,
            zorder=5,
        )
        ax.add_patch(arrow)

    def _draw_message_flow(self, ax, points: List[Tuple[float, float]], color: str):
        """Draw BPMN message flow (dashed with open circle + open arrow)."""
        if len(points) < 2:
            return
        xs = [pt[0] for pt in points]
        ys = [pt[1] for pt in points]
        ax.plot(xs, ys, color=color, linewidth=1.35, linestyle=(0, (6, 4)), zorder=3)

        start_circle = Circle(points[0], radius=3.2, facecolor=self.WHITE, edgecolor=color, linewidth=1.1, zorder=5)
        ax.add_patch(start_circle)
        self._draw_open_arrow_head(ax, points[-2], points[-1], color=color, size=8.5, width=1.2)

    @staticmethod
    def _point_inside_bounds(point: Tuple[float, float], bounds: Dict[str, float]) -> bool:
        """Check whether point lies within shape bounds."""
        x, y = point
        return (
            bounds['x'] <= x <= (bounds['x'] + bounds['w'])
            and bounds['y'] <= y <= (bounds['y'] + bounds['h'])
        )

    @staticmethod
    def _project_center_to_bounds_edge(
        bounds: Dict[str, float],
        toward: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Project from shape center toward a point and return box-edge intersection."""
        cx = bounds['x'] + (bounds['w'] / 2)
        cy = bounds['y'] + (bounds['h'] / 2)
        vx = toward[0] - cx
        vy = toward[1] - cy

        if abs(vx) < 1e-9 and abs(vy) < 1e-9:
            return cx, cy

        sx = float('inf') if abs(vx) < 1e-9 else (bounds['w'] / 2) / abs(vx)
        sy = float('inf') if abs(vy) < 1e-9 else (bounds['h'] / 2) / abs(vy)
        scale = min(sx, sy)
        return cx + (vx * scale), cy + (vy * scale)

    def _normalize_flow_points(
        self,
        points: List[Tuple[float, float]],
        source_bounds: Optional[Dict[str, float]],
        target_bounds: Optional[Dict[str, float]],
    ) -> List[Tuple[float, float]]:
        """Adjust first/last waypoints to source/target shape borders when needed."""
        if len(points) < 2:
            return points

        normalized = list(points)

        if source_bounds and self._point_inside_bounds(normalized[0], source_bounds):
            normalized[0] = self._project_center_to_bounds_edge(source_bounds, normalized[1])

        if target_bounds and self._point_inside_bounds(normalized[-1], target_bounds):
            normalized[-1] = self._project_center_to_bounds_edge(target_bounds, normalized[-2])

        return normalized

    def generate_integration_flow_diagram_from_bpmndi(self, parser) -> Optional[bytes]:
        """Generate BPMN-style diagram directly from BPMN-DI coordinates."""
        try:
            root = parser.get_root()
            element_meta = self._collect_element_metadata(root)
            participants = self._collect_participants(root)
            shapes = self._collect_bpmndi_shapes(root)
            edges = self._collect_bpmndi_edges(root)

            bpmn_python_data = self._collect_data_with_bpmn_python(parser)
            if bpmn_python_data:
                for element_id, meta in bpmn_python_data.get('element_meta', {}).items():
                    existing = element_meta.get(element_id, {})
                    existing_name = str(existing.get('name', '')).strip()
                    existing_type = str(existing.get('type', '')).strip()
                    incoming_name = str(meta.get('name', '')).strip()
                    incoming_type = str(meta.get('type', '')).strip()

                    element_meta[element_id] = {
                        'name': existing_name if existing_name else incoming_name,
                        'type': existing_type if existing_type else incoming_type,
                    }

                for participant_id, info in bpmn_python_data.get('participants', {}).items():
                    existing = participants.get(participant_id, {})
                    participants[participant_id] = {
                        'name': info.get('name', existing.get('name', participant_id)),
                        'process_ref': info.get('process_ref', existing.get('process_ref', '')),
                        'participant_type': existing.get('participant_type', ''),
                    }

                shapes.update(bpmn_python_data.get('shapes', {}))
                edges.update(bpmn_python_data.get('edges', {}))

            if not shapes:
                logger.warning("No BPMN-DI shape data found; falling back to legacy layout")
                return None

            flow_meta: Dict[str, Dict[str, str]] = {}
            for flow in root.findall('.//bpmn2:sequenceFlow', self.BPMN_NS):
                flow_id = flow.attrib.get('id')
                if flow_id:
                    flow_meta[flow_id] = {
                        'type': 'sequence',
                        'name': flow.attrib.get('name', ''),
                        'source_ref': flow.attrib.get('sourceRef', ''),
                        'target_ref': flow.attrib.get('targetRef', ''),
                    }
            for flow in root.findall('.//bpmn2:messageFlow', self.BPMN_NS):
                flow_id = flow.attrib.get('id')
                if flow_id:
                    flow_meta[flow_id] = {
                        'type': 'message',
                        'name': flow.attrib.get('name', ''),
                        'source_ref': flow.attrib.get('sourceRef', ''),
                        'target_ref': flow.attrib.get('targetRef', ''),
                    }

            all_x: List[float] = []
            all_y: List[float] = []
            for bounds in shapes.values():
                all_x.extend([bounds['x'], bounds['x'] + bounds['w']])
                all_y.extend([bounds['y'], bounds['y'] + bounds['h']])
            for points in edges.values():
                all_x.extend([pt[0] for pt in points])
                all_y.extend([pt[1] for pt in points])

            if not all_x or not all_y:
                logger.warning("No drawable BPMN-DI coordinates found")
                return None

            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            diagram_w = max(max_x - min_x, 1.0)
            diagram_h = max(max_y - min_y, 1.0)

            fig_w = min(20.0, max(14.0, diagram_w / 95.0))
            fig_h = min(12.5, max(8.0, diagram_h / 95.0))

            fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))
            ax.set_facecolor(self.WHITE)
            fig.patch.set_facecolor(self.WHITE)

            pad = max(20.0, min(32.0, max(diagram_w, diagram_h) * 0.03))
            ax.set_xlim(min_x - pad, max_x + pad)
            ax.set_ylim(max_y + pad, min_y - pad)  # inverted y-axis to match BPMN canvas
            ax.axis('off')

            # Draw pools/participants first.
            participant_ids = [pid for pid in participants if pid in shapes]
            participant_ids.sort(
                key=lambda pid: shapes[pid]['w'] * shapes[pid]['h'],
                reverse=True,
            )

            for participant_id in participant_ids:
                info = participants.get(participant_id, {})
                bounds = shapes[participant_id]
                x, y, w, h = bounds['x'], bounds['y'], bounds['w'], bounds['h']
                name = str(info.get('name', participant_id)).replace('_', ' ')
                is_process_pool = bool(info.get('process_ref')) or w > 300

                if is_process_pool:
                    pool = Rectangle(
                        (x, y), w, h,
                        facecolor='#ECECEC', edgecolor='#6F6F6F', linewidth=1.3, zorder=1
                    )
                    ax.add_patch(pool)

                    lane_w = max(22.0, min(34.0, w * 0.05))
                    lane_label = Rectangle(
                        (x, y), lane_w, h,
                        facecolor='#E3E3E3', edgecolor='#6F6F6F', linewidth=1.1, zorder=2
                    )
                    ax.add_patch(lane_label)

                    ax.text(
                        x + lane_w / 2,
                        y + h / 2,
                        self._wrap_label(name, width=14, max_lines=3),
                        rotation=90,
                        ha='center',
                        va='center',
                        fontsize=8,
                        color='#3D3D3D',
                        zorder=3,
                    )
                else:
                    ext_box = Rectangle(
                        (x, y), w, h,
                        facecolor='#F6F6F6', edgecolor='#6F6F6F', linewidth=1.1, zorder=2
                    )
                    ax.add_patch(ext_box)
                    ax.text(
                        x + w / 2,
                        y + h / 2,
                        self._wrap_label(name, width=14, max_lines=3),
                        ha='center',
                        va='center',
                        fontsize=8,
                        color='#2F2F2F',
                        zorder=3,
                    )

            # Draw BPMN nodes.
            for element_id, bounds in shapes.items():
                if element_id in participants:
                    continue

                meta = element_meta.get(element_id, {})
                element_type = str(meta.get('type', '')).lower()
                label = str(meta.get('name') or element_id).replace('_', ' ')
                x, y, w, h = bounds['x'], bounds['y'], bounds['w'], bounds['h']
                cx, cy = x + (w / 2), y + (h / 2)

                if 'event' in element_type:
                    radius = min(w, h) * 0.46
                    lw = 2.2 if 'endevent' in element_type else 1.6
                    event = Circle(
                        (cx, cy), radius,
                        facecolor='#FFFFFF', edgecolor='#2F343B', linewidth=lw, zorder=6
                    )
                    ax.add_patch(event)
                    ax.text(
                        cx,
                        y + h + 10,
                        self._wrap_label(label, width=12, max_lines=2),
                        ha='center',
                        va='top',
                        fontsize=7.8,
                        color='#2F343B',
                        zorder=7,
                    )
                    continue

                if 'gateway' in element_type:
                    diamond = patches.Polygon(
                        [(cx, y), (x + w, cy), (cx, y + h), (x, cy)],
                        closed=True,
                        facecolor='#FFFFFF', edgecolor='#2F343B', linewidth=1.6, zorder=5
                    )
                    ax.add_patch(diamond)
                    ax.text(
                        cx,
                        y + h + 10,
                        self._truncate_label(label, 22),
                        fontsize=7.8,
                        ha='center',
                        va='top',
                        color='#2F343B',
                        zorder=7,
                    )
                    continue

                if 'subprocess' in element_type:
                    subproc = FancyBboxPatch(
                        (x, y), w, h,
                        boxstyle='round,pad=0.01,rounding_size=8',
                        facecolor='#EFEFEF', edgecolor='#6D7177', linewidth=1.2, zorder=4
                    )
                    ax.add_patch(subproc)
                    label_y = y + min(18.0, max(12.0, h * 0.18))
                    ax.text(
                        cx,
                        label_y,
                        self._wrap_label(label, width=max(10, int(w / 7)), max_lines=2),
                        ha='center',
                        va='top',
                        fontsize=8,
                        color='#2F343B',
                        zorder=6,
                    )
                    self._draw_collapsed_marker(ax, cx, y + h - 5, w)
                    continue

                # Default task/callActivity/serviceTask style.
                line_w = 2.0 if 'callactivity' in element_type else 1.7
                task = FancyBboxPatch(
                    (x, y), w, h,
                    boxstyle='round,pad=0.01,rounding_size=10',
                    facecolor='#FFFFFF', edgecolor='#2F343B', linewidth=line_w, zorder=5
                )
                ax.add_patch(task)

                if 'servicetask' in element_type:
                    ax.add_patch(Circle((x + 8.5, y + 8.5), 3.2, facecolor='#F2F2F2',
                                        edgecolor='#6A6A6A', linewidth=0.8, zorder=6))

                ax.text(
                    cx,
                    cy,
                    self._wrap_label(label, width=max(10, int(w / 7)), max_lines=2),
                    ha='center',
                    va='center',
                    fontsize=8.2,
                    color='#2F343B',
                    zorder=6,
                )

                if 'callactivity' in element_type:
                    self._draw_collapsed_marker(ax, cx, y + h - 5, w)

            # Draw sequence and message edges.
            for flow_id, points in edges.items():
                info = flow_meta.get(flow_id, {'type': 'sequence', 'name': ''})
                is_message = info.get('type') == 'message'
                color = '#7A7A7A' if is_message else '#2F343B'

                source_bounds = shapes.get(str(info.get('source_ref', '')))
                target_bounds = shapes.get(str(info.get('target_ref', '')))
                normalized_points = self._normalize_flow_points(points, source_bounds, target_bounds)

                if is_message:
                    self._draw_message_flow(ax, normalized_points, color=color)
                else:
                    self._draw_sequence_flow(ax, normalized_points, color=color)

                flow_name = str(info.get('name', '')).strip()
                if flow_name:
                    mid_idx = max(0, (len(normalized_points) // 2) - 1)
                    x1, y1 = normalized_points[mid_idx]
                    x2, y2 = normalized_points[mid_idx + 1]
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    ax.text(
                        mid_x,
                        mid_y - 10,
                        self._truncate_label(flow_name, max_len=34),
                        fontsize=7.6,
                        color='#4A4A4A',
                        ha='center',
                        va='center',
                        bbox=dict(facecolor='#FFFFFF', edgecolor='none', alpha=0.8, pad=0.6),
                        zorder=8,
                    )

            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(
                buf,
                format='png',
                dpi=self.dpi,
                bbox_inches='tight',
                facecolor=self.WHITE,
                edgecolor='none',
            )
            buf.seek(0)
            plt.close(fig)
            return buf.getvalue()

        except Exception as e:
            logger.error(f"BPMN-DI diagram generation error: {e}")
            return None
    
    def generate_integration_flow_diagram(
        self,
        processes: List[Dict[str, Any]],
        sequence_flows: List[Tuple[str, str, str]],
    ) -> bytes:
        """Generate integration flow diagram showing process steps."""
        try:
            fig, ax = plt.subplots(1, 1, figsize=(14, 8))
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 70)
            ax.axis('off')
            ax.set_facecolor(self.WHITE)
            fig.patch.set_facecolor(self.WHITE)
            
            # Title
            ax.text(50, 67, f"Integration Flow: {self.iflow_name}", fontsize=14,
                   ha='center', weight='bold', color=self.BLUE)
            
            # Main container
            container = FancyBboxPatch((5, 10), 90, 50, boxstyle="round,pad=0.01,rounding_size=0.3",
                                      facecolor=self.LIGHT_GRAY, edgecolor=self.GRAY, linewidth=1.5)
            ax.add_patch(container)
            ax.text(50, 57, "Integration Process", fontsize=11, ha='center', weight='bold')
            
            # Build node list from sequence flows
            nodes = []
            for src, tgt, _ in sequence_flows:
                if src not in nodes:
                    nodes.append(src)
                if tgt not in nodes:
                    nodes.append(tgt)
            
            # If no sequence flows, use process names
            if not nodes:
                nodes = [p.get('name', f'Step {i+1}') for i, p in enumerate(processes)]
            
            if not nodes:
                nodes = ['Start', 'Process', 'End']

            nodes = self._order_nodes(sequence_flows, nodes)
            
            # Calculate positions
            num_nodes = len(nodes)
            max_per_row = 6
            row_count = max(1, (num_nodes + max_per_row - 1) // max_per_row)

            if row_count == 1:
                row_ys = [35]
            else:
                vertical_span = 20
                step_y = vertical_span / max(row_count - 1, 1)
                row_ys = [42 - (idx * step_y) for idx in range(row_count)]
            
            node_positions = {}
            for row_index, y in enumerate(row_ys):
                row_nodes = nodes[row_index * max_per_row:(row_index + 1) * max_per_row]
                count = len(row_nodes)
                if count == 1:
                    x_positions = [50]
                else:
                    start_x, end_x = 12, 88
                    step_x = (end_x - start_x) / (count - 1)
                    x_positions = [start_x + (i * step_x) for i in range(count)]

                for node, x in zip(row_nodes, x_positions):
                    node_positions[node] = (x, y)
            
            # Determine start/end nodes
            sources = {src for src, _, _ in sequence_flows}
            targets = {tgt for _, tgt, _ in sequence_flows}
            start_nodes = sources - targets
            end_nodes = targets - sources

            if not start_nodes:
                start_nodes = {name for name in nodes if 'start' in name.lower()}
            if not end_nodes:
                end_nodes = {name for name in nodes if 'end' in name.lower()}
            
            # Draw nodes
            box_w = 11 if num_nodes <= 8 else 9.5
            box_h = 6.5
            event_radius = 2.5
            font_size = 8 if num_nodes <= 8 else 7
            event_nodes = start_nodes.union(end_nodes)
            
            for node, (x, y) in node_positions.items():
                display = self._truncate_label(node, max_len=20)
                node_lower = node.lower()
                
                if node in start_nodes or 'start' in node_lower:
                    # Start event - green circle
                    circle = Circle((x, y), event_radius, facecolor=self.GREEN, edgecolor=self.GREEN, linewidth=2, zorder=2)
                    ax.add_patch(circle)
                    ax.text(x, y - 5.5, display, fontsize=font_size, ha='center', zorder=3)
                elif node in end_nodes or 'end' in node_lower:
                    # End event - orange circle
                    circle = Circle((x, y), event_radius, facecolor=self.ORANGE, edgecolor=self.ORANGE, linewidth=2, zorder=2)
                    ax.add_patch(circle)
                    ax.text(x, y - 5.5, display, fontsize=font_size, ha='center', zorder=3)
                else:
                    # Task box
                    box = FancyBboxPatch((x - box_w/2, y - box_h/2), box_w, box_h,
                                        boxstyle="round,pad=0.02,rounding_size=0.3",
                                        facecolor=self.LIGHT_BLUE, edgecolor=self.BLUE, linewidth=1.5, zorder=2)
                    ax.add_patch(box)
                    ax.text(
                        x,
                        y,
                        self._wrap_label(display, width=14 if box_w >= 10 else 12, max_lines=2),
                        fontsize=font_size,
                        ha='center',
                        va='center',
                        zorder=3
                    )
            
            # Draw sequence flows
            for src, tgt, label in sequence_flows:
                if src in node_positions and tgt in node_positions:
                    x1, y1 = node_positions[src]
                    x2, y2 = node_positions[tgt]

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = (dx ** 2 + dy ** 2) ** 0.5
                    if distance == 0:
                        continue

                    ux = dx / distance
                    uy = dy / distance

                    src_offset = event_radius if src in event_nodes else box_w / 2
                    tgt_offset = event_radius if tgt in event_nodes else box_w / 2

                    start_x = x1 + (ux * src_offset)
                    start_y = y1 + (uy * src_offset)
                    end_x = x2 - (ux * tgt_offset)
                    end_y = y2 - (uy * tgt_offset)

                    ax.annotate('', xy=(end_x, end_y), xytext=(start_x, start_y),
                               arrowprops=dict(arrowstyle='->', color=self.GRAY, lw=1.5), zorder=1)
            
            # Legend
            ax.add_patch(Circle((15, 5), 1.5, facecolor=self.GREEN, edgecolor=self.GREEN))
            ax.text(18, 5, "Start", fontsize=8, va='center')
            
            ax.add_patch(FancyBboxPatch((30, 3.5), 5, 3, boxstyle="round,pad=0.02,rounding_size=0.2",
                                       facecolor=self.LIGHT_BLUE, edgecolor=self.BLUE))
            ax.text(38, 5, "Task", fontsize=8, va='center')
            
            ax.add_patch(Circle((55, 5), 1.5, facecolor=self.ORANGE, edgecolor=self.ORANGE))
            ax.text(58, 5, "End", fontsize=8, va='center')
            
            plt.tight_layout()
            
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight',
                       facecolor=self.WHITE, edgecolor='none')
            buf.seek(0)
            plt.close(fig)
            
            return buf.getvalue()
            
        except Exception as e:
            logger.error(f"Integration flow diagram error: {e}")
            raise


def generate_diagram_bytes(parser, diagram_type: str = "integration_flow") -> Optional[bytes]:
    """
    Generate diagram and return as bytes for embedding in documents.
    
    Args:
        parser: IFlowParser instance
        diagram_type: 'integration_flow'
        
    Returns:
        PNG image bytes or None on failure
    """
    try:
        generator = BPMNDiagramGenerator(parser.iflow_name)

        if diagram_type == "integration_flow":
            bpmn_diagram = generator.generate_integration_flow_diagram_from_bpmndi(parser)
            if bpmn_diagram:
                return bpmn_diagram

            logger.warning("Falling back to legacy integration flow layout")
            processes = parser.get_integration_processes()
            sequence_flows = parser.extract_sequence_flows_with_names()
            return generator.generate_integration_flow_diagram(processes, sequence_flows)
        
        logger.warning(f"Unknown diagram type: {diagram_type}")
        return None
            
    except Exception as e:
        logger.error(f"Error generating {diagram_type} diagram: {e}")
        return None


def generate_iflow_diagrams(parser, output_dir: Optional[Path] = None) -> Dict[str, Path]:
    """
    Generate all diagrams and save to files.
    
    Args:
        parser: IFlowParser instance
        output_dir: Output directory
        
    Returns:
        Dict mapping diagram type to file path
    """
    if output_dir is None:
        output_dir = Path("output")
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    results = {}
    safe_name = "".join(c for c in parser.iflow_name if c.isalnum() or c in "._- ")
    
    for dtype in ['integration_flow']:
        try:
            img_bytes = generate_diagram_bytes(parser, dtype)
            if img_bytes:
                path = output_dir / f"{safe_name}_{dtype}.png"
                with open(path, 'wb') as f:
                    f.write(img_bytes)
                results[dtype] = path
                logger.info(f"Generated {dtype} diagram: {path}")
        except Exception as e:
            logger.error(f"Failed to generate {dtype} diagram: {e}")
    
    return results
