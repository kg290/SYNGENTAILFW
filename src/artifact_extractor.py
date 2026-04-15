"""Artifact Extractor - Extracts and summarizes SAP CPI project artifacts."""
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
import xml.etree.ElementTree as ET


class GroovyExtractor:
    """Extracts information from Groovy script files."""
    
    def __init__(self, groovy_path: Path):
        self.groovy_path = Path(groovy_path)
        self.content: str = ""
    
    def read(self) -> str:
        """Read the Groovy file content."""
        self.content = self.groovy_path.read_text(encoding='utf-8')
        return self.content
    
    def extract_functions(self) -> List[Dict[str, Any]]:
        """Extract function signatures and documentation."""
        if not self.content:
            self.read()
        
        functions = []
        
        # Pattern to match Groovy function definitions
        func_pattern = r'def\s+(\w+)\s*\((.*?)\)\s*\{'
        
        for match in re.finditer(func_pattern, self.content, re.DOTALL):
            func_name = match.group(1)
            params = match.group(2).strip()
            
            # Try to extract preceding comment as documentation
            start_pos = match.start()
            preceding_text = self.content[:start_pos].rstrip()
            doc_comment = ""
            
            if preceding_text.endswith('*/'):
                comment_start = preceding_text.rfind('/*')
                if comment_start != -1:
                    doc_comment = preceding_text[comment_start:].strip()
            
            functions.append({
                'name': func_name,
                'parameters': params,
                'documentation': doc_comment,
                'file': self.groovy_path.name,
            })
        
        return functions
    
    def get_info(self) -> Dict[str, Any]:
        """Get complete information about the Groovy script."""
        if not self.content:
            self.read()
        
        return {
            'file_name': self.groovy_path.name,
            'file_path': str(self.groovy_path),
            'content': self.content,
            'functions': self.extract_functions(),
            'imports': self._extract_imports(),
            'line_count': len(self.content.splitlines()),
        }
    
    def _extract_imports(self) -> List[str]:
        """Extract import statements."""
        imports = []
        for line in self.content.splitlines():
            line = line.strip()
            if line.startswith('import '):
                imports.append(line[7:].rstrip(';'))
        return imports


