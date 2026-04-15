#!/usr/bin/env python3
"""Unified CLI for SAP CPI specification generation and system operations."""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from config import settings as app_settings
from src.ai_generator import AIGenerator, AIGeneratorError
from src.artifact_extractor import extract_all_artifacts
from src.diagram_generator import generate_iflow_diagrams
from src.document_builder import build_specification_document
from src.functional_spec_parser import (
    discover_functional_spec_path,
    load_functional_spec_context,
)
from src.iflow_parser import IFlowParser
from src.zip_handler import ZipHandler, ZipHandlerError, extract_from_directory

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except Exception:
    Console = None
    RichHandler = None
    Panel = None
    Table = None
    RICH_AVAILABLE = False

try:
    import questionary

    QUESTIONARY_AVAILABLE = True
except Exception:
    questionary = None
    QUESTIONARY_AVAILABLE = False


# Exit codes
EXIT_SUCCESS = 0
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_PROCESSING_ERROR = 3

KNOWN_COMMANDS = {
    "interactive",
    "run",
    "validate",
    "inspect",
    "diagrams",
    "diagnostics",
    "cache",
    "config",
    "inputs",
}


class CLIUI:
    """Small terminal UI helper with rich fallback support."""

    def __init__(self, use_color: bool = True):
        self.use_rich = bool(use_color and RICH_AVAILABLE and Console and Panel and Table)
        self.console: Any | None = Console(highlight=False, soft_wrap=True) if self.use_rich else None

    def banner(self, title: str, subtitle: str = ""):
        """Print a styled command banner."""
        if self.use_rich and self.console is not None and Panel is not None:
            body = title if not subtitle else f"{title}\n{subtitle}"
            self.console.print(Panel(body, border_style="cyan", expand=False))
            return

        line = "=" * max(64, len(title) + 4)
        print(line)
        print(title)
        if subtitle:
            print(subtitle)
        print(line)

    def _print(self, prefix: str, message: str, style: str):
        if self.use_rich and self.console is not None:
            self.console.print(f"{prefix} {message}", style=style)
        else:
            print(f"{prefix} {message}")

    def info(self, message: str):
        self._print("[INFO]", message, "cyan")

    def success(self, message: str):
        self._print("[OK]", message, "green")

    def warning(self, message: str):
        self._print("[WARN]", message, "yellow")

    def error(self, message: str):
        self._print("[ERROR]", message, "bold red")

    def key_values(self, title: str, rows: Iterable[tuple[str, str]]):
        """Render key/value pairs as a table."""
        pairs = [(str(k), str(v)) for k, v in rows]

        if self.use_rich and self.console is not None and Table is not None:
            table = Table(title=title, show_header=False, expand=False)
            table.add_column("Key", style="bold")
            table.add_column("Value")
            for key, value in pairs:
                table.add_row(key, value)
            self.console.print(table)
            return

        print(title)
        for key, value in pairs:
            print(f"  - {key}: {value}")

    def table(self, title: str, headers: list[str], rows: list[list[str]]):
        """Render a generic table."""
        if self.use_rich and self.console is not None and Table is not None:
            table = Table(title=title, expand=False)
            for header in headers:
                table.add_column(header)
            for row in rows:
                table.add_row(*[str(cell) for cell in row])
            self.console.print(table)
            return

        print(title)
        print(" | ".join(headers))
        print("-" * 64)
        for row in rows:
            print(" | ".join([str(cell) for cell in row]))


def setup_logging(verbose: bool, ui: CLIUI) -> logging.Logger:
    """Configure logging with rich output when available."""
    level = logging.DEBUG if verbose else logging.INFO

    if ui.use_rich and ui.console is not None and RichHandler is not None:
        handler = RichHandler(
            console=ui.console,
            show_path=False,
            rich_tracebacks=True,
            markup=False,
        )
        logging.basicConfig(level=level, format="%(message)s", handlers=[handler], force=True)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            force=True,
        )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    return logging.getLogger(__name__)


def validate_input(input_path: Path) -> tuple[bool, str]:
    """Validate input path and return (is_valid, error_message)."""
    if not input_path.exists():
        return False, f"Input path does not exist: {input_path}"

    if input_path.is_file():
        if input_path.suffix.lower() != ".zip":
            return False, f"Input file must be a ZIP archive, got: {input_path.suffix}"
    elif input_path.is_dir():
        iflows = list(input_path.rglob("*.iflw"))
        if not iflows:
            return False, f"No .iflw files found in directory: {input_path}"
    else:
        return False, f"Input must be a file or directory: {input_path}"

    return True, ""


