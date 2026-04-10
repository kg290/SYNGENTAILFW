# How The System Builds The Generated Document

## 1. Purpose Of This Explanation
This document explains the logic that transforms SAP Cloud Integration assets into a structured technical specification document. The focus is on how information is discovered, interpreted, organized, and rendered into the final output.

The explanation is intentionally implementation-agnostic. It describes system behavior and decision flow rather than source-level details.

## 2. End-To-End Logical Flow
The system follows a staged pipeline. Each stage outputs structured data that is consumed by later stages.

### 2.1 Stage 1: Input Validation And Classification
The system first validates the input path and classifies it as one of two supported input types:
- ZIP package containing an integration project
- Extracted directory containing integration artifacts

Validation ensures:
- The path exists
- A ZIP input actually has ZIP format
- A directory input contains at least one iFlow definition file

If validation fails, processing stops early with an input error.

### 2.2 Stage 2: Artifact Discovery
After validation, the system discovers known artifact types across the input structure.

Artifact categories include:
- iFlow definition files
- Groovy scripts
- XSD schemas
- Parameter files and parameter definitions
- Mapping and WSDL resources
- Metadata resources

If a ZIP input is used, extraction happens first, then discovery runs against the extracted tree.

### 2.3 Stage 3: Core iFlow Parsing
The iFlow XML is parsed into structured process data.

At this point, the system derives:
- Integration process list
- Message flow connections
- Sequence flow connections
- Sender and receiver adapter property sets
- Mapping activity property sets
- Security-related properties
- Exception subprocess properties
- iFlow metadata

This parsed structure becomes the canonical technical backbone for the rest of the document.

### 2.4 Stage 4: Supplemental Artifact Extraction
Non-iFlow artifacts are processed into usable technical context.

For Groovy scripts, the system derives:
- Script names and locations
- Full script content
- Function signatures
- Imports
- Line counts

For XSD files, the system derives:
- Target namespace
- Element list and shape
- Complex type list

For parameter files, the system derives key-value dictionaries used later in appendix and configuration sections.

### 2.5 Stage 5: Optional Functional Specification Context
The system can enrich generation with a functional specification source.

Logic:
- If user explicitly provides a functional spec path, that path is used
- Otherwise, auto-discovery searches likely candidates near the project
- Supported text content is extracted
- Extracted context is bounded by a maximum character policy

This context does not replace technical iFlow truth. It only enriches narrative quality.

### 2.6 Stage 6: AI Consolidation
The system sends a consolidated prompt that includes:
- iFlow XML context
- Artifact-derived technical context
- Optional functional-spec context

The AI response is expected as structured JSON with named sections. This gives two benefits:
- Section consistency across the document
- Deterministic mapping from AI output keys to document blocks

### 2.7 Stage 7: Diagram Generation
The system generates an integration flow diagram from BPMN-DI coordinates where available.

Key logic:
- Use BPMN shape bounds and edge waypoints when present
- Normalize edge endpoints to shape borders for cleaner routing
- Style BPMN nodes by role (events, tasks, subprocesses, gateways)
- Render sequence vs message flows with different visual semantics

Only the Integration Flow Diagram is produced now.

### 2.8 Stage 8: Document Assembly
The system builds the Word document in sections. It combines:
- Deterministic technical extraction
- AI-generated narrative content
- Diagram image bytes
- Derived metrics and statistics

The Table of Contents is generated as a visible static section list (not a dynamic field), which avoids field-update prompts and still gives immediate readability.

### 2.9 Stage 9: Finalization
The final document is written to output with:
- Naming based on iFlow identity
- Embedded media (integration flow diagram)
- Complete section hierarchy
- Appendix and generation statistics

## 3. How Required Data Is Identified, Collected, And Prepared

### 3.1 Required Data Classes
The system logically treats data in four classes:
- Structural workflow data (processes, steps, flows)
- Integration configuration data (sender, receiver, security, mapping)
- Artifact content data (scripts, schemas, parameters)
- Narrative context data (AI summaries and optional functional context)

### 3.2 Identification Strategy
Data is identified by artifact type and semantic role:
- File type patterns identify artifact candidates
- XML namespaces identify BPMN and integration model entities
- Property keys identify sender/receiver direction and behavior
- Subprocess signatures identify error handling logic

### 3.3 Collection Strategy
Collection is done in a fail-safe sequence:
1. Discover files
2. Parse iFlow core first
3. Parse supporting artifacts
4. Attach optional context
5. Run AI synthesis

