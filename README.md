# SAP CPI Specification Generator

Automatically generates comprehensive enterprise-grade technical specification documents from SAP CPI integration flow files using Generative AI.

## 🚀 What's New

### Performance Improvements
| Metric | Legacy | Current | Improvement |
|--------|-----|-----|-------------|
| API Calls | 14 | 1-2 | 85% reduction |
| First Run | ~30s | ~8s | 3.7x faster |
| Cached Run | ~5s | ~1s | 5x faster |
| API Cost | ~$0.14 | ~$0.02 | 85% savings |

### New Features
- **Batch Processing**: Single API call generates entire specification
- **Enterprise Template**: Follows Syngenta enterprise documentation standard
- **Gemini 2.0 Flash Thinking**: Support for thinking model (experimental)
- **Enhanced Prompts**: Professional prompt engineering for accuracy
- **Optional Functional Spec Context**: Enrich AI generation from functional spec files/folders
- **Streaming Support**: Optional streaming responses for better UX
- **Validation Tools**: iFlow configuration validation

## Features

- **ZIP/Directory Support**: Process SAP CPI projects from ZIP files or extracted directories
- **Dynamic Process Extraction**: Automatically discovers and documents all integration processes
- **XML Parsing**: Extract metadata, participants, message flows, processes from iFlow files
- **Artifact Extraction**: Parse Groovy scripts, XSD schemas, and runtime parameters
- **AI-Powered Documentation**: Generate comprehensive technical descriptions using Gemini AI
- **AI Response Caching**: Cache AI responses for faster re-runs and cost efficiency
- **Professional Documents**: Create formatted Word documents matching SAP standards
- **Production Ready**: Comprehensive error handling, logging, and validation

## Document Structure (Enterprise Template)

The generated technical specification follows enterprise documentation standards:

1. **Header Information**
   - 1.1 Executive Summary
   - 1.2 Purpose
2. **Business Process Overview**
   - 2.1 Current Scenario
   - 2.2 To-Be Scenario
3. **Functional Overview**
   - 3.1 Interface Requirement
   - 3.2 Functional Description
   - 3.3 Process Flow
   - 3.4 Functional Assumptions
4. **Technical Overview**
   - 4.1 High Level Design
   - 4.2 Security Configuration
5. **Development Overview**
   - 5.1 Technical Flow Description
   - 5.2 Integration Processes (dynamic - all discovered)
   - 5.3 Sender Details
   - 5.4 Receiver Details
   - 5.5 Mapping Details
   - 5.6 Groovy Scripts
   - 5.7 Error Handling
6. **Metadata**
7. **Appendix**

## Quick Start

### 1. Install Python 3.10+

Ensure Python 3.10 or higher is installed.

### 2. Create Virtual Environment

```bash
# Windows
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1

# Linux/Mac
python3.10 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Key

Create a `.env` file with your Gemini API key:
```bash
cp .env.example .env
# Edit .env and add your API key
```

Or set environment variable:
```bash
export GEMINI_API_KEY=your_api_key_here
```

### 5. Run Generator

```bash
# Interactive CLI (arrow keys + Enter)
python main.py

# Enterprise generator (direct command)
python main.py project.zip
```

## Usage

### Command Line Options

```bash
python main.py <command> [options]

Commands:
   interactive            Start interactive arrow-key menu loop
   run <input_path> [output_path]
                                     Generate technical specification document
   validate <input_path>  Validate input + configuration without generation
   inspect <input_path>   Inspect discovered artifacts and iFlow summary
   diagrams <input_path>  Generate integration-flow PNG diagram
   diagnostics            Run full system diagnostics
   cache [show|clear]     Show or clear local AI cache files
   config [show|validate] Show runtime config or validate it
   inputs [path]          Discover iFlow files and functional-spec candidates

Global option:
   --no-color             Disable colored CLI output

Run command options:
   -o, --output PATH      Output directory
   --functional-spec PATH Optional override functional specification file/folder
   --clear-cache          Clear AI cache before processing
   -v, --verbose          Enable verbose logging
```

Legacy compatibility is preserved:

```bash
python main.py <input_path> [output_path] [run options]
python main.py --show-config
```

Interactive navigation:
- Use Up/Down arrow keys to move through menu options.
- Press Enter to execute the selected action.
- After each action, choose whether to return to menu or exit.

### Examples

```bash
# Start interactive loop menu
python main.py

