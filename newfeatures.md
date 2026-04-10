# New Features: Detailed Internal Workflow Reference

This document explains the current system in function-level detail, with focus on:
1. BPMN model generation (how the model is built and rendered)
2. Functional specification integration (how AI understands it, and why it helps)
3. Improved CLI (command model, execution flow, and output ownership)

---

## 1) BPMN Model: How the Integration Flow Diagram Is Built

### 1.1 Objective
The BPMN model pipeline turns the `.iflw` BPMN XML into a readable diagram image that is either:
- embedded into the DOCX document, or
- exported as standalone PNG.

### 1.2 Primary call chain
For document generation, the call sequence is:

1. `main.py` -> `command_run()`
2. `command_run()` -> `process_iflow()`
3. `process_iflow()` -> `build_specification_document()`
4. `build_specification_document()` -> `generate_diagram_bytes(parser, "integration_flow")`
5. `generate_diagram_bytes()` -> `BPMNDiagramGenerator.generate_integration_flow_diagram_from_bpmndi(parser)`
6. If BPMN-DI is missing/insufficient -> fallback to `generate_integration_flow_diagram(processes, sequence_flows)`

### 1.3 BPMN data structures used by the renderer
In `src/diagram_generator.py`, `generate_integration_flow_diagram_from_bpmndi()` builds these structures:

- `element_meta`: element ID -> `{type, name}`
  - from `_collect_element_metadata()`
- `participants`: participant ID -> `{name, process_ref, participant_type}`
  - from `_collect_participants()`
- `shapes`: BPMN element ID -> `{x, y, w, h}`
  - from `_collect_bpmndi_shapes()`
- `edges`: flow ID -> list of waypoints `[(x1,y1), (x2,y2), ...]`
  - from `_collect_bpmndi_edges()`
- `flow_meta`: flow ID -> `{type, name, source_ref, target_ref}`
  - built from XML `sequenceFlow` and `messageFlow`

### 1.4 BPMN model source preference
The renderer merges two coordinate sources:

1. Native XML BPMN-DI coordinates
2. Optional `bpmn_python` graph extraction (`_collect_data_with_bpmn_python()`)

Merge behavior:
- If `bpmn_python` provides better shape/edge coverage, data is merged in.
- Existing XML metadata is preserved when possible.
- If no drawable shapes are available, system falls back to synthetic layout.

### 1.5 Geometry normalization and routing
Before drawing flows:

- `_normalize_flow_points()` adjusts first/last waypoints.
- `_point_inside_bounds()` detects if waypoint starts/ends inside shape.
- `_project_center_to_bounds_edge()` moves anchor to shape boundary.

Why this matters:
- Arrows should originate/terminate at shape borders, not inside boxes.
- Improves visual correctness, especially for exported diagrams in technical docs.

### 1.6 Shape semantics (BPMN-like rendering)
Node rendering is type-aware:

- Events:
  - Drawn as circles
  - End events use thicker stroke
- Gateways:
  - Drawn as diamonds
- Subprocess:
  - Rounded rectangle + collapsed marker (`+`)
- Tasks/call activities/service tasks:
  - Rounded task boxes
  - callActivity uses heavier border
  - service task includes small icon marker
- Participants/pools:
  - Drawn first (background layers)
  - Process pools include lane-style label region

### 1.7 Edge semantics
Flow rendering is type-aware:

- Sequence flow:
  - solid line + filled arrow (`_draw_sequence_flow()`)
- Message flow:
  - dashed line + open circle at source + open arrow head (`_draw_message_flow()`)

Labeling:
- Flow labels are placed near midpoint with white background box to improve readability.

### 1.8 Fallback legacy layout (if BPMN-DI unavailable)
`generate_integration_flow_diagram()` creates a synthetic process layout:

- Builds node list from sequence flows
- Orders nodes using `_order_nodes()` (topological-like ordering)
- Uses row-based layout with max nodes per row
- Distinguishes start/end event circles and task boxes
- Adds basic legend

Why fallback exists:
- Some iFlow exports may miss complete BPMN-DI coordinates.
- System remains resilient and still generates useful diagrams.

### 1.9 Output paths
- In-document embedding:
  - `build_specification_document()` stores bytes in `diagram_bytes` and injects via `builder.add_image()`
- Standalone export:
  - `generate_iflow_diagrams()` writes `<iflow_name>_integration_flow.png`

---

## 2) Functional Specification: Why It Helps and How AI Uses It

### 2.1 Problem solved
iFlow XML is strong for technical wiring but weak for business context.

XML usually provides:
- adapters
- endpoints
- flows
- script references
- component properties

XML usually does not fully provide:
- business drivers
- explicit current vs to-be narratives
- country/process intent
- operational assumptions (volume/frequency)

Functional spec closes that gap.

### 2.2 Discovery and selection workflow
When user does not pass `--functional-spec`, `process_iflow()` does this:

1. `discover_functional_spec_path(discovery_anchor)`
2. If ZIP input was used, first anchor is extraction dir, then original input path fallback
3. Returns best candidate path or `None`

Candidate discovery internals in `src/functional_spec_parser.py`:

- `_iter_supported_files(root, max_depth)`
  - scans for `.docx`, `.doc`, `.txt`, `.md`, `.rtf`
  - excludes noisy directories (`output`, `temp`, `venv`, `.git`, etc.)
- `_score_candidate(file_path, base_dir, parent_dir)`
  - positive signals: `functional`, `specification`, `spec`, `requirement`, `business`
  - penalties: `techspec`, `technical specification`, `readme`, `requirements`, `changelog`
  - location weighting: closer files score higher
- threshold: keeps only strong candidates (`score >= 7`)

Why this design:
- Auto-select when likely useful
- avoid accidental picks like `requirements.txt` or generated tech specs

### 2.3 Content extraction by format
`load_functional_spec_context()` reads and normalizes content:

- DOCX: `_extract_docx_text()`
  - paragraph text + table row text
- DOC (legacy): `_extract_doc_text()`
  - first tries `_extract_doc_text_with_word()` via Word COM
  - fallback `_extract_doc_text_heuristic()` printable-string extraction
- RTF: `_extract_rtf_text()` best-effort cleanup
- TXT/MD: `_read_text_with_fallback()`

Post-processing:
- `_normalize_text()` whitespace cleanup
- per-file context block prefix: `Functional specification source: <file>`
- truncation to `FUNCTIONAL_SPEC_MAX_CHARS` (default 15000)

Return payload:
- `context`
- `loaded_files`
- `ignored_files`
- `warnings`
- `truncated`

### 2.4 How AI understands and uses this context
AI prompt injection happens in `AIGenerator.generate_all_sections_batch()`:

1. Builds `groovy_info` and truncated XML
2. Builds `functional_spec_info` from context (or `Not provided.`)
3. Injects into `COMPREHENSIVE_BATCH_PROMPT`

Prompt rule that controls safety:
- "Use functional-spec context to improve business/process understanding, but do not contradict explicit iFlow XML technical configuration."

Why this is important:
- prevents functional document text from overriding hard technical facts in iFlow XML

### 2.5 Where improvements appear in output
Functional context primarily improves these sections:

- `2.1 Executive Summary`
- `2.3 Interface Requirement`
- `3.1 Current Scenario`
- `3.2 To-Be Scenario`
- `2.4 Functional Assumptions`

System also marks whether functional context was used:
- `Document Control` table contains `Functional Spec Context: Provided|Not Provided`

### 2.6 Benefits by stakeholder
For us (engineering/document owners):
- better business-level completeness
- fewer generic placeholders
- stronger traceability between technical and functional narrative

For AI model quality:
- richer grounding context for business sections
- improved terminology consistency
- improved inference when XML is silent on business assumptions

For runtime system behavior:
- optional by design
- graceful ignore path when missing/unreadable
- explicit warnings without hard-fail on functional-spec issues

### 2.7 Known limitations
- functional spec may be stale
- DOC extraction quality depends on source file quality and format
- context truncation may cut low-priority tail content

---

## 3) Improved CLI: Detailed Command and Execution Workflow

### 3.1 CLI architecture
`main.py` now uses command-driven architecture with legacy compatibility.

Entry sequence:

1. `main()`
2. `_extract_no_color(argv)`
3. `normalize_legacy_argv(argv)`
4. `build_parser()`
5. parse args and dispatch to command handler

Legacy compatibility examples:
- `python main.py <input_path>` -> remapped to `run`
- `python main.py --show-config` -> remapped to `config show`

### 3.2 Command surface
Main commands:

- `interactive`
- `run`
- `validate`
- `inspect`
- `diagrams`
- `diagnostics`
- `cache`
- `config`
- `inputs`

### 3.3 Output ownership: who prints what
There are three output layers:

1. `CLIUI` layer (user-facing command summaries)
   - `banner()`, `info()`, `success()`, `warning()`, `error()`
   - `key_values()` and `table()`
2. logger layer (module and runtime logs)
   - configured by `setup_logging()`
   - includes `process_iflow()` and `AIGenerator` logs
3. raw `print()` progress in document build phase
   - `build_specification_document()` prints `[1/10] ... [10/10]`

### 3.4 `run` command: step-by-step function workflow
Command handler:

1. `command_run(args, ui)`
2. `setup_logging(args.verbose, ui)`
3. `validate_config()`
4. `validate_input(args.input_path)`
5. optional `clear_cache_files()`
6. compute effective output path (`--output` or positional `output_path`)
7. call `process_iflow(...)`

Inside `process_iflow()`:

1. `discover_artifacts(input_path, logger)`
   - ZIP path -> `ZipHandler.extract()`, `ZipHandler.discover_artifacts()`, `ZipHandler.get_iflow_path()`
   - directory path -> `extract_from_directory()`