def discover_artifacts(
    input_path: Path,
    logger: logging.Logger,
) -> tuple[dict[str, list[Path]], Path | None, ZipHandler | None]:
    """Discover artifacts and return (artifacts, iflow_path, zip_handler_if_used)."""
    def collect_all_files(root: Path) -> list[Path]:
        return [path for path in root.rglob("*") if path.is_file()]

    zip_handler: ZipHandler | None = None

    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        logger.info("Extracting ZIP file...")
        zip_handler = ZipHandler(str(input_path))
        zip_handler.extract()
        artifacts = zip_handler.discover_artifacts()
        if zip_handler.extract_dir is not None and zip_handler.extract_dir.exists():
            artifacts["all_files"] = collect_all_files(zip_handler.extract_dir)
        iflow_path = zip_handler.get_iflow_path()
        return artifacts, iflow_path, zip_handler

    logger.info("Processing directory...")
    artifacts = extract_from_directory(input_path)
    artifacts["all_files"] = collect_all_files(input_path)
    iflows = artifacts.get("iflow", [])
    iflow_path = iflows[0] if iflows else None
    return artifacts, iflow_path, None


def _safe_relative(path: Path) -> str:
    """Render compact path relative to current working directory when possible."""
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except Exception:
        return str(path)


def _format_bytes(size_bytes: int) -> str:
    """Format byte sizes for human-readable output."""
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB"]

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{int(size_bytes)} B"


def _to_path_or_none(value: str | None) -> Path | None:
    """Convert optional user text into Path or None."""
    if value is None:
        return None

    cleaned = value.strip()
    return Path(cleaned) if cleaned else None


def get_cache_stats() -> dict[str, Any]:
    """Collect cache directory statistics."""
    cache_dir = app_settings.TEMP_DIR / "ai_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[Path, int, float]] = []
    total_size = 0

    for file_path in cache_dir.glob("*.json"):
        if not file_path.is_file():
            continue
        try:
            stat = file_path.stat()
        except OSError:
            continue

        total_size += stat.st_size
        entries.append((file_path, stat.st_size, stat.st_mtime))

    entries.sort(key=lambda item: item[2], reverse=True)
    newest = (
        datetime.fromtimestamp(entries[0][2]).strftime("%Y-%m-%d %H:%M:%S")
        if entries
        else "n/a"
    )

    sample_rows = [
        [
            entry[0].name,
            _format_bytes(entry[1]),
            datetime.fromtimestamp(entry[2]).strftime("%Y-%m-%d %H:%M:%S"),
        ]
        for entry in entries[:5]
    ]

    return {
        "cache_dir": cache_dir,
        "entry_count": len(entries),
        "total_size": total_size,
        "newest": newest,
        "sample_rows": sample_rows,
    }


def clear_cache_files(logger: logging.Logger | None = None) -> int:
    """Clear cached AI response files directly from cache directory."""
    cache_dir = app_settings.TEMP_DIR / "ai_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    removed = 0
    for file_path in cache_dir.glob("*.json"):
        try:
            file_path.unlink()
            removed += 1
        except OSError as exc:
            if logger is not None:
                logger.warning(f"Failed to remove cache file {file_path}: {exc}")

    return removed


def _artifact_rows(artifacts: dict[str, list[Path]]) -> list[list[str]]:
    """Create a stable artifact-count table."""
    order = [
        "iflow",
        "groovy",
        "xsd",
        "mapping",
        "wsdl",
        "parameters",
        "paramdef",
        "manifest",
        "metainfo",
        "xml",
    ]

    rows: list[list[str]] = []
    for key in order:
        rows.append([key, str(len(artifacts.get(key, [])))])

    for key in sorted(artifacts.keys()):
        if key not in order:
            rows.append([key, str(len(artifacts.get(key, [])))])

    return rows


