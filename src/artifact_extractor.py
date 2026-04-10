"""Artifact Extractor - Extracts Groovy scripts, schemas, and parameters."""
from pathlib import Path
from typing import Dict, List, Any
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


def extract_all_artifacts(artifacts: Dict[str, List[Path]]) -> Dict[str, Any]:
    """Extract information from all discovered artifacts."""
    extracted = {
        'groovy_scripts': [],
        'schemas': [],
        'parameters': {},
        'parameter_definitions': {},
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
    
    return extracted