class SchemaExtractor:
    """Extracts information from XSD schema files."""
    
    def __init__(self, xsd_path: Path):
        self.xsd_path = Path(xsd_path)
        self.content: str = ""
    
    def read(self) -> str:
        """Read the XSD file content."""
        self.content = self.xsd_path.read_text(encoding='utf-8')
        return self.content
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about the schema."""
        if not self.content:
            self.read()

        info = {
            'file_name': self.xsd_path.name,
            'file_path': str(self.xsd_path),
            'elements': [],
            'complex_types': [],
            'target_namespace': '',
        }
        
        try:
            root = ET.fromstring(self.content)

            # Get target namespace
            info['target_namespace'] = root.attrib.get('targetNamespace', '')

            xsd_ns = '{http://www.w3.org/2001/XMLSchema}'

            # Extract elements
            for elem in root.findall(f'.//{xsd_ns}element'):
                info['elements'].append({
                    'name': elem.attrib.get('name', ''),
                    'type': elem.attrib.get('type', ''),
                    'min_occurs': elem.attrib.get('minOccurs', '1'),
                    'max_occurs': elem.attrib.get('maxOccurs', '1'),
                })

            # Extract complex types
            for ct in root.findall(f'.//{xsd_ns}complexType'):
                info['complex_types'].append({
                    'name': ct.attrib.get('name', ''),
                })
        except Exception as e:
            info['parse_error'] = str(e)
        
        return info


class ParameterExtractor:
    """Extracts parameters from .prop and .propdef files."""
    
    def __init__(self, prop_path: Path):
        self.prop_path = Path(prop_path)
    
    def extract(self) -> Dict[str, str]:
        """Extract key-value parameters."""
        params = {}
        
        content = self.prop_path.read_text(encoding='utf-8')
        
        for line in content.splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Handle escaped spaces in keys
            line = line.replace('\\ ', ' ')
            
            if '=' in line:
                key, value = line.split('=', 1)
                params[key.strip()] = value.strip()
        
        return params


TEXT_EXTENSIONS = {
    ".iflw",
    ".xml",
    ".xsd",
    ".wsdl",
    ".xsl",
    ".xslt",
    ".mmap",
    ".groovy",
    ".gsh",
    ".js",
    ".json",
    ".yaml",
    ".yml",
    ".prop",
    ".propdef",
    ".mf",
    ".txt",
    ".md",
    ".csv",
    ".project",
}


def _read_text_with_fallback(path: Path) -> str:
    """Read file text with conservative encoding fallbacks."""
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue

    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_space(text: str) -> str:
    """Normalize whitespace while keeping readable line breaks."""
    compact = text.replace("\r\n", "\n").replace("\r", "\n")
    compact = re.sub(r"[\t ]+", " ", compact)
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def _is_text_candidate(path: Path) -> bool:
    """Return True when file extension strongly indicates text content."""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True

    # Handle extension-less or unusual config-like files.
    return suffix == ""


def _safe_relative(path: Path, root: Optional[Path]) -> str:
    """Return stable relative path for reporting when root is provided."""
    if root is None:
        return str(path)

    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def _categorize_extension(ext: str) -> str:
    """Map file extension to high-level technical category."""
    if ext in {".iflw", ".xml", ".xsd", ".wsdl", ".xsl", ".xslt", ".mmap"}:
        return "integration-definition"
    if ext in {".groovy", ".gsh", ".js"}:
        return "script"
    if ext in {".prop", ".propdef", ".yaml", ".yml", ".json", ".project", ".mf"}:
        return "configuration"
    if ext in {".txt", ".md", ".doc", ".docx", ".rtf"}:
        return "documentation"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico"}:
        return "image"
    if ext in {".zip", ".jar"}:
        return "archive"
    return "other"


def _build_text_preview(content: str, max_chars: int = 700) -> str:
    """Return compact preview text suitable for prompts and appendix tables."""
    normalized = _normalize_space(content)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + " ..."


def _extract_signal_lines(content: str, max_items: int = 8) -> List[str]:
    """Extract meaningful lines likely describing behavior/configuration."""
    lines = [_normalize_space(line) for line in content.splitlines()]
    lines = [line for line in lines if line]

    signal_pattern = re.compile(
        r"(endpoint|address|url|uri|operation|mapping|transform|receiver|sender|auth|"
        r"security|certificate|oauth|retry|exception|schedule|cron|adapter|protocol|"
        r"target|source|namespace|schema)",
        re.IGNORECASE,
    )

    selected: List[str] = []
    seen: set[str] = set()
    for line in lines:
        if len(line) < 8:
            continue
        if signal_pattern.search(line) is None and len(selected) >= 3:
            continue

        key = line.lower()
        if key in seen:
            continue

        seen.add(key)
        selected.append(line)
        if len(selected) >= max_items:
            break

    return selected


def _summarize_file_for_context(
    file_path: Path,
    project_root: Optional[Path],
    max_preview_chars: int,
) -> Optional[Dict[str, Any]]:
    """Read and summarize a single file if it is suitable for text analysis."""
    try:
        stat = file_path.stat()
    except Exception:
        return None

    ext = file_path.suffix.lower()
    if not _is_text_candidate(file_path):
        return None

    # Skip very large files for prompt efficiency.
    if stat.st_size > 2_000_000:
        return None

    try:
        content = _read_text_with_fallback(file_path)
    except Exception:
        return None

    content = content.strip()
    if not content:
        return None

    relative = _safe_relative(file_path, project_root)
    signals = _extract_signal_lines(content)
    preview = _build_text_preview(content, max_preview_chars)

    return {
        "file_name": file_path.name,
        "relative_path": relative,
        "extension": ext or "[no-extension]",
        "category": _categorize_extension(ext),
        "size_bytes": stat.st_size,
        "line_count": len(content.splitlines()),
        "signal_lines": signals,
        "preview": preview,
    }


def _compose_artifact_analysis_context(
    all_files: List[Dict[str, Any]],
    file_type_summary: Dict[str, int],
    text_artifacts: List[Dict[str, Any]],
    max_chars: int = 18000,
) -> str:
    """Compose compact but rich project-file context for AI generation."""
    lines: List[str] = []

    lines.append("Project-wide technical file analysis")
    lines.append(f"Total files discovered: {len(all_files)}")

    if file_type_summary:
        top_ext = sorted(file_type_summary.items(), key=lambda item: (-item[1], item[0]))[:20]
        ext_text = ", ".join([f"{ext}: {count}" for ext, count in top_ext])
        lines.append(f"File-type distribution: {ext_text}")

    if text_artifacts:
        lines.append("Key text artifacts and extracted signals:")
        for artifact in text_artifacts:
            path = artifact.get("relative_path", "")
            ext = artifact.get("extension", "")
            category = artifact.get("category", "")
            lines.append(f"- {path} [{ext}, {category}]")

            signals = artifact.get("signal_lines", [])
            if isinstance(signals, list) and signals:
                for signal in signals[:4]:
                    lines.append(f"  * {signal}")

    context = "\n".join(lines).strip()
    if len(context) <= max_chars:
        return context

    return context[:max_chars].rstrip() + "\n[Artifact analysis context truncated]"


def extract_all_artifacts(
    artifacts: Dict[str, List[Path]],
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extract information from all discovered artifacts and full file inventory."""
    extracted = {
        'groovy_scripts': [],
        'schemas': [],
        'parameters': {},
        'parameter_definitions': {},
        'all_files': [],
        'file_type_summary': {},
        'text_artifacts': [],
        'artifact_analysis_context': '',
    }
    
    # Extract Groovy scripts
    for groovy_path in artifacts.get('groovy', []):
        try:
            extractor = GroovyExtractor(groovy_path)
            extracted['groovy_scripts'].append(extractor.get_info())
        except Exception as e:
            extracted['groovy_scripts'].append({
                'file_name': groovy_path.name,
                'error': str(e),
            })
    
    # Extract XSD schemas
    for xsd_path in artifacts.get('xsd', []):
        try:
            extractor = SchemaExtractor(xsd_path)
            extracted['schemas'].append(extractor.get_info())
        except Exception as e:
            extracted['schemas'].append({
                'file_name': xsd_path.name,
                'error': str(e),
            })
    
    # Extract parameters
    for param_path in artifacts.get('parameters', []):
        try:
            extractor = ParameterExtractor(param_path)
            extracted['parameters'].update(extractor.extract())
        except Exception as e:
            extracted['parameters']['_error'] = str(e)
    
    # Extract parameter definitions
    for propdef_path in artifacts.get('paramdef', []):
        try:
            extractor = ParameterExtractor(propdef_path)
            extracted['parameter_definitions'].update(extractor.extract())
        except Exception as e:
            extracted['parameter_definitions']['_error'] = str(e)

    all_files: List[Path] = []
    if artifacts.get('all_files'):
        all_files = sorted(artifacts['all_files'], key=lambda p: str(p).lower())
    else:
        seen: set[Path] = set()
        for paths in artifacts.values():
            for path in paths:
                if path.is_file() and path not in seen:
                    seen.add(path)
                    all_files.append(path)
        all_files.sort(key=lambda p: str(p).lower())

    extension_counter: Counter[str] = Counter()
    all_file_rows: List[Dict[str, Any]] = []
    text_artifacts: List[Dict[str, Any]] = []

    for file_path in all_files:
        ext = file_path.suffix.lower() or '[no-extension]'
        extension_counter[ext] += 1

        try:
            stat = file_path.stat()
            size_bytes = stat.st_size
        except Exception:
            size_bytes = 0

        rel_path = _safe_relative(file_path, project_root)
        all_file_rows.append({
            'file_name': file_path.name,
            'relative_path': rel_path,
            'extension': ext,
            'category': _categorize_extension(file_path.suffix.lower()),
            'size_bytes': size_bytes,
        })

        summary = _summarize_file_for_context(
            file_path=file_path,
            project_root=project_root,
            max_preview_chars=600,
        )
        if summary:
            text_artifacts.append(summary)

    extracted['all_files'] = all_file_rows
    extracted['file_type_summary'] = dict(
        sorted(extension_counter.items(), key=lambda item: (-item[1], item[0]))
    )

    # Keep AI prompt efficient while still representing all artifact types.
    text_artifacts = sorted(
        text_artifacts,
        key=lambda item: (item.get('category', ''), item.get('relative_path', '')),
    )
    extracted['text_artifacts'] = text_artifacts[:80]
    extracted['artifact_analysis_context'] = _compose_artifact_analysis_context(
        all_files=all_file_rows,
        file_type_summary=extracted['file_type_summary'],
        text_artifacts=extracted['text_artifacts'],
    )
    
    return extracted