def process_iflow(
    input_path: Path,
    output_dir: Path | None = None,
    functional_spec_path: Path | None = None,
    enable_ai: bool = True,
    logger: logging.Logger | None = None,
) -> Path:
    """
    Process SAP CPI project and generate technical specification.

    Uses enterprise components with diagram generation.
    """
    logger = logger or logging.getLogger(__name__)
    output_dir = output_dir or app_settings.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_handler: ZipHandler | None = None

    try:
        logger.info(f"Processing: {input_path}")
        artifacts, iflow_path, zip_handler = discover_artifacts(input_path, logger)

        project_analysis_root = input_path if input_path.is_dir() else input_path.parent
        if zip_handler is not None and zip_handler.extract_dir is not None:
            project_analysis_root = zip_handler.extract_dir

        logger.info(f"Discovered {len(artifacts.get('all_files', []))} total file(s) for analysis")

        if not iflow_path:
            raise ValueError("No iFlow file (.iflw) found in input")

        logger.info(f"Found iFlow: {iflow_path.name}")
        logger.info(f"Found {len(artifacts.get('groovy', []))} Groovy scripts")
        logger.info(f"Found {len(artifacts.get('xsd', []))} XSD schemas")

        # Step 2: Parse iFlow XML
        logger.info("Parsing iFlow XML...")
        parser = IFlowParser(iflow_path)
        parser.parse()

        processes = parser.get_integration_processes()
        logger.debug(f"Found {len(processes)} integration process(es)")

        # Step 3: Extract artifacts
        logger.info("Extracting artifacts...")
        extracted_artifacts = extract_all_artifacts(
            artifacts,
            project_root=project_analysis_root,
        )
        groovy_scripts = extracted_artifacts.get("groovy_scripts", [])

        # Optional: load functional specification context to enrich AI prompt.
        functional_spec_context = ""
        functional_spec_analysis: dict[str, Any] = {}
        selected_functional_spec = functional_spec_path
        if selected_functional_spec is None:
            discovery_anchor: Path = input_path
            if zip_handler is not None and zip_handler.extract_dir is not None:
                discovery_anchor = zip_handler.extract_dir

            selected_functional_spec = discover_functional_spec_path(discovery_anchor, logger=logger)
            if selected_functional_spec is None and discovery_anchor != input_path:
                selected_functional_spec = discover_functional_spec_path(input_path, logger=logger)

            if selected_functional_spec:
                logger.info(f"Auto-detected functional specification: {selected_functional_spec}")
            else:
                logger.info("No functional specification detected; continuing without it")

        if selected_functional_spec:
            logger.info(f"Loading functional specification input: {selected_functional_spec}")
            spec_result = load_functional_spec_context(
                selected_functional_spec,
                max_chars=app_settings.FUNCTIONAL_SPEC_MAX_CHARS,
                logger=logger,
            )

            functional_spec_context = str(spec_result.get("context", ""))
            llm_context = spec_result.get("llm_context", "")
            if isinstance(llm_context, str) and llm_context.strip():
                functional_spec_context = llm_context.strip()
            functional_spec_analysis = spec_result.get("analysis", {}) or {}
            loaded_files = spec_result.get("loaded_files", [])
            ignored_files = spec_result.get("ignored_files", [])
            warnings = spec_result.get("warnings", [])

            if loaded_files:
                logger.info(f"Loaded functional spec context from {len(loaded_files)} file(s)")
            else:
                logger.warning("No functional spec content loaded; proceeding without it")

            if ignored_files:
                logger.warning(
                    f"Ignored {len(ignored_files)} unreadable/unsupported functional spec file(s)"
                )

            for warning in warnings:
                logger.warning(warning)

        # Step 4: Initialize AI Generator
        ai_generator = None
        if enable_ai and app_settings.ENABLE_AI_SUMMARIES:
            logger.info("Initializing AI Generator...")
            ai_generator = AIGenerator()

            model_info = ai_generator.get_model_info()
            logger.info(f"  Model: {model_info['model']}")
            logger.info(f"  Batch mode: {model_info['batch_mode']}")
            logger.info(f"  Caching: {model_info['caching']}")

        if ai_generator is None:
            raise AIGeneratorError("AI generator is required for document generation")

        # Step 5: Build enterprise document with diagrams
        logger.info("Building specification document (Enterprise with Diagrams)...")
        output_path = build_specification_document(
            parser=parser,
            ai_generator=ai_generator,
            groovy_scripts=groovy_scripts,
            schemas=extracted_artifacts.get("schemas", []),
            parameters=extracted_artifacts.get("parameters", {}),
            parameter_definitions=extracted_artifacts.get("parameter_definitions", {}),
            all_files=extracted_artifacts.get("all_files", []),
            file_type_summary=extracted_artifacts.get("file_type_summary", {}),
            text_artifacts=extracted_artifacts.get("text_artifacts", []),
            artifact_analysis_context=extracted_artifacts.get("artifact_analysis_context", ""),
            output_dir=output_dir,
            include_diagrams=True,
            functional_spec_context=functional_spec_context,
            functional_spec_analysis=functional_spec_analysis,
        )

        # Log AI stats
        stats = ai_generator.get_stats()
        logger.info("=" * 50)
        logger.info("AI Generation Statistics:")
        logger.info(f"  API calls: {stats['api_calls']}")
        logger.info(f"  Batch calls: {stats.get('batch_calls', 0)}")
        logger.info(f"  Cache hits: {stats['cache_hits']}")
        logger.info(f"  Cache hit rate: {stats.get('cache_hit_rate', 0)}%")
        logger.info(f"  Failures: {stats['failures']}")
        if "estimated_calls_saved" in stats:
            logger.info(f"  Estimated calls saved: {stats['estimated_calls_saved']}")
        logger.info("=" * 50)
        logger.info(f"Document generated: {output_path}")

        return output_path

    finally:
        if zip_handler:
            zip_handler.cleanup()


