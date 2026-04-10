"""ZIP Handler Module - Extracts and processes SAP CPI project archives."""
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import tempfile
import logging

logger = logging.getLogger(__name__)


class ZipHandlerError(Exception):
    """Custom exception for ZIP handling errors."""
    pass


class ZipHandler:
    """Handles extraction and artifact discovery from SAP CPI ZIP files."""
    
    SUPPORTED_ARTIFACTS = {
        'iflow': '*.iflw',
        'groovy': '*.groovy',
        'xsd': '*.xsd',
        'parameters': 'parameters.prop',
        'paramdef': 'parameters.propdef',
        'manifest': 'MANIFEST.MF',
        'metainfo': 'metainfo.prop',
        'mapping': '*.mmap',
        'wsdl': '*.wsdl',
        'xml': '*.xml',
    }
    
    def __init__(self, zip_path: str, temp_dir: Optional[Path] = None):
        self.zip_path = Path(zip_path)
        
        if not self.zip_path.exists():
            raise ZipHandlerError(f"ZIP file not found: {self.zip_path}")
        
        if not self.zip_path.suffix.lower() == '.zip':
            raise ZipHandlerError(f"Not a ZIP file: {self.zip_path}")
        
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp(prefix="sap_cpi_"))
        self.extract_dir: Optional[Path] = None
        self.artifacts: Dict[str, List[Path]] = {}
    
    def extract(self) -> Path:
        """Extract ZIP file to temporary directory."""
        self.extract_dir = self.temp_dir / self.zip_path.stem
        self.extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                # Check for suspicious paths (path traversal)
                for name in zf.namelist():
                    if name.startswith('/') or '..' in name:
                        raise ZipHandlerError(f"Suspicious path in ZIP: {name}")
                
                zf.extractall(self.extract_dir)
                logger.debug(f"Extracted {len(zf.namelist())} files to {self.extract_dir}")
        except zipfile.BadZipFile as e:
            raise ZipHandlerError(f"Invalid ZIP file: {e}")
        except Exception as e:
            raise ZipHandlerError(f"Failed to extract ZIP: {e}")
        
        return self.extract_dir
    
    def discover_artifacts(self) -> Dict[str, List[Path]]:
        """Discover all SAP CPI artifacts in extracted directory."""
        if not self.extract_dir:
            self.extract()

        base_dir = self.extract_dir
        if base_dir is None:
            raise ZipHandlerError("Extraction directory is not available")
        
        self.artifacts = {}
        for artifact_type, pattern in self.SUPPORTED_ARTIFACTS.items():
            self.artifacts[artifact_type] = list(base_dir.rglob(pattern))
            if self.artifacts[artifact_type]:
                logger.debug(f"Found {len(self.artifacts[artifact_type])} {artifact_type} file(s)")
        
        return self.artifacts
    
    def get_iflow_path(self) -> Optional[Path]:
        """Get the primary iFlow file path."""
        if 'iflow' not in self.artifacts:
            self.discover_artifacts()
        
        iflows = self.artifacts.get('iflow', [])
        if len(iflows) > 1:
            logger.warning(f"Multiple iFlow files found, using first: {iflows[0].name}")
        
        return iflows[0] if iflows else None
    
    def get_artifact_summary(self) -> Dict[str, int]:
        """Get summary of discovered artifacts."""
        if not self.artifacts:
            self.discover_artifacts()
        
        return {k: len(v) for k, v in self.artifacts.items() if v}
    
    def cleanup(self):
        """Remove temporary extraction directory."""
        if self.extract_dir and self.extract_dir.exists():
            try:
                shutil.rmtree(self.extract_dir, ignore_errors=True)
                logger.debug(f"Cleaned up: {self.extract_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")


def extract_from_directory(directory: Path) -> Dict[str, List[Path]]:
    """Extract artifacts from an already-extracted directory (not ZIP)."""
    directory = Path(directory)
    
    if not directory.exists():
        raise ZipHandlerError(f"Directory not found: {directory}")
    
    if not directory.is_dir():
        raise ZipHandlerError(f"Not a directory: {directory}")
    
    artifacts = {}
    for artifact_type, pattern in ZipHandler.SUPPORTED_ARTIFACTS.items():
        artifacts[artifact_type] = list(directory.rglob(pattern))
    
    return artifacts