2. `IFlowParser(iflow_path).parse()`
3. `extract_all_artifacts(artifacts)`
4. functional-spec detection/load
   - `discover_functional_spec_path()`
   - `load_functional_spec_context()`
5. `AIGenerator()` initialization
6. `build_specification_document(...)`
7. `ai_generator.get_stats()` logging
8. returns output doc path

Inside `build_specification_document()` (high level):

1. extract parser-derived data
2. print run summary
3. generate diagram bytes
4. call `ai_generator.generate_all_sections_batch()`
5. map AI JSON to section getters (`get_text`, `get_dict`, `get_list`)
6. render document sections through `EnterpriseDocumentBuilder`
7. save DOCX
8. print final success line

### 3.5 `validate` command workflow
`command_validate()`:

1. validate input path
2. validate config
3. if `--functional-spec` passed:
   - load content and report loaded/ignored/truncated
4. else:
   - run auto-discovery candidate check

### 3.6 `inspect` command workflow
`command_inspect()`:

1. discover artifacts
2. parse iFlow
3. extract process/flow/metadata summaries
4. print artifact summary and iFlow summary tables

### 3.7 `diagrams` command workflow
`command_diagrams()`:

1. discover iFlow
2. parse iFlow
3. call `generate_iflow_diagrams(parser, output_dir)`
4. print generated file table

### 3.8 `cache` and `config`
- `cache show` -> `get_cache_stats()`
- `cache clear` -> `clear_cache_files()`
- `config show|validate` -> reads from `config/settings.py`

### 3.9 `inputs` command workflow
`command_inputs()`:

1. scan target ZIP/dir for `.iflw`
2. print detected iFlow file list (limited)
3. run functional-spec auto-discovery and show candidate

### 3.10 Interactive mode workflow
`command_interactive()` uses `questionary` for menu-driven command execution.

Capabilities:
- run generation
- validate
- inspect
- generate diagrams
- run diagnostics
- manage cache
- inspect config
- discover inputs

---

## 4) End-to-End Runtime Workflow (Single Run, Detailed)

This is the practical order for a normal run:

1. User runs command
   - example: `python main.py <input> <output>`
2. `main()` normalizes args and dispatches to `command_run()`
3. CLI prints banner + run parameters
4. `process_iflow()` starts
5. artifacts are discovered from ZIP or directory
6. iFlow XML parsed
7. scripts/schemas/params extracted
8. functional spec auto-detected or overridden
9. functional spec context loaded + normalized + truncated if needed
10. AI generator initialized
11. diagram generated (BPMN-DI first, fallback if needed)
12. AI batch prompt built from:
    - combined XML
    - groovy snippets
    - functional-spec context
13. AI returns full JSON payload for sections
14. document sections rendered in order
15. DOCX saved
16. AI stats printed
17. CLI prints final success summary

---

## 5) Why Each Design Choice Exists

### BPMN-DI first, fallback second
- BPMN-DI preserves original model geometry.
- Fallback keeps output available even with incomplete source data.

### Functional context optional, never mandatory
- avoids hard dependency on business document availability
- keeps pipeline reliable in technical-only projects

### Batch AI generation
- minimizes API calls
- improves section consistency because one prompt sees all context

### Command-based CLI with legacy mapping
- modern discoverable command UX
- no breakage for older invocation patterns

### Strong observability
- clear separation of command UI output, logger output, and build-stage progress output
- easier debugging and user trust in pipeline behavior

---

## 6) Quick Function Index (for maintainers)

### Main orchestration
- `main.py::main`
- `main.py::command_run`
- `main.py::process_iflow`
- `main.py::discover_artifacts`

### Functional specification
- `src/functional_spec_parser.py::discover_functional_spec_path`
- `src/functional_spec_parser.py::load_functional_spec_context`
- `src/functional_spec_parser.py::_extract_docx_text`
- `src/functional_spec_parser.py::_extract_doc_text`

### AI generation
- `src/ai_generator.py::generate_all_sections_batch`
- `src/ai_generator.py::generate`
- `src/ai_generator.py::get_stats`

### Diagram generation
- `src/diagram_generator.py::generate_diagram_bytes`
- `src/diagram_generator.py::generate_integration_flow_diagram_from_bpmndi`
- `src/diagram_generator.py::generate_integration_flow_diagram`

### Document building
- `src/document_builder.py::build_specification_document`
- `src/document_builder.py::EnterpriseDocumentBuilder.add_table`
- `src/document_builder.py::EnterpriseDocumentBuilder.save`

---

## 7) Current Status Summary

- BPMN model generation is deterministic and resilient (BPMN-DI + fallback).
- Functional specification is integrated as optional high-value context.
- CLI is modernized with subcommands and still backward compatible.
- Workflow is traceable function-by-function from input to output.