def command_run(args: argparse.Namespace, ui: CLIUI) -> int:
    """Run full technical specification generation."""
    logger = setup_logging(args.verbose, ui)
    ui.banner("SAP CPI Specification Generator", "Command: run")

    config_valid, config_errors = app_settings.validate_config()
    if not config_valid:
        for error in config_errors:
            ui.error(f"Configuration error: {error}")
        return EXIT_CONFIG_ERROR

    input_valid, input_error = validate_input(args.input_path)
    if not input_valid:
        ui.error(input_error)
        return EXIT_INPUT_ERROR

    if args.output is not None and args.output_path is not None:
        logger.warning("Both --output and positional output_path provided; using --output")

    if args.clear_cache:
        cleared = clear_cache_files(logger)
        ui.info(f"Cleared {cleared} cached AI responses")

    effective_output = args.output if args.output is not None else args.output_path
    ui.key_values(
        "Run Parameters",
        [
            ("Input", str(args.input_path)),
            ("Output Dir", str(effective_output or app_settings.OUTPUT_DIR)),
            ("Batch Mode", "Enabled" if app_settings.ENABLE_BATCH_MODE else "Disabled"),
            (
                "Functional Spec",
                str(args.functional_spec) if args.functional_spec is not None else "Auto-detect",
            ),
        ],
    )

    start_time = datetime.now()

    try:
        output_path = process_iflow(
            input_path=args.input_path,
            output_dir=effective_output,
            functional_spec_path=args.functional_spec,
            enable_ai=True,
            logger=logger,
        )
    except AIGeneratorError as exc:
        logger.error(f"AI Error: {exc}")
        return EXIT_CONFIG_ERROR
    except ValueError as exc:
        logger.error(f"Input Error: {exc}")
        return EXIT_INPUT_ERROR
    except Exception as exc:
        logger.error(f"Processing Error: {exc}")
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROCESSING_ERROR

    elapsed = (datetime.now() - start_time).total_seconds()

    ui.success("Specification generated successfully.")
    ui.key_values(
        "Generation Result",
        [
            ("Output", str(output_path)),
            ("Time", f"{elapsed:.1f} seconds"),
        ],
    )
    return EXIT_SUCCESS


def command_validate(args: argparse.Namespace, ui: CLIUI) -> int:
    """Validate input, configuration, and optional functional-spec source."""
    logger = setup_logging(args.verbose, ui)
    ui.banner("SAP CPI Specification Generator", "Command: validate")

    input_valid, input_error = validate_input(args.input_path)
    if not input_valid:
        ui.error(input_error)
        return EXIT_INPUT_ERROR
    ui.success("Input path is valid.")

    config_valid, config_errors = app_settings.validate_config()
    if not config_valid:
        for error in config_errors:
            ui.error(f"Configuration error: {error}")
        return EXIT_CONFIG_ERROR
    ui.success("Configuration is valid.")

    if args.functional_spec is not None:
        if not args.functional_spec.exists():
            ui.error(f"Functional spec path does not exist: {args.functional_spec}")
            return EXIT_INPUT_ERROR

        result = load_functional_spec_context(
            args.functional_spec,
            max_chars=2000,
            logger=logger,
        )
        analysis = result.get("analysis", {})
        req_count = (
            len(analysis.get("business_requirements", []))
            if isinstance(analysis.get("business_requirements", []), list)
            else 0
        )
        iface_count = (
            len(analysis.get("interface_points", []))
            if isinstance(analysis.get("interface_points", []), list)
            else 0
        )
        section_count = (
            len(analysis.get("section_map", []))
            if isinstance(analysis.get("section_map", []), list)
            else 0
        )
        llm_context_len = len(str(result.get("llm_context", "")))

        ui.key_values(
            "Functional Spec Validation",
            [
                ("Loaded files", str(len(result.get("loaded_files", [])))),
                ("Ignored files", str(len(result.get("ignored_files", [])))),
                ("Warnings", str(len(result.get("warnings", [])))),
                ("Truncated", str(bool(result.get("truncated", False)))),
                ("Requirement signals", str(req_count)),
                ("Interface signals", str(iface_count)),
                ("Section blocks", str(section_count)),
                ("LLM context chars", str(llm_context_len)),
            ],
        )
    else:
        candidate = discover_functional_spec_path(args.input_path, logger=logger)
        if candidate is not None:
            ui.info(f"Auto-detected functional specification candidate: {candidate}")
        else:
            ui.info("No functional specification candidate detected near the input path.")

    ui.success("Validation checks completed.")
    return EXIT_SUCCESS


def command_inspect(args: argparse.Namespace, ui: CLIUI) -> int:
    """Inspect discovered artifacts and parsed iFlow structure."""
    logger = setup_logging(args.verbose, ui)
    ui.banner("SAP CPI Specification Generator", "Command: inspect")

    input_valid, input_error = validate_input(args.input_path)
    if not input_valid:
        ui.error(input_error)
        return EXIT_INPUT_ERROR

    zip_handler: ZipHandler | None = None
    try:
        artifacts, iflow_path, zip_handler = discover_artifacts(args.input_path, logger)
        if iflow_path is None:
            ui.error("No iFlow file (.iflw) found in input.")
            return EXIT_INPUT_ERROR

        parser = IFlowParser(iflow_path)
        parser.parse()

        processes = parser.get_integration_processes()
        seq_flows = parser.extract_sequence_flows_with_names()
        msg_flows = parser.extract_message_flows_with_names()
        sender_props = parser.extract_sender_properties()
        receiver_props = parser.extract_receiver_properties()
        metadata = parser.extract_metadata()

        ui.table("Artifact Summary", ["Artifact", "Count"], _artifact_rows(artifacts))
        ui.key_values(
            "iFlow Summary",
            [
                ("iFlow", parser.iflow_name),
                ("Processes", str(len(processes))),
                ("Message Flows", str(len(msg_flows))),
                ("Sequence Flows", str(len(seq_flows))),
                ("Sender Properties", str(len(sender_props))),
                ("Receiver Properties", str(len(receiver_props))),
            ],
        )

        if metadata:
            metadata_rows = [[str(k), str(v)] for k, v in metadata.items()]
            ui.table("Metadata", ["Key", "Value"], metadata_rows)
        else:
            ui.info("No metadata key/value pairs found in iFlow properties.")

        return EXIT_SUCCESS

    except (ZipHandlerError, ValueError) as exc:
        logger.error(str(exc))
        return EXIT_INPUT_ERROR
    except Exception as exc:
        logger.error(f"Inspection error: {exc}")
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROCESSING_ERROR
    finally:
        if zip_handler is not None:
            zip_handler.cleanup()


