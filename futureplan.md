# Future Plan for SAP CPI Specification Generator

## 1. Project Goal for the Next Phase
Build a stable, testable, and production-ready generator that produces high-quality SAP CPI technical specifications with predictable output quality, lower operational risk, and better maintainability.

## 2. Current State Summary
- Strong CLI workflow is already in place: run, validate, inspect, diagrams, diagnostics, cache, config.
- Batch AI generation and caching already reduce cost and runtime significantly.
- Enterprise document output and BPMN-style diagram generation are implemented.
- Main gaps are automation quality gates, deeper validation, and long-term maintainability.

## 3. Highest Priority Changes (Do First)

### 3.1 Add Automated Test Suite
Why this is needed:
- There is no project-owned test suite in the tests folder, which increases regression risk.

Changes to implement:
- Add pytest with unit tests for:
  - iflow_parser: message/sequence flow extraction, sender/receiver extraction, exception subprocess extraction.
  - zip_handler: safe extraction, suspicious path rejection, multi-artifact discovery.
  - artifact_extractor: Groovy function extraction, XSD parsing, parameters parsing edge cases.
  - functional_spec_parser: candidate scoring, exclusion rules, doc/txt extraction fallback behavior.
  - diagram_generator: successful PNG bytes generation for sample iFlow and fallback behavior.
- Add integration tests for CLI commands:
  - run, validate, inspect, diagrams, cache show/clear, config validate.
- Add golden-output checks:
  - Generated doc contains expected headings, table counts, and at least one embedded image.

Acceptance criteria:
- Automated tests run in one command and pass in CI.
- Critical parser and builder paths have meaningful coverage.

### 3.2 Add CI Pipeline with Quality Gates
Why this is needed:
- No continuous checks means breakages can be introduced unnoticed.

Changes to implement:
- Add CI workflow for:
  - Dependency install.
  - Linting and formatting checks.
  - Type checks.
  - Unit and integration tests.
- Enforce merge blocking on failed checks.

Acceptance criteria:
- Every PR is validated automatically.
- No code merges when lint, typing, or tests fail.

### 3.3 Strengthen AI Output Validation
Why this is needed:
- AI responses can be malformed or partially missing keys.

Changes to implement:
- Add strict response schema validation for AI JSON output.
- Add automatic fallback handling for missing/invalid keys.
- Add structured parse diagnostics that identify which section failed.
- Add deterministic defaults for every required section.

Acceptance criteria:
- Document generation never fails due to missing optional AI fields.
- Error messages clearly identify invalid AI response fields.

## 4. Reliability and Robustness Improvements

### 4.1 Standardize Error Taxonomy
Changes to implement:
- Define consistent error classes and user-facing messages across parser, AI, document, and ZIP modules.
- Return machine-readable error codes from all command paths.
- Improve diagnostics output with severity levels and remediation hints.

### 4.2 Improve Input Handling and Multi-iFlow Behavior
Changes to implement:
- Add explicit strategy when multiple .iflw files are found:
  - interactive selection mode, or
  - process-all mode with separate outputs.
- Add path validation for uncommon edge cases and very large ZIP inputs.

### 4.3 Temporary File Lifecycle Hardening
Changes to implement:
- Ensure temp extraction directories are cleaned reliably on both success and failure.
- Add optional retain-temp flag for debugging.

## 5. Architecture and Maintainability Upgrades

### 5.1 Replace Path Injection with Proper Packaging
Current issue:
- Several modules use runtime sys.path insertion.

Changes to implement:
- Convert project to package-first structure.
- Add pyproject.toml and console script entry point.
- Remove runtime path patching.

Benefits:
- Cleaner imports, easier local development, and safer deployment behavior.

### 5.2 Introduce Typed Data Models
Changes to implement:
- Add dataclasses or pydantic models for:
  - Parsed iFlow data.
  - Artifact extraction results.
  - AI section payload.
  - Document assembly input.
- Enforce typing at module boundaries.

Benefits:
- Fewer runtime shape errors and easier refactoring.

### 5.3 Refactor Main Pipeline into Explicit Stages
Changes to implement:
- Create a pipeline orchestration layer with clear stages:
  - Input -> Discovery -> Parse -> Enrich -> AI -> Build -> Validate -> Output.
- Add stage timing and structured run summary.

## 6. Output Quality Enhancements

### 6.1 Post-Generation Quality Scoring
Changes to implement:
- Add a scoring report for generated DOCX:
  - Section completeness.
  - Minimum table/image thresholds.
  - AI field coverage.
  - Empty placeholder detection.

### 6.2 Improve Diagram Scalability
Changes to implement:
- Add large-flow layout options for dense process diagrams.
- Add alternative orientation modes and configurable styles.
- Add connector-crossing reduction heuristics.

### 6.3 Add Optional PDF Export
Changes to implement:
- Add command flag to produce PDF from DOCX in the same run.
- Include clear fallback behavior when PDF conversion dependency is unavailable.

## 7. Performance and Cost Optimization

### 7.1 Smarter Cache Invalidation
Changes to implement:
- Invalidate cache by content hash of key inputs (iflow XML + scripts + functional context + prompt template).
- Add cache metadata report and stale-cache detection.

### 7.2 Incremental Regeneration
Changes to implement:
- Regenerate only changed sections when source artifacts are unchanged.
- Reuse previous validated sections to lower AI usage and runtime.

### 7.3 Runtime Metrics
Changes to implement:
- Persist run metrics:
  - Elapsed time per stage.
  - API calls and cache hit ratio.
  - Estimated token and cost usage.

## 8. Security and Compliance Improvements

### 8.1 Secret and Sensitive Data Protection
Changes to implement:
- Ensure logs do not expose secrets, credentials, or sensitive payload snippets.
- Add optional masking for endpoint hostnames and IDs in outputs.

### 8.2 Safe Processing Controls
Changes to implement:
- Add max ZIP/file size limits and configurable safety thresholds.
- Add strict handling for malformed files and unsupported encodings.

## 9. Developer Experience and Documentation

### 9.1 Improve Developer Setup
Changes to implement:
- Add one-command dev setup.
- Add contributor guide with coding standards, testing commands, and release process.
- Add local pre-commit checks.

### 9.2 Keep Documentation Fully Aligned
Changes to implement:
- Ensure README, diagnostics, and command help remain synchronized.
- Add real examples for each CLI command with expected outputs.

## 10. Suggested Delivery Plan

### Phase 1 (Immediate)
- Automated tests.
- CI quality gates.
- AI output schema validation.
- Error taxonomy standardization.

### Phase 2 (Short Term)
- Packaging cleanup.
- Typed data models.
- Pipeline stage refactor.
- Multi-iFlow handling improvements.

### Phase 3 (Medium Term)
- Quality scoring.
- Incremental regeneration.
- Advanced diagram layouts.
- Optional PDF export.

### Phase 4 (Advanced)
- Run history and comparison reports.
- Policy-driven compliance and masking rules.
- Enhanced performance analytics dashboard.

## 11. Definition of Done for Future Plan Execution
- Test suite exists and runs automatically on every change.
- Build pipeline blocks regressions.
- Output quality is measurable and reported.
- Architecture is modular with explicit contracts between stages.
- Documentation and CLI behavior stay consistent and predictable.
