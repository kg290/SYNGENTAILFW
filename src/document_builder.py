"""
Document Builder - Enterprise-Grade SAP CPI Technical Specification Generator.

Features:
- Professional enterprise document formatting
- BPMN-style diagram integration
- Colored tables with proper spacing
- Clean cover page
- Table of contents
- Proper headers and footers
- Professional typography
- Production-ready output
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
import logging
import io
import re

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import OUTPUT_DIR, DOC_AUTHOR, DOC_VERSION, ENABLE_BATCH_MODE

logger = logging.getLogger(__name__)


class DocumentBuilderError(Exception):
    """Custom exception for document building errors."""
    pass


class EnterpriseDocumentBuilder:
    """Creates enterprise-grade Word documents for SAP CPI technical specs."""
    
    # Professional color palette
    PRIMARY_BLUE = RGBColor(0, 82, 147)
    SECONDARY_BLUE = RGBColor(0, 120, 180)
    DARK_TEXT = RGBColor(33, 37, 41)
    MUTED_TEXT = RGBColor(108, 117, 125)
    TABLE_HEADER_BG = "005293"
    TABLE_ALT_ROW = "F5F8FA"
    
    def __init__(self, iflow_name: str, output_dir: Optional[Path] = None):
        self.iflow_name = iflow_name
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(exist_ok=True)
        self.doc = Document()
        self._setup_page()
        self._setup_header_footer()
        # Keep field updates manual to avoid Word's update-fields prompt on open.
    
    def _setup_page(self):
        """Configure page layout."""
        section = self.doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1)

    def _append_field(self, paragraph, instruction: str, default_text: str = ""):
        """Append a Word field code to a paragraph."""
        run = paragraph.add_run()
        fld_char_begin = OxmlElement('w:fldChar')
        fld_char_begin.set(qn('w:fldCharType'), 'begin')

        instr_text = OxmlElement('w:instrText')
        instr_text.set(qn('xml:space'), 'preserve')
        instr_text.text = instruction

        fld_char_sep = OxmlElement('w:fldChar')
        fld_char_sep.set(qn('w:fldCharType'), 'separate')

        fld_char_end = OxmlElement('w:fldChar')
        fld_char_end.set(qn('w:fldCharType'), 'end')

        run._r.append(fld_char_begin)
        run._r.append(instr_text)
        run._r.append(fld_char_sep)
        if default_text:
            run._r.append(OxmlElement('w:t'))
            run._r[-1].text = default_text
        run._r.append(fld_char_end)

    def _setup_header_footer(self):
        """Add a professional header and page numbers."""
        section = self.doc.sections[0]

        header = section.header
        header_para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        header_para.text = f"{self.iflow_name} - Technical Specification"
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in header_para.runs:
            run.font.name = 'Calibri'
            run.font.size = Pt(9)
            run.font.color.rgb = self.MUTED_TEXT

        footer = section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_para.add_run("Page ")
        self._append_field(footer_para, "PAGE")
        footer_para.add_run(" of ")
        self._append_field(footer_para, "NUMPAGES")

        for run in footer_para.runs:
            run.font.name = 'Calibri'
            run.font.size = Pt(9)
            run.font.color.rgb = self.MUTED_TEXT

    def _enable_auto_field_updates(self):
        """Ask Word to update fields (like TOC and page numbers) on open."""
        settings = self.doc.settings.element
        update_fields = settings.find(qn('w:updateFields'))
        if update_fields is None:
            update_fields = OxmlElement('w:updateFields')
            settings.append(update_fields)
        update_fields.set(qn('w:val'), 'true')
    
    def _set_cell_shading(self, cell, color_hex: str):
        """Set background color for a table cell."""
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), color_hex)
        cell._tc.get_or_add_tcPr().append(shading)

    def _set_repeat_table_header(self, row):
        """Repeat table header row when a table spans multiple pages."""
        tr_pr = row._tr.get_or_add_trPr()
        tbl_header = OxmlElement('w:tblHeader')
        tbl_header.set(qn('w:val'), 'true')
        tr_pr.append(tbl_header)

    def _set_row_cant_split(self, row):
        """Prevent a table row from being split across pages."""
        tr_pr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement('w:cantSplit')
        tr_pr.append(cant_split)

    @staticmethod
    def _strip_markdown_inline(text: str) -> str:
        """Remove simple markdown formatting artifacts from generated prose."""
        if text is None:
            return ""

        cleaned = str(text)

        # [label](url) -> label
        cleaned = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', cleaned)
        # **bold** / __bold__ -> bold
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'__(.*?)__', r'\1', cleaned)
        # *italic* / _italic_ -> italic (only around words)
        cleaned = re.sub(r'(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)', r'\1', cleaned)
        # inline code
        cleaned = cleaned.replace('`', '')

        return cleaned.strip()
    
    def add_cover_page(self):
        """Add professional cover page."""
        # Top spacing
        for _ in range(4):
            self.doc.add_paragraph()
        
        # Main title
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("SAP Integration Suite")
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.name = 'Calibri Light'
        run.font.color.rgb = self.PRIMARY_BLUE
        
        # Subtitle
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("Cloud Integration")
        run.font.size = Pt(24)
        run.font.name = 'Calibri Light'
        run.font.color.rgb = self.SECONDARY_BLUE
        
        # Spacing
        for _ in range(2):
            self.doc.add_paragraph()
        
        # Document type
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("Technical Specification Document")
        run.font.size = Pt(18)
        run.font.name = 'Calibri'
        run.font.italic = True
        run.font.color.rgb = self.MUTED_TEXT
        
        # Spacing
        for _ in range(2):
            self.doc.add_paragraph()
        
        # iFlow name
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(self.iflow_name)
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.name = 'Calibri'
        run.font.color.rgb = self.DARK_TEXT
        
        # More spacing
        for _ in range(8):
            self.doc.add_paragraph()
        
        # Metadata table
        table = self.doc.add_table(rows=4, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        meta = [
            ("Version:", DOC_VERSION),
            ("Author:", DOC_AUTHOR),
            ("Date:", datetime.today().strftime("%B %d, %Y")),
            ("Status:", "Draft")
        ]
        
        for i, (key, val) in enumerate(meta):
            table.rows[i].cells[0].text = key
            table.rows[i].cells[1].text = val
            for para in table.rows[i].cells[0].paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                for r in para.runs:
                    r.bold = True
                    r.font.color.rgb = self.MUTED_TEXT
        
        self.doc.add_page_break()
    
    def add_toc_placeholder(self, entries: Optional[List[str]] = None):
        """Add a static table of contents without Word TOC field prompts."""
        h = self.doc.add_heading("Table of Contents", level=1)
        for run in h.runs:
            run.font.color.rgb = self.PRIMARY_BLUE

        toc_entries = entries or []
        if not toc_entries:
            self.add_paragraph("Sections will be listed in the document body.")
            self.doc.add_page_break()
            return

        for raw_entry in toc_entries:
            entry = self._strip_markdown_inline(raw_entry)
            if not entry:
                continue

            level_match = re.match(r"^(\d+)\.(\d+)\b", entry)
            indent_level = 1 if level_match else 0

            para = self.doc.add_paragraph(entry)
            para.paragraph_format.left_indent = Inches(0.28 * indent_level)
            para.paragraph_format.space_after = Pt(4)
            for run in para.runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(11)
                run.font.color.rgb = self.DARK_TEXT
        
        self.doc.add_page_break()
    
    def add_heading(self, text: str, level: int = 1):
        """Add heading with styling."""
        h = self.doc.add_heading(text, level=min(level, 4))
        h.paragraph_format.keep_with_next = True
        h.paragraph_format.keep_together = True
        for run in h.runs:
            run.font.name = 'Calibri Light'
            if level == 1:
                run.font.size = Pt(18)
                run.font.color.rgb = self.PRIMARY_BLUE
            elif level == 2:
                run.font.size = Pt(14)
                run.font.color.rgb = self.SECONDARY_BLUE
            else:
                run.font.size = Pt(12)
                run.font.color.rgb = self.DARK_TEXT
        return h
    
    def add_paragraph(self, text: str, bold: bool = False, italic: bool = False):
        """Add paragraph."""
        p = self.doc.add_paragraph()
        run = p.add_run(self._strip_markdown_inline(text))
        run.bold = bold
        run.italic = italic
        run.font.name = 'Calibri'
        run.font.size = Pt(11)
        run.font.color.rgb = self.DARK_TEXT
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.15
        return p
    
    def add_bullet_list(self, items: List[str]):
        """Add bullet list."""
        for item in items:
            p = self.doc.add_paragraph(self._strip_markdown_inline(item), style='List Bullet')
            for run in p.runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(11)

    def add_numbered_list(self, items: List[str]):
        """Add numbered list."""
        for item in items:
            text = self._strip_markdown_inline(str(item).strip())
            if not text:
                continue
            p = self.doc.add_paragraph(text, style='List Number')
            for run in p.runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(11)

    def add_numbered_steps_from_text(self, text: str) -> bool:
        """Split text like '1. ... 2. ...' into a real numbered list."""
        compact = re.sub(r"\s+", " ", self._strip_markdown_inline(str(text))).strip()
        if not compact:
            return False

        matches = re.findall(r'(?:^|\s)(\d{1,2})[\.)]\s+(.*?)(?=(?:\s+\d{1,2}[\.)]\s+)|$)', compact)
        if len(matches) < 2:
            return False

        items = [m[1].strip() for m in matches if m[1].strip()]
        if len(items) < 2:
            return False

        self.add_numbered_list(items)
        return True
    
    def add_table(self, headers: List[str], rows: List[List[str]], caption: Optional[str] = None):
        """Add professional table with header styling."""
        if not headers:
            return

        num_cols = len(headers)
        normalized_rows: List[List[str]] = []
        for row_data in rows:
            if row_data is None:
                continue
            cells = [str(cell).strip() if cell is not None else "" for cell in row_data]
            if len(cells) < num_cols:
                cells.extend([""] * (num_cols - len(cells)))
            elif len(cells) > num_cols:
                cells = cells[:num_cols]

            if any(cells):
                normalized_rows.append(cells)

        if not normalized_rows:
            if caption:
                p = self.add_paragraph(f"Table: {caption}", bold=True)
                p.paragraph_format.space_after = Pt(4)
            self.add_paragraph("No data available.", italic=True)
            return
        
        if caption:
            p = self.add_paragraph(f"Table: {caption}", bold=True)
            p.paragraph_format.space_after = Pt(4)
        
        table = self.doc.add_table(rows=1, cols=num_cols)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        table.autofit = False

        width_map = {
            2: [Cm(5.5), Cm(10.2)],
            3: [Cm(4.0), Cm(5.0), Cm(6.7)],
            4: [Cm(3.2), Cm(4.0), Cm(4.0), Cm(4.5)],
        }
        column_widths = width_map.get(num_cols)
        if column_widths:
            for idx, width in enumerate(column_widths):
                table.columns[idx].width = width
        
        # Header row
        hdr_row = table.rows[0]
        self._set_repeat_table_header(hdr_row)
        self._set_row_cant_split(hdr_row)
        for i, hdr_text in enumerate(headers):
            cell = hdr_row.cells[i]
            cell.text = hdr_text
            if column_widths:
                cell.width = column_widths[i]
            self._set_cell_shading(cell, self.TABLE_HEADER_BG)
            for para in cell.paragraphs:
                para.paragraph_format.keep_with_next = True
                for run in para.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.font.size = Pt(10)
                    run.font.name = 'Calibri'
        
        # Data rows
        for row_idx, row_data in enumerate(normalized_rows):
            row = table.add_row()
            self._set_row_cant_split(row)
            for i, cell_text in enumerate(row_data):
                if i < num_cols:
                    cell = row.cells[i]
                    cell.text = self._strip_markdown_inline(str(cell_text)) if cell_text else ""
                    if column_widths:
                        cell.width = column_widths[i]
                    if row_idx % 2 == 1:
                        self._set_cell_shading(cell, self.TABLE_ALT_ROW)
                    for para in cell.paragraphs:
                        for run in para.runs:
                            run.font.size = Pt(10)
                            run.font.name = 'Calibri'
        
        self.doc.add_paragraph()
    
    def add_code_block(self, code: str, language: str = "", max_lines: int = 40):
        """Add code block."""
        if language:
            p = self.add_paragraph(f"[{language}]", italic=True)
            p.paragraph_format.space_after = Pt(2)
        
        lines = code.strip().split('\n')
        if len(lines) > max_lines:
            code = '\n'.join(lines[:max_lines]) + f"\n\n... [{len(lines) - max_lines} more lines]"
        
        p = self.doc.add_paragraph()
        run = p.add_run(code)
        run.font.name = 'Consolas'
        run.font.size = Pt(9)
        p.paragraph_format.left_indent = Inches(0.25)
    
    def add_image(self, image_bytes: bytes, width: float = 6.0, caption: Optional[str] = None):
        """Add image from bytes."""
        try:
            img_stream = io.BytesIO(image_bytes)
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(img_stream, width=Inches(width))
            
            if caption:
                cap = self.doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = cap.add_run(f"Figure: {caption}")
                run.font.size = Pt(10)
                run.font.italic = True
                run.font.color.rgb = self.MUTED_TEXT
            
            self.doc.add_paragraph()
        except Exception as e:
            logger.error(f"Failed to add image: {e}")
            self.add_paragraph(f"[Image could not be loaded: {caption}]", italic=True)
    
    def add_page_break(self):
        """Add page break."""
        self.doc.add_page_break()
    
    def save(self, filename: Optional[str] = None) -> Path:
        """Save document."""
        if filename is None:
            safe_name = "".join(c for c in self.iflow_name if c.isalnum() or c in "._- ")
            filename = f"{safe_name}_TechSpec.docx"
        
        output_path = self.output_dir / filename
        self.doc.save(str(output_path))
        logger.info(f"Document saved: {output_path}")
        return output_path


def build_specification_document(
    parser,
    ai_generator,
    groovy_scripts: List[Dict[str, Any]],
    schemas: Optional[List[Dict[str, Any]]] = None,
    parameters: Optional[Dict[str, str]] = None,
    parameter_definitions: Optional[Dict[str, str]] = None,
    output_dir: Optional[Path] = None,
    include_diagrams: bool = True,
    functional_spec_context: str = "",
) -> Path:
    """Build a detailed enterprise specification document."""

    schemas = schemas or []
    parameters = parameters or {}
    parameter_definitions = parameter_definitions or {}

    iflow_name = parser.iflow_name
    all_processes = parser.get_integration_processes()
    message_flows = parser.extract_message_flows_with_names()
    sequence_flows = parser.extract_sequence_flows_with_names()
    sender_props = parser.extract_sender_properties()
    receiver_props = parser.extract_receiver_properties()
    mapping_props = parser.extract_mapping_properties()
    security_props = parser.extract_security_properties()
    exception_props = parser.extract_exception_properties()
    metadata = parser.extract_metadata()

    builder = EnterpriseDocumentBuilder(iflow_name, output_dir)

    print("\n" + "=" * 70)
    print("  SAP CPI Technical Specification Generator")
    print("=" * 70)
    print(f"  iFlow: {iflow_name}")
    print(f"  Processes: {len(all_processes)}")
    print(f"  Scripts: {len(groovy_scripts)}")
    print(f"  Schemas: {len(schemas)}")
    print(f"  Diagrams: {'Enabled' if include_diagrams else 'Disabled'}")
    print("=" * 70)

    # ========================================================================
    # GENERATE DIAGRAMS
    # ========================================================================
    diagram_bytes: Dict[str, bytes] = {}
    if include_diagrams:
        print("\n🎨 Generating diagrams...")
        try:
            from src.diagram_generator import generate_diagram_bytes

            for dtype in ['integration_flow']:
                print(f"   • {dtype.replace('_', ' ').title()}...", end=" ")
                try:
                    img = generate_diagram_bytes(parser, dtype)
                    if img:
                        diagram_bytes[dtype] = img
                        print("✅")
                    else:
                        print("⚠️")
                except Exception as e:
                    print(f"❌ {e}")
        except ImportError as e:
            print(f"   ⚠️ Diagrams not available: {e}")

    # ========================================================================
    # BATCH AI GENERATION
    # ========================================================================
    batch: Dict[str, Any] = {}

    if ENABLE_BATCH_MODE and hasattr(ai_generator, 'generate_all_sections_batch'):
        print("\n🚀 Generating AI content...")

        combined_xml = "\n".join([
            parser.extract_collaboration_xml(),
            parser.extract_process_xml(),
            parser.extract_message_flows_xml(),
            parser.sender_props_to_xml(),
            parser.receiver_props_to_xml(),
            parser.mapping_props_to_xml(),
            parser.exception_props_to_xml(),
            parser.metadata_to_xml(),
        ])

        generated = ai_generator.generate_all_sections_batch(
            iflow_name=iflow_name,
            xml_content=combined_xml,
            groovy_scripts=groovy_scripts,
            functional_spec_context=functional_spec_context,
        )

        if isinstance(generated, dict):
            batch = generated
            print("   ✅ AI content generated!")
        else:
            print("   ⚠️ Using fallback mode")

    def value_to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if str(v).strip())
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                rendered = value_to_text(v)
                if rendered:
                    parts.append(f"{k.replace('_', ' ').title()}: {rendered}")
            return "; ".join(parts)
        return str(value)

    def get_text(key: str, default: str = "") -> str:
        if key not in batch:
            return default
        rendered = value_to_text(batch.get(key))
        return rendered if rendered else default

    def get_dict(key: str) -> Dict[str, Any]:
        value = batch.get(key, {})
        return value if isinstance(value, dict) else {}

    def get_list(key: str) -> List[Any]:
        value = batch.get(key, [])
        return value if isinstance(value, list) else []

    ai_stats: Dict[str, Any] = {}
    if hasattr(ai_generator, "get_stats"):
        raw_stats = ai_generator.get_stats()
        if isinstance(raw_stats, dict):
            ai_stats = raw_stats

    assumptions = get_dict("functional_assumptions")
    dependencies_text = get_text("technical_dependencies")
    process_flow_data = get_dict("process_flow")

    def dict_to_rows(data: Dict[str, Any]) -> List[List[str]]:
        rows: List[List[str]] = []
        for k, v in data.items():
            rendered = value_to_text(v)
            if rendered:
                rows.append([k.replace('_', ' ').title(), rendered])
        return rows

    print("\n📄 Building document...")

    # Cover + TOC
    print("   [1/10] Cover Page...")
    builder.add_cover_page()
    print("   [2/10] Table of Contents...")
    toc_entries: List[str] = [
        "1. Change History",
        "1.1 Document Control",
        "2. Overview",
        "2.1 Executive Summary",
        "2.2 Purpose",
        "2.3 Interface Requirement",
    ]
    if assumptions:
        toc_entries.append("2.4 Functional Assumptions")
    toc_entries.extend([
        "2.5 Integration Snapshot",
        "3. High level iFlow Design",
        "3.1 Current Scenario",
        "3.2 To-Be Scenario",
        "3.3 High Level Design",
    ])
    if dependencies_text:
        toc_entries.append("3.4 Technical Dependencies")
    toc_entries.extend([
        "4. Message Flow",
        "4.1 Process Flow",
    ])
    if message_flows:
        toc_entries.append("4.2 Message Flow Connections")
    elif sequence_flows:
        toc_entries.append("4.2 Sequence Flow Connections")
    if 'integration_flow' in diagram_bytes:
        toc_entries.append("4.3 Integration Flow Diagram")
    toc_entries.extend([
        "5. Technical Description",
        "5.1 Main Integration Process",
        "5.2 Local Integration Process",
        "5.3 Sender",
        "5.4 Receiver",
        "5.5 Mappings",
        "5.6 Security",
        "5.7 Groovy Scripts",
        "5.8 Error Handling & Logging",
        "6. Version and Metadata",
        "7. Appendix",
        "7.1 Technical Artifacts",
        "7.2 Schemas",
        "7.3 Runtime Parameters",
        "7.4 Parameter Definitions",
        "7.5 Glossary",
        "7.6 References",
        "7.7 Generation Statistics",
    ])
    builder.add_toc_placeholder(toc_entries)

    # 1. Change History
    print("   [3/10] Change History...")
    builder.add_heading("1. Change History", 1)
    builder.add_table(
        ["Version", "Date", "Author", "Description"],
        [[DOC_VERSION, datetime.today().strftime("%Y-%m-%d"), DOC_AUTHOR, "Initial autogenerated version"]],
    )

    builder.add_heading("1.1 Document Control", 2)
    builder.add_table(
        ["Attribute", "Value"],
        [
            ["Document ID", f"TS-{iflow_name}"],
            ["Integration Flow", iflow_name],
            ["Generated On", datetime.today().strftime("%Y-%m-%d %H:%M")],
            ["Generation Mode", "Batch" if ENABLE_BATCH_MODE else "Section-by-section"],
            ["Diagrams Included", "Yes" if include_diagrams else "No"],
            ["Functional Spec Context", "Provided" if functional_spec_context.strip() else "Not Provided"],
        ],
    )

    # 2. Overview
    print("   [4/10] Overview...")
    builder.add_page_break()
    builder.add_heading("2. Overview", 1)
    builder.add_heading("2.1 Executive Summary", 2)
    builder.add_paragraph(get_text("executive_summary", f"Technical specification for integration flow {iflow_name}."))

    builder.add_heading("2.2 Purpose", 2)
    builder.add_paragraph(get_text("purpose", "This document describes design and implementation details for the integration flow."))

    builder.add_heading("2.3 Interface Requirement", 2)
    builder.add_paragraph(get_text("interface_requirement", "Business requirement is captured through source-to-target system integration."))

    if assumptions:
        builder.add_heading("2.4 Functional Assumptions", 2)
        builder.add_table(["Assumption", "Value"], dict_to_rows(assumptions))

    builder.add_heading("2.5 Integration Snapshot", 2)
    builder.add_table(
        ["Metric", "Value"],
        [
            ["Integration Processes", str(len(all_processes))],
            ["Message Flows", str(len(message_flows))],
            ["Sequence Flows", str(len(sequence_flows))],
            ["Groovy Scripts", str(len(groovy_scripts))],
            ["Schemas", str(len(schemas))],
            ["Runtime Parameters", str(len(parameters))],
        ],
    )

    # 3. High Level iFlow Design
    print("   [5/10] High Level Design...")
    builder.add_page_break()
    builder.add_heading("3. High level iFlow Design", 1)
    builder.add_heading("3.1 Current Scenario", 2)
    builder.add_paragraph(get_text("current_scenario", "Current scenario details are not explicitly configured in the iFlow."))

    builder.add_heading("3.2 To-Be Scenario", 2)
    builder.add_paragraph(get_text("tobe_scenario", "The integration automates message processing between source and target landscapes."))

    builder.add_heading("3.3 High Level Design", 2)
    builder.add_paragraph(get_text("high_level_design", "The integration is implemented using SAP Cloud Integration with adapter-based communication."))

    if dependencies_text:
        builder.add_heading("3.4 Technical Dependencies", 2)
        builder.add_paragraph(dependencies_text)

    # 4. Message Flow
    print("   [6/10] Message Flow...")
    builder.add_page_break()
    builder.add_heading("4. Message Flow", 1)
    technical_flow_text = get_text(
        "technical_flow_description",
        "The message flow follows process-defined sequence flows and message exchanges.",
    )
    if not builder.add_numbered_steps_from_text(technical_flow_text):
        builder.add_paragraph(technical_flow_text)

    if process_flow_data:
        builder.add_heading("4.1 Process Flow", 2)
        steps = process_flow_data.get("steps", []) if isinstance(process_flow_data.get("steps"), list) else []
        if steps:
            builder.add_table(
                ["Step", "Description"],
                [[str(idx + 1), str(step)] for idx, step in enumerate(steps)]
            )
        summary_rows = dict_to_rows({
            "source_system": process_flow_data.get("source_system", ""),
            "target_system": process_flow_data.get("target_system", ""),
            "trigger": process_flow_data.get("trigger", ""),
        })
        if summary_rows:
            builder.add_table(["Flow Attribute", "Value"], summary_rows)

    if message_flows:
        builder.add_heading("4.2 Message Flow Connections", 2)
        builder.add_table(
            ["Source", "Target", "Name"],
            [[src, tgt, name] for src, tgt, name in message_flows],
        )
    elif sequence_flows:
        builder.add_heading("4.2 Sequence Flow Connections", 2)
        builder.add_table(
            ["Source", "Target", "Label"],
            [[src, tgt, name] for src, tgt, name in sequence_flows],
        )

    if 'integration_flow' in diagram_bytes:
        builder.add_heading("4.3 Integration Flow Diagram", 2)
        builder.add_image(diagram_bytes['integration_flow'], width=6.2, caption="Integration Flow Diagram")

    # 5. Technical Description
    print("   [7/10] Technical Description...")
    builder.add_page_break()
    builder.add_heading("5. Technical Description", 1)

    process_ai = {
        str(item.get("name", "")).strip(): item
        for item in get_list("integration_processes")
        if isinstance(item, dict)
    }

    def render_process_block(processes: List[Dict[str, Any]], heading: str):
        builder.add_heading(heading, 2)
        if not processes:
            builder.add_paragraph("No processes available in this section.", italic=True)
            return

        for idx, process in enumerate(processes, start=1):
            proc_name = process.get("name", f"Process {idx}")
            builder.add_heading(proc_name, 3)

            ai_entry = process_ai.get(proc_name, {})
            if ai_entry.get("description"):
                builder.add_paragraph(str(ai_entry.get("description")))

            key_activities = ai_entry.get("key_activities", []) if isinstance(ai_entry.get("key_activities"), list) else []
            if key_activities:
                builder.add_table(["Key Activity"], [[str(activity)] for activity in key_activities])

            steps = ai_entry.get("steps", []) if isinstance(ai_entry.get("steps"), list) else []
            if steps:
                builder.add_table(["Step", "Description"], [[str(i + 1), str(step)] for i, step in enumerate(steps)])

            process_elem = process.get("element")
            if process_elem is None:
                continue

            components = parser.extract_components_from_process(process_elem)
            if components:
                builder.add_table(["Component Name", "Key", "Value"], components)

            child_props = parser.extract_child_properties(process_elem)
            for child in child_props:
                child_heading = child.get("heading", "").strip()
                props = child.get("properties", [])
                if child_heading and props:
                    builder.add_heading(f"{child_heading} Properties", 4)
                    builder.add_table(["Key", "Value"], props)

    main_processes = all_processes[:1]
    local_processes = all_processes[1:]
    render_process_block(main_processes, "5.1 Main Integration Process")
    render_process_block(local_processes, "5.2 Local Integration Process")

    # Sender
    builder.add_heading("5.3 Sender", 2)
    sender_ai = get_dict("sender_details")
    if sender_ai:
        builder.add_table(["Attribute", "Value"], dict_to_rows(sender_ai))
    if sender_props:
        builder.add_table(["Key", "Value"], sender_props)
    else:
        builder.add_paragraph("No sender configuration found.", italic=True)

    # Receiver
    builder.add_heading("5.4 Receiver", 2)
    receiver_ai = get_dict("receiver_details")
    if receiver_ai:
        builder.add_table(["Attribute", "Value"], dict_to_rows(receiver_ai))
    if receiver_props:
        builder.add_table(["Key", "Value"], receiver_props)
    else:
        builder.add_paragraph("No receiver configuration found.", italic=True)

    # Mappings
    builder.add_heading("5.5 Mappings", 2)
    mapping_ai = get_dict("mapping_details")
    if mapping_ai:
        builder.add_table(["Attribute", "Value"], dict_to_rows(mapping_ai))
    if mapping_props:
        for idx, mapping in enumerate(mapping_props, start=1):
            builder.add_heading(f"Mapping Activity {idx} Properties", 3)
            builder.add_table(["Key", "Value"], mapping)
    else:
        builder.add_paragraph("No mapping activities found in this integration flow.", italic=True)

    # Security
    builder.add_heading("5.6 Security", 2)
    security_ai = get_dict("security_config")
    if security_ai:
        builder.add_table(["Security Aspect", "Details"], dict_to_rows(security_ai))
    if security_props:
        builder.add_table(["Key", "Value"], security_props)
    else:
        builder.add_paragraph("No explicit security properties found.", italic=True)

    # Groovy Scripts
    builder.add_heading("5.7 Groovy Scripts", 2)
    groovy_ai = get_dict("groovy_scripts")
    if groovy_ai.get("overview"):
        builder.add_paragraph(str(groovy_ai.get("overview")))

    if groovy_scripts:
        for script in groovy_scripts:
            script_name = script.get("file_name") or script.get("name") or "Script"
            content = script.get("content", "")
            builder.add_heading(f"Script: {script_name}", 3)

            script_meta_rows = dict_to_rows({
                "line_count": script.get("line_count", ""),
                "imports": script.get("imports", []),
                "file_path": script.get("file_path", ""),
            })
            if script_meta_rows:
                builder.add_table(["Key", "Value"], script_meta_rows)

            functions = script.get("functions", []) if isinstance(script.get("functions"), list) else []
            if functions:
                fn_rows = []
                for fn in functions:
                    fn_rows.append([
                        str(fn.get("name", "")),
                        str(fn.get("parameters", "")),
                        str(fn.get("documentation", ""))[:200],
                    ])
                builder.add_table(["Function", "Parameters", "Documentation"], fn_rows)

            if content:
                builder.add_code_block(content, "Groovy", max_lines=60)
    else:
        builder.add_paragraph("No Groovy scripts in this integration flow.", italic=True)

    # Error handling and logging
    builder.add_heading("5.8 Error Handling & Logging", 2)
    error_ai = get_dict("error_handling")
    if error_ai:
        builder.add_table(["Aspect", "Details"], dict_to_rows(error_ai))

    if exception_props:
        for idx, exc in enumerate(exception_props, start=1):
            builder.add_heading(f"Exception SubProcess {idx} Properties", 3)
            sub_rows = exc.get("subproc_props", [])
            if sub_rows:
                builder.add_table(["Key", "Value"], sub_rows)

            for child in exc.get("children", []):
                child_title = f"Child Element: {child.get('tag', '')} {child.get('name', '')}".strip()
                builder.add_heading(child_title, 4)
                if child.get("props"):
                    builder.add_table(["Key", "Value"], child.get("props"))
    else:
        builder.add_paragraph("No exception subprocess configuration found.", italic=True)

    # 6. Version and Metadata
    print("   [8/10] Version and Metadata...")
    builder.add_page_break()
    builder.add_heading("6. Version and Metadata", 1)
    combined_metadata = metadata.copy()
    combined_metadata.update(get_dict("metadata"))
    meta_rows = dict_to_rows(combined_metadata)
    if meta_rows:
        builder.add_table(["Key", "Value"], meta_rows)
    else:
        builder.add_paragraph("No metadata found in the integration flow.", italic=True)

    # 7. Appendix
    print("   [9/10] Appendix...")
    builder.add_page_break()
    builder.add_heading("7. Appendix", 1)
    appendix = get_dict("appendix")

    artifacts = [f"iFlow: {iflow_name}.iflw"]
    artifacts.extend([f"Groovy Script: {s.get('file_name', 'Unknown')}" for s in groovy_scripts])
    artifacts.extend([f"Schema: {s.get('file_name', 'Unknown')}" for s in schemas])
    artifacts.append(f"Message Flows: {len(message_flows)}")
    artifacts.append(f"Sequence Flows: {len(sequence_flows)}")
    artifacts.append(f"Mapping Activities: {len(mapping_props)}")

    appendix_artifacts = appendix.get("artifacts", [])
    if isinstance(appendix_artifacts, list):
        artifacts.extend([str(item) for item in appendix_artifacts])

    builder.add_heading("7.1 Technical Artifacts", 2)
    builder.add_bullet_list(artifacts)

    if schemas:
        builder.add_heading("7.2 Schemas", 2)
        schema_rows = []
        for schema in schemas:
            schema_rows.append([
                str(schema.get("file_name", "")),
                str(schema.get("target_namespace", "")),
                str(len(schema.get("elements", []))) if isinstance(schema.get("elements"), list) else "0",
                str(len(schema.get("complex_types", []))) if isinstance(schema.get("complex_types"), list) else "0",
            ])
        builder.add_table(["File", "Namespace", "Elements", "Complex Types"], schema_rows)

    if parameters:
        builder.add_heading("7.3 Runtime Parameters", 2)
        param_rows = [[str(k), str(v)] for k, v in parameters.items()]
        builder.add_table(["Parameter", "Value"], param_rows)

    if parameter_definitions:
        builder.add_heading("7.4 Parameter Definitions", 2)
        def_rows = [[str(k), str(v)] for k, v in parameter_definitions.items()]
        builder.add_table(["Parameter", "Definition"], def_rows)

    glossary = appendix.get("glossary", []) if isinstance(appendix.get("glossary"), list) else []
    if glossary:
        builder.add_heading("7.5 Glossary", 2)
        builder.add_bullet_list([str(item) for item in glossary])

    references = appendix.get("references", "")
    if references:
        builder.add_heading("7.6 References", 2)
        builder.add_paragraph(str(references))

    if ai_stats:
        builder.add_heading("7.7 Generation Statistics", 2)
        stat_rows = [
            ["API Calls", str(ai_stats.get("api_calls", 0))],
            ["Batch Calls", str(ai_stats.get("batch_calls", 0))],
            ["Cache Hits", str(ai_stats.get("cache_hits", 0))],
            ["Cache Hit Rate", f"{ai_stats.get('cache_hit_rate', 0)}%"],
            ["Failures", str(ai_stats.get("failures", 0))],
        ]
        builder.add_table(["Statistic", "Value"], stat_rows)

    print("   [10/10] Finalizing...")
    output_path = builder.save()

    print("\n" + "=" * 70)
    print(f"  ✅ Document generated: {output_path}")
    print("=" * 70)
    return output_path


# Backward compatibility for older imports
build_specification = build_specification_document