def command_diagrams(args: argparse.Namespace, ui: CLIUI) -> int:
    """Generate standalone integration-flow diagram."""
    logger = setup_logging(args.verbose, ui)
    ui.banner("SAP CPI Specification Generator", "Command: diagrams")

    input_valid, input_error = validate_input(args.input_path)
    if not input_valid:
        ui.error(input_error)
        return EXIT_INPUT_ERROR

    zip_handler: ZipHandler | None = None
    try:
        _, iflow_path, zip_handler = discover_artifacts(args.input_path, logger)
        if iflow_path is None:
            ui.error("No iFlow file (.iflw) found in input.")
            return EXIT_INPUT_ERROR

        parser = IFlowParser(iflow_path)
        parser.parse()

        output_dir = args.output or app_settings.OUTPUT_DIR
        results = generate_iflow_diagrams(parser, output_dir=output_dir)

        if not results:
            ui.error("No diagrams were generated.")
            return EXIT_PROCESSING_ERROR

        rows: list[list[str]] = []
        for diagram_type, path in results.items():
            size = _format_bytes(path.stat().st_size) if path.exists() else "n/a"
            rows.append([diagram_type, _safe_relative(path), size])

        ui.table("Generated Diagrams", ["Type", "File", "Size"], rows)
        ui.success("Diagram generation completed.")
        return EXIT_SUCCESS

    except (ZipHandlerError, ValueError) as exc:
        logger.error(str(exc))
        return EXIT_INPUT_ERROR
    except Exception as exc:
        logger.error(f"Diagram generation error: {exc}")
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROCESSING_ERROR
    finally:
        if zip_handler is not None:
            zip_handler.cleanup()


def command_diagnostics(args: argparse.Namespace, ui: CLIUI) -> int:
    """Run full diagnostics script."""
    setup_logging(args.verbose, ui)
    ui.banner("SAP CPI Specification Generator", "Command: diagnostics")

    try:
        from run_diagnostics import run_diagnostics

        is_ok = run_diagnostics()
    except Exception as exc:
        ui.error(f"Diagnostics failed to start: {exc}")
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROCESSING_ERROR

    if is_ok:
        ui.success("Diagnostics completed.")
        return EXIT_SUCCESS

    ui.warning("Diagnostics completed with warnings/failures.")
    return EXIT_PROCESSING_ERROR


def command_cache(args: argparse.Namespace, ui: CLIUI) -> int:
    """Show or clear cache."""
    logger = setup_logging(False, ui)
    ui.banner("SAP CPI Specification Generator", "Command: cache")

    if args.action == "clear":
        removed = clear_cache_files(logger)
        ui.success(f"Cleared {removed} cache file(s).")
        return EXIT_SUCCESS

    stats = get_cache_stats()
    ui.key_values(
        "Cache Summary",
        [
            ("Cache Dir", _safe_relative(stats["cache_dir"])),
            ("Entries", str(stats["entry_count"])),
            ("Total Size", _format_bytes(stats["total_size"])),
            ("Newest Entry", stats["newest"]),
        ],
    )

    sample_rows = stats.get("sample_rows", [])
    if sample_rows:
        ui.table("Recent Cache Files", ["File", "Size", "Updated"], sample_rows)
    else:
        ui.info("No cache files found.")

    return EXIT_SUCCESS


