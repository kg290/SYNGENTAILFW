# SAP CI Technical Specification Generator

Generate SAP CI technical specification documents and diagrams from SAP integration flow projects stored as ZIP files or extracted folders.

The generator parses the iFlow BPMN/XML and related artifacts, resolves externalized parameters, builds technical sections for sender/receiver/mappings/scripts, and produces a formatted `.docx` specification plus standalone PNG diagrams.

## What it generates

- Technical specification Word document
- Integration flow diagram
- Sender diagram
- Receiver diagram

The generated document includes:

- overview and purpose sections
- message flow
- main integration process
- local integration process when present
- dedicated sender section
- dedicated receiver section
- simplified mapping section
- Groovy script section
- error handling / exception subprocess section
- metadata and appendix
- externalized parameters with usage

## Current behavior

- Works with ZIP inputs and extracted project folders
- Resolves runtime placeholders like `{{Address}}` and `${Credential}` where values are available
- Removes noisy internal property rows from the document
- Keeps sender/receiver diagrams in dedicated sections
- Separates local integration process from exception subprocess content
- Uses fallback document content when AI generation is unavailable or rate-limited

## Requirements

- Python 3.10+
- Gemini API key
- SAP integration project containing an `.iflw` file

## Setup

### 1. Create a virtual environment

```powershell
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment

Create `.env` from `.env.example` and set your API key:

```powershell
Copy-Item .env.example .env
```

Required environment variable:

- `GEMINI_API_KEY`

Useful optional variables:

- `AI_MODEL`
- `DOC_AUTHOR`
- `DOC_VERSION`
- `ENABLE_AI_CACHING`
- `ENABLE_BATCH_MODE`
- `TECH_SPEC_SCOPE_MODE`
- `FUNCTIONAL_SPEC_MAX_CHARS`

## Usage

### Interactive mode

```powershell
.\venv\Scripts\python.exe main.py
```

### Generate a specification

```powershell
.\venv\Scripts\python.exe main.py run ".\sample\Sample 2\gSAP_eCustoms_MIC.zip" --output ".\output\Sample 2" --no-color
```

### Generate diagrams only

```powershell
.\venv\Scripts\python.exe main.py diagrams ".\sample\Sample 2\gSAP_eCustoms_MIC.zip" --output ".\output\Sample 2" --no-color
```

### Inspect discovered artifacts

```powershell
.\venv\Scripts\python.exe main.py inspect ".\sample\Sample 2\gSAP_eCustoms_MIC.zip" --no-color
```

### Validate configuration and parser health

```powershell
.\venv\Scripts\python.exe main.py diagnostics --no-color
```

## CLI commands

```text
interactive
run
validate
inspect
diagrams
diagnostics
cache
config
inputs
```

## Output layout

Generated files are intended to live under one root output folder:

```text
output/
  Sample 1/
  Sample 2/
  Sample 3/
  Sample 4/
```

Each sample folder can contain:

- `<iflow>_TechSpec.docx`
- `<iflow>_integration_flow.png`
- `<iflow>_sender.png`
- `<iflow>_receiver.png`

## Project structure

```text
main.py
config/
  settings.py
src/
  ai_generator.py
  artifact_extractor.py
  diagram_generator.py
  document_builder.py
  functional_spec_parser.py
  iflow_parser.py
  zip_handler.py
sample/
output/
temp/
```

## Key implementation details

### Parser

`src/iflow_parser.py` extracts:

- processes
- sequence flows
- message flows
- sender properties
- receiver properties
- mapping properties
- exception subprocess details
- metadata

### Document builder

`src/document_builder.py` is responsible for:

- document structure
- sender/receiver tables
- mapping summaries and relation tables
- Groovy section formatting
- appendix sections
- externalized parameter usage tables
- removing noisy internal property content

### Diagram generator

`src/diagram_generator.py` renders:

- integration flow diagram
- sender diagram
- receiver diagram
- local process diagrams where supported

## Notes on generated content

- Structured tables and resolved technical values are derived from parsed source artifacts.
- Some narrative sections are AI-generated or fallback-generated summaries.
- If the AI service is unavailable, document generation still continues using fallback content.

## Troubleshooting

### Permission denied while saving a document

- Close the `.docx` file in Microsoft Word
- Remove any temporary `~$` lock file in the output folder
- Re-run the command

### AI rate limit or 429 error

- Re-run later
- Cached runs may still succeed
- The generator can fall back to non-AI section content for core technical output

### No iFlow found

Make sure the project contains an `.iflw` file under a scenario flow path similar to:

```text
src/main/resources/scenarioflows/integrationflow/
```

## Recommended local commands

```powershell
.\venv\Scripts\python.exe main.py diagnostics --no-color
.\venv\Scripts\python.exe main.py inspect ".\sample\Sample 1\Foundation_BusinessDocumentPDF_IDT_Subscriber (2)" --no-color
.\venv\Scripts\python.exe main.py run ".\sample\Sample 4\gSAP_SalesConsignment_SYNRJ" --output ".\output\Sample 4" --no-color
```

## License

MIT
