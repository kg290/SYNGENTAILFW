"""
AI Generator - Optimized version with batch processing, streaming, and improved prompts.

Key Improvements:
- Batch API calls: 14 calls to 1-2 calls
- Streaming responses for better UX
- Structured JSON output
- Gemini 2.0 Flash Thinking support
- Enhanced prompt engineering
- Smart caching with semantic keys
- Syngenta-standard document structure support
"""

import hashlib
import json
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, Generator, List
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from google.genai import types
from config.settings import (
    GEMINI_API_KEY, AI_MODEL, AI_MODEL_THINKING, TEMP_DIR,
    ENABLE_AI_CACHING, AI_MAX_RETRIES, AI_SENTENCE_LIMIT,
    ENABLE_BATCH_MODE, ENABLE_STREAMING, USE_THINKING_MODEL
)

logger = logging.getLogger(__name__)


class AIGeneratorError(Exception):
    """Custom exception for AI generation failures."""
    pass


# ============================================================================
# OPTIMIZED BATCH PROMPT - SINGLE API CALL FOR ENTIRE DOCUMENT
# ============================================================================

COMPREHENSIVE_BATCH_PROMPT = """You are an expert SAP CPI Integration Suite technical writer creating enterprise-grade documentation.

## iFlow Name: {iflow_name}

## Complete iFlow XML:
```xml
{xml_content}
```

## Groovy Scripts:
{groovy_scripts_info}

## Functional Specification Source Context:
{functional_spec_info}

## Functional Specification Structured Analysis:
{functional_spec_analysis_info}

## Project File Analysis Context (all discovered files):
{artifact_analysis_info}

## Your Task:
Generate a COMPLETE technical specification following enterprise standards. Analyze the iFlow XML, all supplied artifacts, and functional-spec evidence thoroughly.

Return a JSON object with these EXACT keys (analyze XML carefully for each):

{{
  "executive_summary": "2-3 sentences: What does this iFlow do? What systems does it connect? What business problem does it solve?",
  
  "purpose": "1-2 sentences: Technical purpose of this specification document.",
  
  "current_scenario": "What exists before this integration? (e.g., 'Manual data transfer' or 'No automated integration')",
  
  "tobe_scenario": "What this integration enables. Be specific about the data flow.",
  
  "interface_requirement": "Business requirement driving this integration. What triggered the need?",
  
  "functional_description": "Detailed description of what data is processed and how. 3-5 sentences.",
  
  "process_flow": {{
    "steps": [
      "Step 1: Source system triggers...",
      "Step 2: Integration Suite receives...",
      "Step 3: Data is transformed...",
      "Step 4: Target system receives..."
    ],
    "source_system": "Name of source system",
    "target_system": "Name of target system",
    "trigger": "What triggers this flow (schedule/event/manual)"
  }},
  
  "functional_assumptions": {{
    "frequency": "How often does this run? (real-time/scheduled/on-demand)",
    "volume": "Expected message volume (messages per day/hour)",
    "processing_type": "Sync/Async, XML/JSON/etc",
    "performance": "Expected performance requirements"
  }},

    "functional_spec_alignment": {{
        "requirement_traceability": ["Requirement signals from functional spec and where they appear in iFlow/artifacts"],
        "assumptions_used": ["Assumptions inferred from functional spec and supported by technical artifacts"],
        "open_questions": ["Gaps or ambiguities that are not explicit in artifacts"]
    }},
  
  "high_level_design": "Technical architecture overview. Describe adapters, protocols, and flow. 3-4 sentences.",
  
  "technical_dependencies": "List any dependencies (certificates, credentials, endpoints, etc.)",
  
  "security_config": {{
    "authentication": "OAuth2/Basic Auth/Certificate/API Key/etc",
    "authorization": "How access is controlled",
    "encryption": "TLS/SSL details if any"
  }},
  
  "technical_flow_description": "Step-by-step technical flow. Be VERY specific about each component.",
  
  "integration_processes": [
    {{
      "name": "Process name from XML",
      "description": "What this process does. 2-3 sentences.",
      "steps": ["Step 1", "Step 2", "etc"],
      "key_activities": ["Content Modifier", "Mapping", "Script", "etc"]
    }}
  ],
  
  "sender_details": {{
    "system": "Source system name",
    "adapter_type": "SOAP/HTTP/SFTP/etc",
    "address": "Endpoint address pattern",
    "protocol": "Protocol used",
    "authentication": "Auth method",
    "description": "2-3 sentences about sender configuration"
  }},
  
  "receiver_details": {{
    "system": "Target system name", 
    "adapter_type": "HTTP/HTTPS/SFTP/etc",
    "address": "Target endpoint pattern",
    "protocol": "Protocol used",
    "authentication": "Auth method",
    "description": "2-3 sentences about receiver configuration"
  }},
  
  "mapping_details": {{
    "description": "What mappings exist and what they transform. 2-3 sentences.",
    "source_format": "XML/JSON/CSV/etc",
    "target_format": "XML/JSON/CSV/etc",
    "transformations": ["List of key transformations"]
  }},

    "artifact_coverage": {{
        "analyzed_file_types": ["Key file types analyzed across the provided folder"],
        "critical_non_iflow_artifacts": ["Important files beyond .iflw and why they matter"],
        "observations": ["Technical observations grounded in those files"]
    }},
  
  "groovy_scripts": {{
    "overview": "How Groovy scripts are used in this iFlow. 2 sentences.",
    "scripts": [
      {{
        "name": "Script name",
        "purpose": "What this script does. 2-3 sentences.",
        "key_operations": ["Operation 1", "Operation 2"]
      }}
    ]
  }},
  
  "error_handling": {{
    "description": "How errors are handled in this iFlow. 2-3 sentences.",
    "exception_handling": "Exception subprocess details if any",
    "alerting": "How alerts/notifications work",
    "retry_logic": "Any retry mechanisms"
  }},
  
  "validation_and_checks": {{
    "input_validation": "How input data is validated",
    "business_rules": "Any business rules applied",
    "data_quality": "Data quality checks if any"
  }},
  
  "metadata": {{
    "version": "Version from XML or '1.0'",
    "package": "Package name if found",
    "author": "Author if found",
    "description": "Description from XML metadata"
  }},
  
  "appendix": {{
    "artifacts": ["List all artifacts: scripts, schemas, mappings"],
    "glossary": ["Key terms used in this document"],
    "references": "Any reference documentation"
  }}
}}

CRITICAL INSTRUCTIONS:
1. Return ONLY valid JSON - no markdown, no code blocks, no explanations
2. Analyze XML and supplied artifact context THOROUGHLY - extract real values, don't make up data
3. If a field has no data in XML, say "Not configured" or "Not found in iFlow"
4. Be SPECIFIC - use actual names, values, and configurations from the XML
5. For scripts, describe what they ACTUALLY do based on the code
6. Use functional-spec context and structured analysis to improve business/process understanding, but do not contradict explicit iFlow XML technical configuration
7. Ensure all JSON keys use double quotes and strings are properly escaped
8. Include meaningful requirement traceability and artifact coverage grounded in provided evidence
"""