def command_config(args: argparse.Namespace, ui: CLIUI) -> int:
    """Show or validate runtime configuration."""
    setup_logging(False, ui)
    ui.banner("SAP CPI Specification Generator", "Command: config")

    config_rows = [
        ("BASE_DIR", str(app_settings.BASE_DIR)),
        ("OUTPUT_DIR", str(app_settings.OUTPUT_DIR)),
        ("TEMP_DIR", str(app_settings.TEMP_DIR)),
        ("AI_MODEL", app_settings.AI_MODEL),
        ("AI_MODEL_THINKING", app_settings.AI_MODEL_THINKING),
        ("API_KEY", "Set" if app_settings.GEMINI_API_KEY else "NOT SET"),
        ("AI_SUMMARIES", str(app_settings.ENABLE_AI_SUMMARIES)),
        ("AI_CACHING", str(app_settings.ENABLE_AI_CACHING)),
        ("BATCH_MODE", str(app_settings.ENABLE_BATCH_MODE)),
        ("STREAMING", str(app_settings.ENABLE_STREAMING)),
        ("USE_THINKING_MODEL", str(app_settings.USE_THINKING_MODEL)),
        ("DOC_AUTHOR", app_settings.DOC_AUTHOR),
        ("DOC_VERSION", app_settings.DOC_VERSION),
        ("TECH_SPEC_SCOPE_MODE", app_settings.TECH_SPEC_SCOPE_MODE),
        ("FUNCTIONAL_SPEC_MAX_CHARS", str(app_settings.FUNCTIONAL_SPEC_MAX_CHARS)),
    ]

    if args.action == "validate":
        valid, errors = app_settings.validate_config()
        if valid:
            ui.success("Configuration is valid.")
        else:
            for error in errors:
                ui.error(f"Configuration error: {error}")
            ui.key_values("Current Configuration", config_rows)
            return EXIT_CONFIG_ERROR

    ui.key_values("Current Configuration", config_rows)
    return EXIT_SUCCESS


def command_inputs(args: argparse.Namespace, ui: CLIUI) -> int:
    """Discover iFlow inputs and functional-spec candidates."""
    logger = setup_logging(args.verbose, ui)
    ui.banner("SAP CPI Specification Generator", "Command: inputs")

    target = args.path
    if not target.exists():
        ui.error(f"Input path does not exist: {target}")
        return EXIT_INPUT_ERROR

    zip_handler: ZipHandler | None = None
    try:
        if target.is_file():
            if target.suffix.lower() != ".zip":
                ui.error("inputs command expects a ZIP or a directory path.")
                return EXIT_INPUT_ERROR

            zip_handler = ZipHandler(str(target))
            zip_handler.extract()
            artifacts = zip_handler.discover_artifacts()
            iflow_files = sorted(artifacts.get("iflow", []), key=lambda p: str(p).lower())
            discovery_anchor = zip_handler.extract_dir if zip_handler.extract_dir else target.parent
        else:
            iflow_files = sorted(target.rglob("*.iflw"), key=lambda p: str(p).lower())
            discovery_anchor = target

        ui.key_values(
            "Input Discovery",
            [
                ("Target", str(target)),
                ("Detected iFlow files", str(len(iflow_files))),
                ("Result limit", str(args.limit)),
            ],
        )

        if iflow_files:
            rows: list[list[str]] = []
            for idx, iflow in enumerate(iflow_files[: args.limit], start=1):
                rows.append([str(idx), iflow.name, _safe_relative(iflow)])
            ui.table("Detected iFlow Files", ["#", "Name", "Path"], rows)

            if len(iflow_files) > args.limit:
                ui.warning(f"Showing first {args.limit} iFlow files.")
        else:
            ui.warning("No iFlow files found under the target path.")

        candidate = discover_functional_spec_path(discovery_anchor, logger=logger)
        if candidate:
            ui.info(f"Functional-spec candidate: {candidate}")
        else:
            ui.info("No functional-spec candidate detected.")

        return EXIT_SUCCESS

    except ZipHandlerError as exc:
        ui.error(str(exc))
        return EXIT_INPUT_ERROR
    except Exception as exc:
        logger.error(f"Input discovery error: {exc}")
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROCESSING_ERROR
    finally:
        if zip_handler is not None:
            zip_handler.cleanup()