If any optional source is missing, processing continues with warnings instead of hard failure.

### 3.4 Preparation Strategy
Before data is used in the document:
- Values are normalized to strings for table rendering
- Lists and dictionaries are flattened into table-ready rows
- Long text blocks are cleaned for readability
- Markdown artifacts from generated prose are sanitized
- Diagram output is converted to embeddable PNG bytes

## 4. How Each Major Document Section Is Derived

### 4.1 Cover And Document Control
Derived from:
- iFlow name
- Current generation date/time
- System metadata (author/version settings)
- Generation-mode flags (for example, batch enabled)

### 4.2 Table Of Contents
Derived from:
- Known section structure
- Conditional section presence (for example, assumptions only if available)
- Diagram presence (integration flow heading included only when generated)

The system builds a static list to ensure immediate visibility in all viewers.

### 4.3 Overview Section
Derived from:
- AI narrative keys (executive summary, purpose, interface requirement)
- Parsed integration counts (processes, flows, scripts, schemas, parameters)
- Functional assumptions if present

### 4.4 High-Level iFlow Design Section
Derived from:
- AI narrative keys (current scenario, to-be scenario, high-level design)
- AI technical dependency text when available
- Parsed iFlow semantics where AI fields are absent

### 4.5 Message Flow Section
Derived from:
- AI technical flow narrative
- Parsed process-flow details
- Parsed message-flow and sequence-flow link data
- Generated integration flow diagram

Formatting logic also converts inline numbered prose into a true numbered list when pattern detection succeeds.

### 4.6 Technical Description Section
Derived from:
- Process list extracted from iFlow
- AI process summaries and key activities
- Process component properties and child element properties
- Sender/receiver/mapping/security property tables
- Groovy and exception handling details

### 4.7 Version And Metadata Section
Derived from:
- iFlow metadata properties
- AI metadata fields
- Merge logic that combines both sources into one table

### 4.8 Appendix Section
Derived from:
- Collected artifact inventory
- Schema and parameter extraction outputs
- Optional AI appendix elements such as glossary and references
- Generation statistics from AI subsystem

## 5. Examples Of Input-To-Output Transformation

## Example A: Flow Connectivity
Input:
- BPMN messageFlow nodes with sourceRef and targetRef IDs

Transformation:
- IDs are resolved to meaningful names
- Name triplets are formed as Source, Target, Label

Output:
- A document table listing human-readable flow connections

## Example B: Groovy Script Description
Input:
- Script content and function signatures

Transformation:
- Script metadata is collected
- AI receives script context and returns purpose narrative

Output:
- Script subsection with metadata table, function table, and code block excerpt

## Example C: Functional Assumptions
Input:
- AI returns structured assumptions dictionary

Transformation:
- Dictionary keys are converted into readable row labels
- Empty values are filtered out

Output:
- A two-column assumptions table in the Overview section

## Example D: Integration Diagram Embedding
Input:
- BPMN-DI shape coordinates and edge waypoints

Transformation:
- Diagram renderer draws BPMN-like visual elements
- Final image bytes are produced

Output:
- Embedded Integration Flow Diagram figure inside the Message Flow section

## 6. Decision Logic And Fallback Behavior

### 6.1 If AI Is Unavailable
The system stops document generation because AI-generated narrative is part of the expected output contract.

### 6.2 If Optional Inputs Are Missing
The system continues and inserts defaults, for example:
- No functional spec found -> continue without enrichment
- Missing optional fields -> use safe fallback narrative

### 6.3 If BPMN-DI Coordinates Are Missing
The system falls back to legacy flow layout logic for integration visualization.

### 6.4 If Individual Artifacts Fail To Parse
The system records warnings and continues with available data, preserving pipeline continuity.

## 7. Quality Controls Applied During Generation
The system applies practical quality controls before final output:
- Input integrity validation
- Configuration validation
- Data normalization before rendering
- Structured AI response expectations
- Markdown artifact cleanup in narrative sections
- Deterministic section ordering
- Post-generation statistics capture

## 8. Why The Output Is Consistent
Consistency comes from combining fixed document structure with flexible data population:
- Structure is stable and section-driven
- Data population is conditional but rule-based
- Defaults are used where data is unavailable
- Technical extraction remains source-of-truth anchored to iFlow artifacts

This ensures the final document is both readable for business users and traceable for technical reviewers.