SECTION_PROMPT_TEMPLATE = """You are an SAP CPI technical writer. Analyze this {section_name} and provide enterprise-grade documentation.

## iFlow: {iflow_name}

## XML Content:
```xml
{xml_fragment}
```

## Provide:
1. **Overview**: What is this section about? (1-2 sentences)
2. **Details**: Key configurations and settings (bullet points)
3. **Technical Notes**: Important technical considerations

Be SPECIFIC - use actual values from the XML. Limit to {sentence_limit} sentences.
Focus areas: {focus_areas}
"""


GROOVY_ANALYSIS_PROMPT = """Analyze this SAP CPI Groovy script and explain its purpose.

## Script: {script_name}

```groovy
{script_content}
```

## Provide:
1. **Purpose**: What does this script do? (2-3 sentences)
2. **Key Logic**: 
   - Main function/entry point
   - Key variables used
   - Data transformations performed
3. **Integration Context**: How does this fit in the iFlow?
4. **Input/Output**: What data does it receive and return?

Be technical and specific. Limit to {sentence_limit} sentences.
"""


class AIGenerator:
    """Optimized AI Generator with batch processing and improved accuracy."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or (AI_MODEL_THINKING if USE_THINKING_MODEL else AI_MODEL)
        
        if not self.api_key:
            raise AIGeneratorError(
                "Gemini API key not configured. "
                "Set GEMINI_API_KEY in .env file or environment variable."
            )
        
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            raise AIGeneratorError(f"Failed to initialize Gemini client: {e}")
        
        self.cache_dir = TEMP_DIR / "ai_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.stats: Dict[str, Any] = {
            "cache_hits": 0, 
            "api_calls": 0, 
            "failures": 0,
            "batch_calls": 0,
            "tokens_saved": 0
        }
        
        logger.info(f"AI Generator initialized with model: {self.model}")
    
    # ========================================================================
    # CACHING SYSTEM
    # ========================================================================
    
    def _get_cache_key(self, prompt: str, prefix: str = "") -> str:
        """Generate semantic cache key from prompt."""
        key_content = f"{prefix}_{self.model}_{prompt}"
        return hashlib.sha256(key_content.encode()).hexdigest()[:16]
    
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Get cached response if available."""
        if not ENABLE_AI_CACHING:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding='utf-8'))
                self.stats["cache_hits"] += 1
                logger.debug(f"Cache hit: {cache_key}")
                return data.get('response')
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
                return None
        return None
    
    def _cache_response(
        self,
        cache_key: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Cache AI response with metadata."""
        if not ENABLE_AI_CACHING:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            cache_data = {
                'response': response,
                'model': self.model,
                'timestamp': time.time(),
                'metadata': metadata or {}
            }
            cache_file.write_text(json.dumps(cache_data, indent=2), encoding='utf-8')
            logger.debug(f"Cached response: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")
    
    # ========================================================================
    # CORE GENERATION METHODS
    # ========================================================================
    
    def generate(self, prompt: str, max_retries: Optional[int] = None, cache_prefix: str = "") -> str:
        """Generate content using AI with retry logic."""
        retry_limit = max_retries if max_retries is not None else AI_MAX_RETRIES
        
        cache_key = self._get_cache_key(prompt, cache_prefix)
        cached = self._get_cached_response(cache_key)
        if cached:
            return cached
        
        last_error: Optional[Exception] = None
        for attempt in range(retry_limit):
            try:
                self.stats["api_calls"] += 1
                logger.debug(f"API call attempt {attempt + 1}/{retry_limit}")
                
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "temperature": 0.2,  # Lower for more consistent output
                        "max_output_tokens": 8192,
                    },
                )
                
                result = response.text or ""
                if not result.strip():
                    raise ValueError("AI response was empty")
                self._cache_response(cache_key, result, {'prompt_length': len(prompt)})
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"AI generation attempt {attempt + 1} failed: {e}")
                if attempt < retry_limit - 1:
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
        
        self.stats["failures"] += 1
        error_msg = f"AI generation failed after {retry_limit} attempts: {last_error}"
        logger.error(error_msg)
        return f"[AI Generation Failed: {str(last_error)[:100] if last_error else 'Unknown error'}]"
    
    def generate_streaming(self, prompt: str) -> Generator[str, None, None]:
        """Stream AI response for better UX."""
        if not ENABLE_STREAMING:
            yield self.generate(prompt)
            return
        
        try:
            self.stats["api_calls"] += 1
            response_stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "max_output_tokens": 8192,
                },
            )
            
            accumulated = ""
            for chunk in response_stream:
                chunk_text = getattr(chunk, "text", None) or ""
                if chunk_text:
                    accumulated += chunk_text
                    yield accumulated

            if not accumulated:
                yield "[AI Generation Returned Empty Response]"
                    
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield f"[AI Generation Failed: {str(e)[:100]}]"
    
    # ========================================================================
    # BATCH GENERATION - SINGLE API CALL FOR ENTIRE DOCUMENT
    # ========================================================================
    
    def generate_all_sections_batch(
        self, 
        iflow_name: str, 
        xml_content: str,
        groovy_scripts: Optional[List[Dict[str, Any]]] = None,
        functional_spec_context: str = "",
        functional_spec_analysis: Optional[Dict[str, Any]] = None,
        artifact_analysis_context: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Generate ALL specification sections in a SINGLE API call.
        
        This is the KEY OPTIMIZATION - reduces 14+ API calls to 1 call.
        Returns comprehensive structured data for the entire document.
        """
        if not ENABLE_BATCH_MODE:
            logger.info("Batch mode disabled, falling back to individual calls")
            return None
        
        # Prepare groovy scripts info
        groovy_info = "No Groovy scripts found in this iFlow."
        if groovy_scripts:
            groovy_list = []
            for script in groovy_scripts:
                name = script.get('file_name', 'Unknown')
                content = script.get('content', '')
                # Include more content for better analysis
                truncated = content[:2000] if len(content) > 2000 else content
                groovy_list.append(f"### {name}\n```groovy\n{truncated}\n```")
            groovy_info = "\n\n".join(groovy_list)
        
        # Truncate XML if too large but keep as much as possible
        max_xml_chars = 40000
        if len(xml_content) > max_xml_chars:
            xml_content = xml_content[:max_xml_chars] + "\n<!-- XML truncated for processing -->"
            logger.warning(f"XML truncated to {max_xml_chars} chars")

        functional_spec_info = "Not provided."
        if functional_spec_context.strip():
            max_functional_chars = 15000
            functional_spec_info = functional_spec_context.strip()
            if len(functional_spec_info) > max_functional_chars:
                functional_spec_info = (
                    functional_spec_info[:max_functional_chars]
                    + "\n[Functional specification context truncated for processing]"
                )
                logger.warning(
                    f"Functional spec context truncated to {max_functional_chars} chars"
                )

        functional_spec_analysis_info = "Not provided."
        if functional_spec_analysis:
            try:
                rendered_analysis = json.dumps(
                    functional_spec_analysis,
                    ensure_ascii=True,
                    indent=2,
                )
            except Exception:
                rendered_analysis = str(functional_spec_analysis)

            max_analysis_chars = 8000
            functional_spec_analysis_info = rendered_analysis.strip()
            if len(functional_spec_analysis_info) > max_analysis_chars:
                functional_spec_analysis_info = (
                    functional_spec_analysis_info[:max_analysis_chars]
                    + "\n[Functional specification analysis truncated for processing]"
                )
                logger.warning(
                    f"Functional spec analysis truncated to {max_analysis_chars} chars"
                )

        artifact_analysis_info = "Not provided."
        if artifact_analysis_context.strip():
            max_artifact_chars = 12000
            artifact_analysis_info = artifact_analysis_context.strip()
            if len(artifact_analysis_info) > max_artifact_chars:
                artifact_analysis_info = (
                    artifact_analysis_info[:max_artifact_chars]
                    + "\n[Artifact analysis context truncated for processing]"
                )
                logger.warning(
                    f"Artifact analysis context truncated to {max_artifact_chars} chars"
                )
        
        # Build comprehensive batch prompt
        prompt = COMPREHENSIVE_BATCH_PROMPT.format(
            iflow_name=iflow_name,
            xml_content=xml_content,
            groovy_scripts_info=groovy_info,
            functional_spec_info=functional_spec_info,
            functional_spec_analysis_info=functional_spec_analysis_info,
            artifact_analysis_info=artifact_analysis_info,
        )
        
        # Check cache
        cache_key = self._get_cache_key(prompt, "batch")
        cached = self._get_cached_response(cache_key)
        if cached:
            try:
                cached_data = json.loads(cached)
                if isinstance(cached_data, dict):
                    return cached_data
                logger.warning("Cached batch response is not a dict, regenerating")
            except json.JSONDecodeError:
                logger.warning("Cached batch response invalid, regenerating")
        
        # Generate batch response
        logger.info("Generating complete specification in SINGLE API call...")
        self.stats["batch_calls"] += 1
        
        response_text = self.generate(prompt, cache_prefix="batch")
        
        # Parse JSON response
        try:
            # Clean response - handle various formats
            cleaned = response_text.strip()
            
            # Remove markdown code blocks
            if "```json" in cleaned:
                start = cleaned.find("```json") + 7
                end = cleaned.rfind("```")
                if end > start:
                    cleaned = cleaned[start:end].strip()
            elif "```" in cleaned:
                start = cleaned.find("```") + 3
                end = cleaned.rfind("```")
                if end > start:
                    cleaned = cleaned[start:end].strip()
            
            # Find JSON object boundaries
            json_start = cleaned.find('{')
            json_end = cleaned.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                cleaned = cleaned[json_start:json_end]
            
            result = json.loads(cleaned)
            if not isinstance(result, dict):
                logger.error("Batch response JSON is not an object")
                self.stats["failures"] += 1
                return None
            
            # Cache the parsed JSON
            self._cache_response(cache_key, json.dumps(result), {
                'type': 'batch',
                'iflow': iflow_name,
                'sections': len(result)
            })
            
            logger.info(f"Batch generation successful - {len(result)} sections generated")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch JSON: {e}")
            logger.debug(f"Raw response (first 1000 chars): {response_text[:1000]}")
            self.stats["failures"] += 1
            return None
    
    # ========================================================================
    # INDIVIDUAL SECTION GENERATORS (fallback/supplementary)
    # ========================================================================
    
    def summarize_section(
        self, 
        section_name: str, 
        xml_fragment: str, 
        extra_context: str = "",
        iflow_name: str = ""
    ) -> str:
        """Generate AI summary for a single section (used as fallback)."""
        max_xml_chars = 10000
        if len(xml_fragment) > max_xml_chars:
            xml_fragment = xml_fragment[:max_xml_chars] + "\n<!-- XML truncated -->"
        
        prompt = SECTION_PROMPT_TEMPLATE.format(
            section_name=section_name,
            iflow_name=iflow_name,
            xml_fragment=xml_fragment,
            sentence_limit=AI_SENTENCE_LIMIT,
            focus_areas=extra_context or "technical accuracy and completeness"
        )
        
        return self.generate(prompt, cache_prefix=f"section_{section_name}")
    
    def generate_groovy_explanation(self, script_name: str, script_content: str) -> str:
        """Generate detailed explanation for a Groovy script."""
        max_script_chars = 5000
        if len(script_content) > max_script_chars:
            script_content = script_content[:max_script_chars] + "\n// ... script truncated ..."
        
        prompt = GROOVY_ANALYSIS_PROMPT.format(
            script_name=script_name,
            script_content=script_content,
            sentence_limit=AI_SENTENCE_LIMIT + 2
        )
        
        return self.generate(prompt, cache_prefix=f"groovy_{script_name}")
    
    # ========================================================================
    # LEGACY COMPATIBILITY METHODS
    # ========================================================================
    
    def generate_overview(self, iflow_name: str, overview_xml: str) -> str:
        return self.summarize_section("Overview", overview_xml,
            f"Purpose of this technical specification for iFlow: {iflow_name}", iflow_name)
    
    def generate_high_level_design(self, iflow_name: str, design_xml: str) -> str:
        return self.summarize_section("High Level Design", design_xml,
            "Main components and message flow from Sender to Receiver", iflow_name)
    
    def generate_message_flow(self, message_flows_xml: str) -> str:
        return self.summarize_section("Message Flow", message_flows_xml)
    
    def generate_sender(self, sender_xml: str) -> str:
        return self.summarize_section("Sender", sender_xml,
            "Sender system, protocol, authentication, and configuration")
    
    def generate_receiver(self, receiver_xml: str) -> str:
        return self.summarize_section("Receiver", receiver_xml,
            "Receiver system, protocol, and endpoint configuration")
    
    def generate_mappings(self, mapping_xml: str) -> str:
        return self.summarize_section("Mappings", mapping_xml,
            "Data transformation and mapping logic")
    
    def generate_security(self, security_xml: str) -> str:
        return self.summarize_section("Security", security_xml)
    
    def generate_groovy_overview(self, iflow_name: str, components_xml: str) -> str:
        return self.summarize_section("Groovy Scripts", components_xml,
            f"How Groovy scripts are used in {iflow_name}", iflow_name)
    
    def generate_error_handling(self, exceptions_xml: str) -> str:
        return self.summarize_section("Error Handling", exceptions_xml,
            "Error handling mechanisms and exception subprocesses")
    
    def generate_metadata_summary(self, metadata_xml: str) -> str:
        return self.summarize_section("Metadata", metadata_xml)
    
    def generate_appendix(self, process_xml: str) -> str:
        return self.summarize_section("Appendix", process_xml,
            "Technical artifacts, mappings, and scripts")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def clear_cache(self) -> int:
        """Clear AI response cache."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        logger.info(f"Cleared {count} cached responses")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        stats: Dict[str, Any] = self.stats.copy()
        
        total_operations = stats['api_calls'] + stats['cache_hits']
        if total_operations > 0:
            stats['cache_hit_rate'] = round(stats['cache_hits'] / total_operations * 100, 1)
        else:
            stats['cache_hit_rate'] = 0
        
        if stats['batch_calls'] > 0:
            stats['estimated_calls_saved'] = stats['batch_calls'] * 13
        
        return stats
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get current model configuration."""
        return {
            'model': self.model,
            'is_thinking_model': USE_THINKING_MODEL,
            'batch_mode': ENABLE_BATCH_MODE,
            'streaming': ENABLE_STREAMING,
            'caching': ENABLE_AI_CACHING
        }
# Backward compatibility for older imports
AIGeneratorLatest = AIGenerator