def command_interactive(args: argparse.Namespace, ui: CLIUI) -> int:
    """Start interactive loop with arrow-key navigation."""
    setup_logging(False, ui)

    if not QUESTIONARY_AVAILABLE or questionary is None:
        ui.error("Interactive mode requires the 'questionary' package.")
        ui.info("Install dependencies with: pip install -r requirements.txt")
        return EXIT_CONFIG_ERROR

    ui.banner("SAP CPI Specification Generator", "Interactive Mode")
    ui.info("Use Up/Down arrows to navigate and Enter to select.")

    def ask_text(prompt: str, default: str = "") -> str:
        answer = questionary.text(prompt, default=default).ask()
        if answer is None:
            return ""
        return str(answer).strip()

    def ask_confirm(prompt: str, default: bool = False) -> bool:
        answer = questionary.confirm(prompt, default=default).ask()
        return bool(answer)

    try:
        while True:
            action = questionary.select(
                "Main Menu",
                choices=[
                    questionary.Choice("Run: Generate specification", value="run"),
                    questionary.Choice("Validate: Input and configuration", value="validate"),
                    questionary.Choice("Inspect: Artifacts and iFlow summary", value="inspect"),
                    questionary.Choice("Diagrams: Generate standalone images", value="diagrams"),
                    questionary.Choice("Diagnostics: Full system checks", value="diagnostics"),
                    questionary.Choice("Cache: Show", value="cache_show"),
                    questionary.Choice("Cache: Clear", value="cache_clear"),
                    questionary.Choice("Config: Show", value="config_show"),
                    questionary.Choice("Config: Validate", value="config_validate"),
                    questionary.Choice("Inputs: Discover iFlow files", value="inputs"),
                    questionary.Choice("Exit", value="exit"),
                ],
                qmark=">",
            ).ask()

            if action in {None, "exit"}:
                ui.success("Exiting interactive mode.")
                return EXIT_SUCCESS

            result_code = EXIT_SUCCESS

            if action == "run":
                input_raw = ask_text("Input path (.zip or directory)", default=str(Path.cwd()))
                if not input_raw:
                    ui.warning("Input path is required for run command.")
                    continue

                output_raw = ask_text("Output directory (leave blank for default)")
                spec_raw = ask_text(
                    "Functional spec path (leave blank for auto-detect)",
                )
                clear_cache = ask_confirm("Clear AI cache before run?", default=False)
                verbose = ask_confirm("Enable verbose logging for this run?", default=False)

                result_code = command_run(
                    argparse.Namespace(
                        input_path=Path(input_raw),
                        output_path=_to_path_or_none(output_raw),
                        output=None,
                        functional_spec=_to_path_or_none(spec_raw),
                        clear_cache=clear_cache,
                        verbose=verbose,
                    ),
                    ui,
                )

            elif action == "validate":
                input_raw = ask_text("Input path (.zip or directory)", default=str(Path.cwd()))
                if not input_raw:
                    ui.warning("Input path is required for validate command.")
                    continue

                spec_raw = ask_text(
                    "Functional spec path (leave blank to auto-discover)",
                )
                verbose = ask_confirm("Enable verbose logging for this validation?", default=False)

                result_code = command_validate(
                    argparse.Namespace(
                        input_path=Path(input_raw),
                        functional_spec=_to_path_or_none(spec_raw),
                        verbose=verbose,
                    ),
                    ui,
                )

            elif action == "inspect":
                input_raw = ask_text("Input path (.zip or directory)", default=str(Path.cwd()))
                if not input_raw:
                    ui.warning("Input path is required for inspect command.")
                    continue

                verbose = ask_confirm("Enable verbose logging for this inspection?", default=False)
                result_code = command_inspect(
                    argparse.Namespace(
                        input_path=Path(input_raw),
                        verbose=verbose,
                    ),
                    ui,
                )

            elif action == "diagrams":
                input_raw = ask_text("Input path (.zip or directory)", default=str(Path.cwd()))
                if not input_raw:
                    ui.warning("Input path is required for diagrams command.")
                    continue

                output_raw = ask_text(
                    "Output directory for PNG files",
                    default=str(app_settings.OUTPUT_DIR),
                )
                verbose = ask_confirm("Enable verbose logging for diagram generation?", default=False)

                result_code = command_diagrams(
                    argparse.Namespace(
                        input_path=Path(input_raw),
                        output=Path(output_raw) if output_raw else app_settings.OUTPUT_DIR,
                        verbose=verbose,
                    ),
                    ui,
                )

            elif action == "diagnostics":
                verbose = ask_confirm("Enable verbose logging for diagnostics?", default=False)
                result_code = command_diagnostics(
                    argparse.Namespace(verbose=verbose),
                    ui,
                )

            elif action == "cache_show":
                result_code = command_cache(argparse.Namespace(action="show"), ui)

            elif action == "cache_clear":
                result_code = command_cache(argparse.Namespace(action="clear"), ui)

            elif action == "config_show":
                result_code = command_config(argparse.Namespace(action="show"), ui)

            elif action == "config_validate":
                result_code = command_config(argparse.Namespace(action="validate"), ui)

            elif action == "inputs":
                target_raw = ask_text("Path to scan (.zip or directory)", default=str(Path.cwd()))
                if not target_raw:
                    ui.warning("Path is required for inputs command.")
                    continue

                limit_raw = ask_text("Maximum number of iFlow results", default="25")
                verbose = ask_confirm("Enable verbose logging for input discovery?", default=False)

                try:
                    limit_value = int(limit_raw)
                    if limit_value < 1:
                        raise ValueError("limit must be positive")
                except Exception:
                    limit_value = 25
                    ui.warning("Invalid limit provided. Using default value 25.")

                result_code = command_inputs(
                    argparse.Namespace(
                        path=Path(target_raw),
                        limit=limit_value,
                        verbose=verbose,
                    ),
                    ui,
                )

            if result_code == EXIT_SUCCESS:
                ui.success("Action completed.")
            else:
                ui.warning(f"Action finished with exit code {result_code}.")

            next_step = questionary.select(
                "Next step",
                choices=[
                    questionary.Choice("Back to main menu", value="menu"),
                    questionary.Choice("Exit interactive mode", value="exit"),
                ],
                qmark=">",
            ).ask()

            if next_step in {None, "exit"}:
                ui.success("Exiting interactive mode.")
                return EXIT_SUCCESS

    except KeyboardInterrupt:
        ui.warning("Interactive mode interrupted by user.")
        return EXIT_SUCCESS


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Unified CLI for SAP CPI specification generation and operational controls.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py
    python main.py interactive
  python main.py project.zip
  python main.py run project.zip -o output --verbose
  python main.py validate project.zip
    python main.py inspect ./integration_project
  python main.py diagrams project.zip -o output
  python main.py diagnostics
  python main.py cache show
  python main.py cache clear
  python main.py config show
    python main.py inputs .