# Explicit interactive command
python main.py interactive

# Process a ZIP file
python main.py project.zip

# Process an extracted directory
python main.py run ./Foundation_BusinessDocumentPDF_IDT_Subscriber

# Process with positional output directory
python main.py run project.zip ./specs

# Specify output directory with verbose logging
python main.py run project.zip --output ./specs -v

# Optional manual override for functional specification context
python main.py run project.zip --functional-spec "./Functional Specification GSAP_eCustoms_MIC.doc"

# Validate setup before generation
python main.py validate project.zip

# Inspect iFlow/artifact summary without generating document
python main.py inspect project.zip

# Generate standalone integration-flow diagram
python main.py diagrams project.zip --output ./output

# Cache operations
python main.py cache show
python main.py cache clear

# View/validate configuration
python main.py config show
python main.py config validate

# Run diagnostics
python main.py diagnostics
```

## Configuration

Functional specification discovery behavior:
- Auto-detected by default when you do not provide --functional-spec.
- Search scope: input folder (or ZIP parent) and one parent folder.
- If no functional specification is found, generation continues normally.
- If found, content is added as extra AI context to improve document quality.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | - | Your Gemini API key |
| `AI_MODEL` | No | `gemini-2.0-flash` | AI model to use |
| `DOC_AUTHOR` | No | `Generated by AI` | Document author |
| `DOC_VERSION` | No | `1.0` | Document version |
| `ENABLE_AI_CACHING` | No | `true` | Cache AI responses |
| `ENABLE_BATCH_MODE` | No | `true` | Use batch API processing |
| `ENABLE_STREAMING` | No | `false` | Enable streaming responses |
| `USE_THINKING_MODEL` | No | `false` | Use Gemini thinking model |
| `AI_MAX_RETRIES` | No | `3` | Max API retry attempts |
| `AI_SENTENCE_LIMIT` | No | `5` | Sentences per AI summary |
| `FUNCTIONAL_SPEC_MAX_CHARS` | No | `15000` | Max characters from optional functional spec context |

### Configuration File

Edit `config/settings.py` for advanced configuration.

## Project Structure

```
├── main.py                 # Unified CLI entry point (run/inspect/diagrams/cache/config)
├── requirements.txt        # Python dependencies
├── .env                    # API keys (create from .env.example)
├── .env.example            # Environment template
├── config/
│   ├── __init__.py
│   └── settings.py         # Configuration settings
├── src/
│   ├── __init__.py
│   ├── zip_handler.py      # ZIP extraction and artifact discovery
│   ├── iflow_parser.py     # BPMN2 XML parsing
│   ├── artifact_extractor.py   # Groovy/XSD/parameter extraction
│   ├── ai_generator.py     # Optimized AI generation with batch processing
│   ├── document_builder.py # Enterprise document builder
│   └── diagram_generator.py # BPMN-style diagram generation
├── output/                 # Generated documents
├── temp/                   # Temporary files and AI cache
├── sample/                 # Sample iFlow for testing
└── tests/                  # Unit tests
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Input error (file not found, invalid format) |
| 2 | Configuration error (missing API key) |
| 3 | Processing error (parsing, AI, document) |

## Troubleshooting

### Module not found error
Ensure virtual environment is activated:
```bash
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac
```

### API key error
Ensure `.env` file contains valid `GEMINI_API_KEY`:
```bash
python main.py --show-config  # Verify API key is set
```

### No iFlow found
Ensure input contains `.iflw` file:
```
project/
└── src/main/resources/scenarioflows/integrationflow/
    └── *.iflw
```

### AI generation timeout
- Check internet connection
- Increase `AI_MAX_RETRIES` in `.env`
- Check Gemini API status

### Document generation fails
- Ensure output directory is writable
- Close any open Word documents
- Check disk space

## Performance

- First run: ~8-12 seconds (typically 1-2 AI API calls in batch mode)
- Cached run: ~1-2 seconds
- AI caching reduces API costs significantly

## Requirements

- Python 3.10+
- Gemini API key (free tier available)
- SAP CPI project files (ZIP or extracted directory)

## License

MIT License
