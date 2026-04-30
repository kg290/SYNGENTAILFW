"""
BPMN Diagram Generator for SAP CPI iFlow Technical Specifications.

Generates clean, professional diagrams from SAP CPI iFlow data:
- Integration Flow Diagram (process steps)

Uses matplotlib for vector graphics output.
"""

import io
import logging
import re
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

    # SAP CPI-like styling tokens used by the BPMN-DI renderer.
    SAP_TASK_FILL = '#EAF5FF'
    SAP_TASK_EDGE = '#87B1D8'
    SAP_TEXT = '#2F4D69'
    SAP_POOL_BG = '#F8FAFC'
    SAP_POOL_EDGE = '#C1CAD4'
    SAP_LANE_BG = '#EFF3F7'
    SAP_SEQ_FLOW = '#6087AD'
    SAP_MSG_FLOW = '#92A8BD'

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
        self._runtime_parameters: Dict[str, str] = {}

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
            facecolor='#FFFFFF', edgecolor='#73889D', linewidth=0.75, zorder=7
        )
        ax.add_patch(marker)
        ax.plot([center_x - marker_w * 0.2, center_x + marker_w * 0.2], [marker_y + marker_h / 2] * 2,
            color='#73889D', linewidth=0.8, zorder=8)
        ax.plot([center_x, center_x], [marker_y + marker_h * 0.3, marker_y + marker_h * 0.7],
            color='#73889D', linewidth=0.8, zorder=8)

    @staticmethod
    def _draw_task_activity_marker(ax, center_x: float, bottom_y: float, width: float):
        """Draw a compact activity marker under task nodes for SAP-style look."""
        marker_w = min(7.2, max(5.0, width * 0.055))
        marker_h = marker_w * 0.78
        marker_x = center_x - marker_w / 2
        marker_y = bottom_y - marker_h
        marker = Rectangle(
            (marker_x, marker_y), marker_w, marker_h,
            facecolor='#FFFFFF', edgecolor='#97B2CB', linewidth=0.65, zorder=7
        )
        ax.add_patch(marker)
        ax.plot(
            [marker_x + marker_w * 0.18, marker_x + marker_w * 0.82],
            [marker_y + marker_h * 0.52, marker_y + marker_h * 0.52],
            color='#8CA9C3',
            linewidth=0.6,
            zorder=8,
        )

    @staticmethod
    def _draw_task_corner_icon(ax, x: float, y: float):
        """Draw a tiny document-like glyph in task corner."""
        icon_w = 4.4
        icon_h = 4.0
        left = x + 3.0
        top = y + 3.0
        icon = Rectangle(
            (left, top),
            icon_w,
            icon_h,
            facecolor='#FFFFFF',
            edgecolor='#8EAED0',
            linewidth=0.6,
            zorder=8,
        )
        ax.add_patch(icon)
        ax.plot(
            [left + icon_w * 0.68, left + icon_w * 0.95, left + icon_w * 0.95],
            [top, top, top + icon_h * 0.28],
            color='#8EAED0',
            linewidth=0.55,
            zorder=9,
        )

    @staticmethod
    def _draw_gateway_marker(ax, cx: float, cy: float, element_type: str):
        """Draw BPMN gateway marker inside gateway diamond."""
        marker = element_type.lower()
        size = 2.9
        color = '#4D6F90'

        if 'parallel' in marker:
            ax.plot([cx - size, cx + size], [cy, cy], color=color, linewidth=1.3, zorder=7)
            ax.plot([cx, cx], [cy - size, cy + size], color=color, linewidth=1.3, zorder=7)
            return

        if 'inclusive' in marker:
            inner = Circle((cx, cy), radius=2.7, facecolor='none', edgecolor=color, linewidth=1.2, zorder=7)
            ax.add_patch(inner)
            return

        # Default/exclusive marker.
        ax.plot([cx - size, cx + size], [cy - size, cy + size], color=color, linewidth=1.1, zorder=7)
        ax.plot([cx - size, cx + size], [cy + size, cy - size], color=color, linewidth=1.1, zorder=7)

    @staticmethod
    def _draw_message_envelope(ax, x: float, y: float, color: str):
        """Draw a tiny envelope icon near the start of message flows."""
        w, h = 4.6, 3.2
        left = x - (w / 2)
        top = y - (h / 2)
        env = Rectangle((left, top), w, h, facecolor='#FFFFFF', edgecolor=color, linewidth=0.72, zorder=6)
        ax.add_patch(env)
        ax.plot([left, left + (w / 2), left + w], [top, top + h * 0.58, top], color=color, linewidth=0.7, zorder=7)
        ax.plot([left, left + (w / 2)], [top + h, top + h * 0.54], color=color, linewidth=0.55, zorder=7)
        ax.plot([left + w, left + (w / 2)], [top + h, top + h * 0.54], color=color, linewidth=0.55, zorder=7)

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
    def _normalize_lookup_key(value: str) -> str:
        """Normalize property keys to robust lookup tokens."""
        return re.sub(r'[^a-z0-9]+', '', str(value or '').strip().lower())

    def _resolve_runtime_placeholders(self, value: str) -> str:
        """Resolve ${...} and {{...}} placeholders from runtime parameter files."""
        raw = str(value or '').strip()
        if not raw:
            return ""

        pattern = re.compile(r'\$\{([^}]+)\}|\{\{([^}]+)\}\}')

        def replacer(match: re.Match[str]) -> str:
            key = (match.group(1) or match.group(2) or '').replace('\\ ', ' ').strip()
            if not key:
                return match.group(0)
            lookup = self._normalize_lookup_key(key)
            if lookup not in self._runtime_parameters:
                return match.group(0)
            return self._decode_runtime_value(self._runtime_parameters.get(lookup, ''))

        return pattern.sub(replacer, raw)

    @staticmethod
    def _decode_runtime_value(value: str) -> str:
        """Decode common Java-properties escape sequences for display."""
        rendered = str(value or '')
        rendered = rendered.replace('\\:', ':')
        rendered = rendered.replace('\\=', '=')
        rendered = rendered.replace('\\ ', ' ')
        return rendered

    def _load_runtime_parameters(self, parser) -> None:
        """Load project parameter values near the iFlow for placeholder resolution."""
        self._runtime_parameters = {}
        iflow_path = getattr(parser, 'iflow_path', None)
        if not iflow_path:
            return

        try:
            flow_path = Path(iflow_path)
        except Exception:
            return

        if not flow_path.exists():
            return

        candidates: List[Path] = []
        max_depth = min(7, len(flow_path.parents))
        for idx in range(max_depth):
            parent = flow_path.parents[idx]
            candidates.append(parent / 'parameters.prop')
            candidates.append(parent / 'parameters.propdef')

        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                content = candidate.read_text(encoding='utf-8')
            except Exception:
                continue

            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or '=' not in stripped:
                    continue
                key, value = stripped.split('=', 1)
                key = key.replace('\\ ', ' ').strip()
                lookup = self._normalize_lookup_key(key)
                if not lookup:
                    continue
                if lookup not in self._runtime_parameters:
                    self._runtime_parameters[lookup] = self._decode_runtime_value(value.strip())

    def _properties_to_map(self, properties: List[List[str]]) -> Dict[str, str]:
        """Convert list-based key/value properties to a normalized dictionary."""
        normalized: Dict[str, str] = {}
        for key, value in properties:
            lookup = self._normalize_lookup_key(str(key or '').strip())
            if not lookup:
                continue
            rendered = self._resolve_runtime_placeholders(str(value or '').strip())
            if lookup not in normalized:
                normalized[lookup] = rendered
            elif not normalized[lookup] and rendered:
                normalized[lookup] = rendered
        return normalized

    def _pick_property(self, prop_map: Dict[str, str], keys: List[str]) -> str:
        """Pick first non-empty property value from normalized keys."""
        for key in keys:
            lookup = self._normalize_lookup_key(key)
            if not lookup:
                continue
            value = prop_map.get(lookup, '').strip()
            if value:
                return value
        return ""

    def _pick_property_with_key(self, prop_map: Dict[str, str], keys: List[str]) -> Tuple[str, str]:
        """Pick first non-empty property and return normalized key + value."""
        for key in keys:
            lookup = self._normalize_lookup_key(key)
            if not lookup:
                continue
            value = prop_map.get(lookup, '').strip()
            if value:
                return lookup, value
        return '', ''

    def _enrich_variant_properties(self, prop_map: Dict[str, str]) -> None:
        """Derive adapter details from cmdVariantUri when explicit keys are missing."""
        variant_uri = self._pick_property(prop_map, ['cmd variant uri', 'cmdvarianturi'])
        if not variant_uri:
            return

        parts: Dict[str, str] = {}
        for segment in variant_uri.split('/'):
            if '::' not in segment:
                continue
            seg_key, seg_value = segment.split('::', 1)
            key_norm = self._normalize_lookup_key(seg_key)
            if key_norm and seg_value:
                parts[key_norm] = seg_value.strip()

        cname = parts.get('cname', '').strip()
        if cname and 'componenttype' not in prop_map:
            prop_map['componenttype'] = cname.split(':')[-1]

        tp = parts.get('tp', '').strip()
        if tp and 'transportprotocol' not in prop_map:
            prop_map['transportprotocol'] = tp

        mp = parts.get('mp', '').strip()
        if mp and 'messageprotocol' not in prop_map:
            prop_map['messageprotocol'] = mp

        vendor = parts.get('vendor', '').strip()
        if vendor and 'vendor' not in prop_map:
            prop_map['vendor'] = vendor

        version = parts.get('version', '').strip()
        if version and 'adapterversion' not in prop_map:
            prop_map['adapterversion'] = version

        direction = parts.get('direction', '').strip()
        if direction and 'direction' not in prop_map:
            prop_map['direction'] = direction

    def _build_adapter_panel(self, properties: List[List[str]], direction: str) -> Dict[str, Any]:
        """Build sender/receiver side-panel title and rows from adapter properties."""
        prop_map = self._properties_to_map(properties)
        self._enrich_variant_properties(prop_map)

        adapter_name = self._pick_property(prop_map, ['component type', 'adapter type', 'name', 'message protocol'])
        system_name = self._pick_property(prop_map, ['system'])
        direction_key = direction.lower()

        rows: List[Tuple[str, str]] = []
        used_keys: set[str] = set()

        def add_row(label: str, keys: List[str]) -> None:
            picked_key, picked_value = self._pick_property_with_key(prop_map, keys)
            if picked_key and picked_value:
                rows.append((label, picked_value))
                used_keys.add(picked_key)

        if direction_key == 'sender':
            title = f"Sender Adapter ({adapter_name})" if adapter_name else "Sender Adapter"
            subtitle = system_name if system_name else "Not configured"
            subtitle_label = 'System'
            add_row('Adapter Type', ['component type', 'adapter type', 'name'])
            add_row('Address', ['address', 'url path', 'urlpath', 'endpoint address', 'path'])
            add_row('Service Definition', ['service definition', 'service interface', 'service'])
            add_row('Transport Protocol', ['transport protocol', 'protocol'])
            add_row('Use WS-Addressing', ['use ws-addressing', 'use ws addressing', 'usewsaddressing', 'use w s addressing'])
            add_row('Message Exchange Pattern', ['message exchange pattern', 'message exchange'])
            add_row('Sender Auth Type', ['sender auth type', 'authorization', 'authentication'])
            add_row('User Role', ['user role'])
            add_row('Quality Of Service', ['quality of service', 'qos'])
        else:
            receiver_name = self._pick_property(prop_map, ['name']) or self.iflow_name
            receiver_id = self._pick_property(prop_map, ['id']) or self.iflow_name
            title = f"Receiver Adapter ({adapter_name})" if adapter_name else "Receiver Configuration"
            subtitle = system_name if system_name else "Integration Flow"
            subtitle_label = 'Context'
            rows.append(('Name', receiver_name))
            rows.append(('ID', receiver_id))
            add_row('Description', ['description'])
            add_row('Adapter Type', ['component type', 'adapter type', 'name'])
            add_row('Address', ['address', 'url path', 'urlpath', 'endpoint address'])
            add_row('Authentication Type', ['authentication'])
            add_row(
                'Credential / Security Artifact',
                ['credential name', 'user name token credential name', 'wsdl user name token credential name'],
            )
            add_row('Message Protocol', ['message protocol'])
            add_row('Transport Protocol', ['transport protocol', 'protocol'])
            add_row('Operation', ['operation name', 'operation', 's3 receiver operation'])
            add_row('Bucket Name', ['s3 receiver bucket name', 'bucket name', 'bucketname'])

        skip_keys = {
            self._normalize_lookup_key(name)
            for name in [
                'direction',
                'cmd variant uri',
                'component version',
                'message protocol version',
                'transport protocol version',
                'component swcv id',
                'component swcv name',
                'component ns',
                'component id',
                'vendor',
            ]
        }

        if len(rows) < 9:
            for key, value in properties:
                if len(rows) >= 9:
                    break
                lookup = self._normalize_lookup_key(str(key or '').strip())
                if not lookup or lookup in used_keys or lookup in skip_keys:
                    continue
                rendered = self._resolve_runtime_placeholders(str(value or '').strip())
                if rendered:
                    key_label = self._truncate_label(str(key), max_len=20)
                    rows.append((key_label, rendered))
                    used_keys.add(lookup)

        if not rows:
            rows = [('Status', 'No adapter details found')]

        return {
            'title': title,
            'subtitle': subtitle,
            'subtitle_label': subtitle_label,
            'rows': rows[:9],
        }

    def _wrap_panel_text(self, value: str, width: int, max_lines: int) -> List[str]:
        """Wrap panel text into multiple lines while keeping compact row height."""
        normalized = str(value or '').replace('\n', ' ').strip()
        if not normalized:
            return [""]

        lines = textwrap.wrap(
            normalized,
            width=max(6, width),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [normalized]

        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self._truncate_label(lines[-1], max_len=max(6, width))

        return lines

    def _draw_adapter_side_panel(
        self,
        ax,
        x: float,
        y: float,
        width: float,
        panel_data: Dict[str, Any],
    ):
        """Draw adapter details panel in side whitespace region."""
        rows: List[Tuple[str, str]] = panel_data.get('rows', [])
        title = str(panel_data.get('title', 'Adapter'))
        subtitle = str(panel_data.get('subtitle', ''))
        subtitle_label = str(panel_data.get('subtitle_label', 'System'))

        title_h = 18.0
        subtitle_h = 13.0
        row_line_h = 8.5
        row_padding = 3.6

        y_limits = ax.get_ylim()
        axis_top = min(y_limits)
        axis_bottom = max(y_limits)

        content_x = x + 4
        content_width_chars = max(14, int((width - 12.0) / 4.9))
        approx_label_chars = max(10, content_width_chars)
        approx_value_chars = max(10, content_width_chars - 2)

        prepared_rows: List[Dict[str, Any]] = []
        for label, value in rows:
            label_lines = self._wrap_panel_text(str(label), width=approx_label_chars, max_lines=3)
            value_lines = self._wrap_panel_text(str(value), width=approx_value_chars, max_lines=3)
            line_count = len(label_lines) + len(value_lines)
            prepared_rows.append(
                {
                    'label_lines': label_lines,
                    'value_lines': value_lines,
                    'line_count': line_count,
                }
            )

        body_h = sum((row['line_count'] * row_line_h) + row_padding for row in prepared_rows)
        panel_h = max(154.0, title_h + subtitle_h + 10.0 + body_h + 7.0)

        y = min(max(y, axis_top + 4.0), axis_bottom - panel_h - 4.0)

        panel = FancyBboxPatch(
            (x, y), width, panel_h,
            boxstyle='round,pad=0.02,rounding_size=4',
            facecolor='#FFFFFF', edgecolor='#8C9FB5', linewidth=1.1, zorder=9
        )
        ax.add_patch(panel)

        header = Rectangle(
            (x, y), width, title_h,
            facecolor='#E8F2FC', edgecolor='#8C9FB5', linewidth=0.8, zorder=10
        )
        ax.add_patch(header)

        title_text = ax.text(
            x + 4,
            y + (title_h / 2),
            self._truncate_label(title, max_len=42),
            ha='left',
            va='center',
            fontsize=8.5,
            fontweight='bold',
            color='#2A4A70',
            zorder=11,
        )
        title_text.set_clip_path(panel)

        subtitle_lines = self._wrap_panel_text(
            f"{subtitle_label}: {subtitle}",
            width=max(18, int((width - 10.0) / 4.2)),
            max_lines=2,
        )
        subtitle_text = ax.text(
            x + 4,
            y + title_h + 2.6,
            "\n".join(subtitle_lines),
            ha='left',
            va='top',
            fontsize=7.2,
            color='#3F4E5D',
            linespacing=1.1,
            zorder=11,
        )
        subtitle_text.set_clip_path(panel)

        row_cursor_y = y + title_h + subtitle_h + 5.0
        for idx, row in enumerate(prepared_rows):
            if idx > 0:
                sep_y = row_cursor_y - 2.2
                ax.plot([x + 3.0, x + width - 3.0], [sep_y, sep_y], color='#EAF0F6', linewidth=0.6, zorder=10)

            label_text = ax.text(
                content_x,
                row_cursor_y,
                "\n".join(row['label_lines']),
                ha='left',
                va='top',
                fontsize=6.8,
                fontweight='bold',
                color='#334455',
                linespacing=1.1,
                clip_on=True,
                zorder=11,
            )

            value_start_y = row_cursor_y + (len(row['label_lines']) * row_line_h)
            value_text = ax.text(
                content_x + 8.0,
                value_start_y,
                "\n".join(row['value_lines']),
                ha='left',
                va='top',
                fontsize=6.8,
                color='#334455',
                linespacing=1.1,
                clip_on=True,
                zorder=11,
            )
            label_text.set_clip_path(panel)
            value_text.set_clip_path(panel)

            row_cursor_y += (row['line_count'] * row_line_h) + row_padding

    def generate_adapter_panel_diagram(self, properties: List[List[str]], direction: str) -> Optional[bytes]:
        """Generate a standalone sender/receiver configuration panel image."""
        try:
            panel_data = self._build_adapter_panel(properties, direction)
            rows: List[Tuple[str, str]] = panel_data.get('rows', [])
            wrapped_rows: List[List[str]] = []
            for label, value in rows:
                wrapped_rows.append([
                    textwrap.fill(str(label), width=22, break_long_words=False, break_on_hyphens=False),
                    textwrap.fill(str(value), width=30, break_long_words=True, break_on_hyphens=True),
                ])

            row_count = max(1, len(wrapped_rows))
            fig_h = min(8.0, max(3.6, 1.6 + (row_count * 0.55)))
            fig, ax = plt.subplots(1, 1, figsize=(8.1, fig_h))
            ax.set_facecolor(self.WHITE)
            fig.patch.set_facecolor(self.WHITE)
            ax.axis('off')

            title = str(panel_data.get('title', f'{direction} Configuration'))
            subtitle = str(panel_data.get('subtitle', 'Not configured'))
            subtitle_label = str(panel_data.get('subtitle_label', 'Context'))

            ax.text(
                0.05,
                0.95,
                title,
                transform=ax.transAxes,
                ha='left',
                va='top',
                fontsize=16,
                fontweight='bold',
                color='#2A4A70',
            )
            ax.text(
                0.05,
                0.87,
                f"{subtitle_label}: {subtitle}",
                transform=ax.transAxes,
                ha='left',
                va='top',
                fontsize=10.5,
                color='#43576C',
            )

            table = ax.table(
                cellText=wrapped_rows if wrapped_rows else [["Status", "No adapter details found"]],
                colLabels=["Property", "Value"],
                cellLoc='left',
                colLoc='left',
                bbox=[0.05, 0.06, 0.90, 0.72],
                colWidths=[0.34, 0.58],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 1.35)

            for (row_idx, col_idx), cell in table.get_celld().items():
                cell.set_edgecolor('#D7E1EB')
                cell.set_linewidth(0.8)
                if row_idx == 0:
                    cell.set_facecolor('#E8F2FC')
                    cell.set_text_props(weight='bold', color='#2A4A70')
                else:
                    if col_idx == 0:
                        cell.set_text_props(weight='bold', color='#334455')
                    else:
                        cell.set_text_props(color='#334455')
                    cell.set_facecolor('#FFFFFF' if row_idx % 2 == 1 else '#F8FBFE')

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
        except Exception as exc:
            logger.error(f"{direction} adapter panel diagram error: {exc}")
            return None

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
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=1.05,
            linestyle='-',
            solid_capstyle='round',
            solid_joinstyle='round',
            zorder=3,
        )

        arrow = FancyArrowPatch(
            points[-2],
            points[-1],
            arrowstyle='-|>',
            mutation_scale=8.8,
            linewidth=1.05,
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
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=0.95,
            linestyle=(0, (4.2, 3.6)),
            solid_capstyle='round',
            zorder=3,
        )

        start_circle = Circle(points[0], radius=2.4, facecolor=self.WHITE, edgecolor=color, linewidth=0.9, zorder=5)
        ax.add_patch(start_circle)
        self._draw_message_envelope(ax, points[0][0] + 4.6, points[0][1] - 3.0, color=color)
        self._draw_open_arrow_head(ax, points[-2], points[-1], color=color, size=6.7, width=0.95)

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
            self._load_runtime_parameters(parser)
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

            participant_ids = [pid for pid in participants if pid in shapes]
            participant_ids.sort(
                key=lambda pid: shapes[pid]['w'] * shapes[pid]['h'],
                reverse=True,
            )

            process_pool_bounds: Optional[Dict[str, float]] = None
            process_pool_id: Optional[str] = None
            for participant_id in participant_ids:
                info = participants.get(participant_id, {})
                if info.get('process_ref'):
                    bounds = shapes[participant_id]
                    area = bounds['w'] * bounds['h']
                    if process_pool_bounds is None or area > (process_pool_bounds['w'] * process_pool_bounds['h']):
                        process_pool_bounds = bounds
                        process_pool_id = participant_id

            # Move secondary JDBC process cluster left to better match the reference layout.
            if process_pool_id:
                secondary_process_id: Optional[str] = None
                for participant_id in participant_ids:
                    if participant_id == process_pool_id:
                        continue

                    info = participants.get(participant_id, {})
                    if not info.get('process_ref'):
                        continue

                    participant_bounds = shapes.get(participant_id)
                    if not participant_bounds:
                        continue

                    participant_name = str(info.get('name', '')).lower()
                    contains_jdbc = 'jdbc' in participant_name
                    if not contains_jdbc:
                        for element_id, element_bounds in shapes.items():
                            if element_id in participants:
                                continue
                            center_point = (
                                element_bounds['x'] + (element_bounds['w'] / 2.0),
                                element_bounds['y'] + (element_bounds['h'] / 2.0),
                            )
                            if not self._point_inside_bounds(center_point, participant_bounds):
                                continue
                            node_name = str(element_meta.get(element_id, {}).get('name', '')).lower()
                            if 'jdbc' in node_name:
                                contains_jdbc = True
                                break

                    if contains_jdbc:
                        secondary_process_id = participant_id
                        break

                if secondary_process_id:
                    secondary_bounds = dict(shapes[secondary_process_id])
                    cluster_ids: List[str] = [secondary_process_id]
                    for element_id, element_bounds in shapes.items():
                        if element_id == secondary_process_id:
                            continue
                        center_point = (
                            element_bounds['x'] + (element_bounds['w'] / 2.0),
                            element_bounds['y'] + (element_bounds['h'] / 2.0),
                        )
                        if self._point_inside_bounds(center_point, secondary_bounds):
                            cluster_ids.append(element_id)

                    shift_x = -46.0
                    for element_id in cluster_ids:
                        if element_id in shapes:
                            shapes[element_id]['x'] = shapes[element_id]['x'] + shift_x

                    for flow_id, points in list(edges.items()):
                        if not points:
                            continue

                        flow_info = flow_meta.get(flow_id, {})
                        source_id = str(flow_info.get('source_ref', ''))
                        target_id = str(flow_info.get('target_ref', ''))
                        source_in_cluster = source_id in cluster_ids
                        target_in_cluster = target_id in cluster_ids

                        if source_in_cluster and target_in_cluster:
                            edges[flow_id] = [(x + shift_x, y) for x, y in points]
                            continue

                        if source_in_cluster and not target_in_cluster:
                            edges[flow_id] = [
                                (x + shift_x, y) if idx < (len(points) - 1) else (x, y)
                                for idx, (x, y) in enumerate(points)
                            ]
                            continue

                        if target_in_cluster and not source_in_cluster:
                            edges[flow_id] = [
                                (x, y) if idx == 0 else (x + shift_x, y)
                                for idx, (x, y) in enumerate(points)
                            ]
                            continue

                        if any(self._point_inside_bounds(point, secondary_bounds) for point in points):
                            edges[flow_id] = [
                                (x + shift_x, y) if self._point_inside_bounds((x, y), secondary_bounds) else (x, y)
                                for x, y in points
                            ]

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
            canvas_left = min_x - pad
            canvas_right = max_x + pad
            ax.set_xlim(canvas_left, canvas_right)
            ax.set_ylim(max_y + pad, min_y - pad)  # inverted y-axis to match BPMN canvas
            ax.axis('off')

            # Draw pools/participants first.
            for participant_id in participant_ids:
                info = participants.get(participant_id, {})
                bounds = shapes[participant_id]
                x, y, w, h = bounds['x'], bounds['y'], bounds['w'], bounds['h']
                name = str(info.get('name', participant_id)).replace('_', ' ')
                is_process_pool = bool(info.get('process_ref')) or w > 300

                if is_process_pool:
                    pool = Rectangle(
                        (x, y), w, h,
                        facecolor=self.SAP_POOL_BG, edgecolor=self.SAP_POOL_EDGE, linewidth=0.92, zorder=1
                    )
                    ax.add_patch(pool)

                    lane_w = max(22.0, min(34.0, w * 0.05))
                    lane_label = Rectangle(
                        (x, y), lane_w, h,
                        facecolor=self.SAP_LANE_BG, edgecolor=self.SAP_POOL_EDGE, linewidth=0.88, zorder=2
                    )
                    ax.add_patch(lane_label)

                    ax.text(
                        x + lane_w / 2,
                        y + h / 2,
                        self._wrap_label(name, width=14, max_lines=3),
                        rotation=90,
                        ha='center',
                        va='center',
                        fontsize=7.4,
                        color='#4D5A66',
                        zorder=3,
                    )
                else:
                    ext_box = Rectangle(
                        (x, y), w, h,
                        facecolor='#FFFFFF', edgecolor='#C5CED8', linewidth=0.85, zorder=2
                    )
                    ax.add_patch(ext_box)
                    ax.text(
                        x + w / 2,
                        y + h / 2,
                        self._wrap_label(name, width=14, max_lines=3),
                        ha='center',
                        va='center',
                        fontsize=7.2,
                        color='#4C5968',
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
                    lw = 1.6 if 'endevent' in element_type else 1.1
                    event = Circle(
                        (cx, cy), radius,
                        facecolor='#FFFFFF', edgecolor='#5D7F9F', linewidth=lw, zorder=6
                    )
                    ax.add_patch(event)
                    if 'endevent' in element_type:
                        end_inner = Circle((cx, cy), radius * 0.74, facecolor='none', edgecolor='#5D7F9F', linewidth=0.9, zorder=6)
                        ax.add_patch(end_inner)
                    elif 'startevent' in element_type:
                        start_inner = Circle((cx, cy), radius * 0.18, facecolor='#5D7F9F', edgecolor='none', zorder=7)
                        ax.add_patch(start_inner)
                    ax.text(
                        cx,
                        y + h + 10,
                        self._wrap_label(label, width=12, max_lines=2),
                        ha='center',
                        va='top',
                        fontsize=7.1,
                        color='#49657F',
                        zorder=7,
                    )
                    continue

                if 'gateway' in element_type:
                    diamond = patches.Polygon(
                        [(cx, y), (x + w, cy), (cx, y + h), (x, cy)],
                        closed=True,
                        facecolor='#FFFFFF', edgecolor='#6A8CAF', linewidth=1.0, zorder=5
                    )
                    ax.add_patch(diamond)
                    self._draw_gateway_marker(ax, cx, cy, element_type)
                    ax.text(
                        cx,
                        y + h + 10,
                        self._truncate_label(label, 22),
                        fontsize=6.9,
                        ha='center',
                        va='top',
                        color='#4A6781',
                        zorder=7,
                    )
                    continue

                if 'subprocess' in element_type:
                    subproc = FancyBboxPatch(
                        (x, y), w, h,
                        boxstyle='round,pad=0.01,rounding_size=6',
                        facecolor='#FAFCFE', edgecolor='#B4C3D1', linewidth=0.95, zorder=4
                    )
                    ax.add_patch(subproc)
                    label_y = y + min(18.0, max(12.0, h * 0.18))
                    ax.text(
                        cx,
                        label_y,
                        self._wrap_label(label, width=max(10, int(w / 7)), max_lines=2),
                        ha='center',
                        va='top',
                        fontsize=7.1,
                        color='#3B556D',
                        zorder=6,
                    )
                    self._draw_collapsed_marker(ax, cx, y + h - 5, w)
                    continue

                # Default task/callActivity/serviceTask style.
                line_w = 1.25 if 'callactivity' in element_type else 1.0
                task = FancyBboxPatch(
                    (x, y), w, h,
                    boxstyle='round,pad=0.01,rounding_size=4.6',
                    facecolor=self.SAP_TASK_FILL, edgecolor=self.SAP_TASK_EDGE, linewidth=line_w, zorder=5
                )
                ax.add_patch(task)
                self._draw_task_corner_icon(ax, x, y)

                ax.text(
                    cx,
                    cy,
                    self._wrap_label(label, width=max(10, int(w / 7)), max_lines=2),
                    ha='center',
                    va='center',
                    fontsize=7.1,
                    color=self.SAP_TEXT,
                    zorder=6,
                )
                self._draw_task_activity_marker(ax, cx, y + h - 3.4, w)

                if 'callactivity' in element_type:
                    self._draw_collapsed_marker(ax, cx, y + h - 5, w)

            # Draw sequence and message edges.
            for flow_id, points in edges.items():
                info = flow_meta.get(flow_id, {'type': 'sequence', 'name': ''})
                is_message = info.get('type') == 'message'
                color = self.SAP_MSG_FLOW if is_message else self.SAP_SEQ_FLOW

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
                        fontsize=6.8,
                        color='#5A738B',
                        ha='center',
                        va='center',
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

        if diagram_type == "sender":
            generator._load_runtime_parameters(parser)
            return generator.generate_adapter_panel_diagram(
                parser.extract_sender_properties(),
                "Sender",
            )

        if diagram_type == "receiver":
            generator._load_runtime_parameters(parser)
            return generator.generate_adapter_panel_diagram(
                parser.extract_receiver_properties(),
                "Receiver",
            )
        
        logger.warning(f"Unknown diagram type: {diagram_type}")
        return None
            
    except Exception as e:
        logger.error(f"Error generating {diagram_type} diagram: {e}")
        return None


def generate_process_diagram_bytes(parser, process: Dict[str, Any]) -> Optional[bytes]:
    """Generate a compact diagram for a single integration/local process."""
    try:
        if not isinstance(process, dict):
            return None

        process_elem = process.get("element")
        if process_elem is None:
            return None

        generator = BPMNDiagramGenerator(parser.iflow_name)
        sequence_flows = parser.extract_sequence_flows_for_process(process_elem)
        return generator.generate_integration_flow_diagram([process], sequence_flows)
    except Exception as e:
        logger.error(f"Error generating process diagram: {e}")
        return None


def extract_exception_subdiagram_bytes(parser, integration_diagram_bytes: bytes) -> Optional[bytes]:
    """
    Copy the exception subprocess area from an existing integration diagram image.

    This keeps the original integration image unchanged and returns a separate
    cropped PNG for re-use in other document sections.
    """
    if not integration_diagram_bytes:
        return None

    try:
        generator = BPMNDiagramGenerator(parser.iflow_name)
        root = parser.get_root()

        element_meta = generator._collect_element_metadata(root)
        participants = generator._collect_participants(root)
        shapes = generator._collect_bpmndi_shapes(root)
        edges = generator._collect_bpmndi_edges(root)

        if not shapes:
            return None

        candidate: Optional[Dict[str, Any]] = None
        for element_id, bounds in shapes.items():
            if element_id in participants:
                continue

            meta = element_meta.get(element_id, {})
            element_type = str(meta.get('type', '')).lower()
            if 'subprocess' not in element_type:
                continue

            name = str(meta.get('name', '')).strip()
            priority = 2 if re.search(r'exception|error', name, re.IGNORECASE) else 1
            area = float(bounds.get('w', 0.0)) * float(bounds.get('h', 0.0))
            sort_key = (priority, area)

            if candidate is None or sort_key > candidate['sort_key']:
                candidate = {'bounds': bounds, 'sort_key': sort_key}

        if candidate is None:
            return None

        sub_bounds = candidate['bounds']

        all_x: List[float] = []
        all_y: List[float] = []
        for bounds in shapes.values():
            all_x.extend([bounds['x'], bounds['x'] + bounds['w']])
            all_y.extend([bounds['y'], bounds['y'] + bounds['h']])
        for points in edges.values():
            all_x.extend([pt[0] for pt in points])
            all_y.extend([pt[1] for pt in points])

        if not all_x or not all_y:
            return None

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        diagram_w = max(max_x - min_x, 1.0)
        diagram_h = max(max_y - min_y, 1.0)

        pad = max(20.0, min(32.0, max(diagram_w, diagram_h) * 0.03))
        canvas_left = min_x - pad
        canvas_right = max_x + pad
        canvas_top = min_y - pad
        canvas_bottom = max_y + pad

        margin_x = max(24.0, sub_bounds['w'] * 0.11)
        margin_y = max(22.0, sub_bounds['h'] * 0.18)

        x_left = max(canvas_left, sub_bounds['x'] - margin_x)
        x_right = min(canvas_right, sub_bounds['x'] + sub_bounds['w'] + margin_x)
        y_top = max(canvas_top, sub_bounds['y'] - margin_y)
        y_bottom = min(canvas_bottom, sub_bounds['y'] + sub_bounds['h'] + margin_y)

        if x_right <= x_left or y_bottom <= y_top:
            return None

        image = plt.imread(io.BytesIO(integration_diagram_bytes), format='png')
        if image is None or len(getattr(image, 'shape', ())) < 2:
            return None

        img_h = int(image.shape[0])
        img_w = int(image.shape[1])
        if img_h <= 0 or img_w <= 0:
            return None

        span_x = max(canvas_right - canvas_left, 1.0)
        span_y = max(canvas_bottom - canvas_top, 1.0)

        px_left = int((x_left - canvas_left) / span_x * img_w)
        px_right = int((x_right - canvas_left) / span_x * img_w)

        py_top_a = int((y_top - canvas_top) / span_y * img_h)
        py_bottom_a = int((y_bottom - canvas_top) / span_y * img_h)

        py_top_b = int((canvas_bottom - y_bottom) / span_y * img_h)
        py_bottom_b = int((canvas_bottom - y_top) / span_y * img_h)

        def _clamp(v: int, low: int, high: int) -> int:
            return max(low, min(v, high))

        px_left = _clamp(px_left, 0, img_w - 1)
        px_right = _clamp(px_right, 1, img_w)
        if px_right <= px_left:
            return None

        def _crop(y0: int, y1: int):
            y0 = _clamp(y0, 0, img_h - 1)
            y1 = _clamp(y1, 1, img_h)
            if y1 <= y0:
                return None
            return image[y0:y1, px_left:px_right]

        crop_a = _crop(py_top_a, py_bottom_a)
        crop_b = _crop(py_top_b, py_bottom_b)

        def _coverage(crop) -> float:
            if crop is None or crop.size == 0:
                return 0.0
            if len(crop.shape) == 2:
                if str(crop.dtype).startswith('uint'):
                    return float((crop < 247).mean())
                return float((crop < 0.97).mean())

            rgb = crop[..., :3]
            if str(rgb.dtype).startswith('uint'):
                mask = (rgb < 247).any(axis=2)
            else:
                mask = (rgb < 0.97).any(axis=2)
            return float(mask.mean())

        selected = crop_a if _coverage(crop_a) >= _coverage(crop_b) else crop_b
        if selected is None:
            return None

        if int(selected.shape[0]) < 20 or int(selected.shape[1]) < 20:
            return None

        buf = io.BytesIO()
        plt.imsave(buf, selected, format='png')
        buf.seek(0)
        return buf.getvalue()

    except Exception as exc:
        logger.debug(f"Failed to extract exception subprocess crop: {exc}")
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
    
    for dtype in ['integration_flow', 'sender', 'receiver']:
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