Legacy compatibility:
  python main.py <input_path> [output_path] [run options]
  python main.py --show-config
        """,
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored CLI output.",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Start interactive arrow-key menu loop",
    )
    interactive_parser.set_defaults(handler=command_interactive)

    run_parser = subparsers.add_parser(
        "run",
        help="Generate technical specification document",
    )
    run_parser.add_argument(
        "input_path",
        type=Path,
        help="Path to ZIP file or extracted directory containing SAP CPI project",
    )
    run_parser.add_argument(
        "output_path",
        type=Path,
        nargs="?",
        help="Optional output directory (same as --output)",
    )
    run_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output directory for generated documents",
    )
    run_parser.add_argument(
        "--functional-spec",
        type=Path,
        default=None,
        help="Optional override path to functional specification file/folder",
    )
    run_parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear AI response cache before processing",
    )
    run_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    run_parser.set_defaults(handler=command_run)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate input and configuration without generation",
    )
    validate_parser.add_argument(
        "input_path",
        type=Path,
        help="Path to ZIP file or extracted directory containing SAP CPI project",
    )
    validate_parser.add_argument(
        "--functional-spec",
        type=Path,
        default=None,
        help="Optional functional specification file/folder to validate",
    )
    validate_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    validate_parser.set_defaults(handler=command_validate)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect artifacts and parsed iFlow details",
    )
    inspect_parser.add_argument(
        "input_path",
        type=Path,
        help="Path to ZIP file or extracted directory containing SAP CPI project",
    )
    inspect_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    inspect_parser.set_defaults(handler=command_inspect)

    diagrams_parser = subparsers.add_parser(
        "diagrams",
        help="Generate standalone integration-flow diagram image file",
    )
    diagrams_parser.add_argument(
        "input_path",
        type=Path,
        help="Path to ZIP file or extracted directory containing SAP CPI project",
    )
    diagrams_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=app_settings.OUTPUT_DIR,
        help="Output directory for generated integration-flow diagram PNG file",
    )
    diagrams_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    diagrams_parser.set_defaults(handler=command_diagrams)

    diagnostics_parser = subparsers.add_parser(
        "diagnostics",
        help="Run full system diagnostics",
    )
    diagnostics_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    diagnostics_parser.set_defaults(handler=command_diagnostics)

    cache_parser = subparsers.add_parser(
        "cache",
        help="View or clear local AI response cache",
    )
    cache_parser.add_argument(
        "action",
        nargs="?",
        choices=["show", "clear"],
        default="show",
        help="Cache action to perform",
    )
    cache_parser.set_defaults(handler=command_cache)

    config_parser = subparsers.add_parser(
        "config",
        help="Show or validate configuration",
    )
    config_parser.add_argument(
        "action",
        nargs="?",
        choices=["show", "validate"],
        default="show",
        help="Configuration action to perform",
    )
    config_parser.set_defaults(handler=command_config)

    inputs_parser = subparsers.add_parser(
        "inputs",
        help="Discover iFlow files and functional-spec candidates",
    )
    inputs_parser.add_argument(
        "path",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Path to scan (.zip or directory)",
    )
    inputs_parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of iFlow paths to display",
    )
    inputs_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    inputs_parser.set_defaults(handler=command_inputs)

    return parser


def _extract_no_color(argv: Sequence[str]) -> tuple[list[str], bool]:
    """Extract --no-color so it works before/after subcommands."""
    cleaned: list[str] = []
    no_color = False
    for arg in argv:
        if arg == "--no-color":
            no_color = True
        else:
            cleaned.append(arg)
    return cleaned, no_color


def normalize_legacy_argv(argv: Sequence[str]) -> list[str]:
    """Map legacy argument patterns to command-based CLI usage."""
    args = list(argv)
    if not args:
        return args

    first = args[0]

    if first in {"-h", "--help"}:
        return args

    if first in KNOWN_COMMANDS:
        return args

    if first == "--show-config":
        return ["config", "show", *args[1:]]

    if first == "--clear-cache":
        return ["cache", "clear", *args[1:]]

    # Backward-compatible default: treat unknown first token as run input_path.
    return ["run", *args]


def main() -> int:
    """Main CLI entry point."""
    raw_argv = sys.argv[1:]
    without_color_flag, no_color = _extract_no_color(raw_argv)
    argv = normalize_legacy_argv(without_color_flag)

    parser = build_parser()
    args = parser.parse_args(argv)
    ui = CLIUI(use_color=not no_color)

    if args.command is None:
        return int(command_interactive(argparse.Namespace(), ui))

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_INPUT_ERROR

    return int(handler(args, ui))


if __name__ == "__main__":
    sys.exit(main())
