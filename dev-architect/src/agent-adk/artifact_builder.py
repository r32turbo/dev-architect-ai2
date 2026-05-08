"""
artifact_builder.py – Extract and synthesize structured artifacts from agent outputs

This module provides utilities to:
  1. Extract SystemArtifact from system_architect markdown output
  2. Summarize backend_lld output as structured artifact
  3. Cache and serve artifacts downstream to avoid re-parsing

Primary goal: reduce lld_agent input from ~12k chars (markdown) to ~5k chars (artifact).
"""

import json
import logging
import os
from typing import Optional, Any

logger = logging.getLogger(__name__)


def summarize_backend_output_to_artifact(
    backend_lld_output: str,
    project_name: str = "System",
) -> dict[str, Any]:
    """
    Summarize backend LLD markdown output into compact artifact.
    
    Extracts:
      - Service/component names and responsibilities
      - Database schemas (entity names only, no full schema)
      - API endpoints (path, method, purpose)
      - Integration points and external systems
      - Deployment target and scaling notes
    
    Returns compact dict (~3-5k chars) suitable for downstream agents.
    
    Example:
      backend_output (14k chars) → artifact (4k chars)
      Compression ratio: ~3.5x
    """
    try:
        from agent_adk.artifacts import SystemArtifact, ServiceEntity, SchemaEntity, APIEntity
    except ImportError:
        from artifacts import SystemArtifact, ServiceEntity, SchemaEntity, APIEntity

    lines = backend_lld_output.split('\n')
    
    # Extract summary from opening sections
    summary_lines = []
    for i, line in enumerate(lines[:20]):
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            summary_lines.append(stripped)
            if len(summary_lines) >= 3:
                break
    summary = ' '.join(summary_lines)[:300]
    
    # Extract services/components (look for section headers and bullets)
    services = []
    schemas = []
    apis = []
    integrations = []
    deployment_target = "Kubernetes"
    scalability_notes = ""
    
    current_section = ""
    for line in lines:
        lower = line.lower()
        
        # Detect section headers
        if line.startswith('###') or line.startswith('##'):
            current_section = lower
        
        # Extract service/component names
        if 'service' in current_section or 'component' in current_section:
            if line.startswith('-') or line.startswith('*'):
                name = line.lstrip('-* ').split(':')[0].strip()
                if name and 1 < len(name) < 50 and name not in [s.name for s in services]:
                    responsibility = line.lstrip('-* ').split(':')[1].strip() if ':' in line else ""
                    services.append(ServiceEntity(
                        name=name,
                        responsibility=responsibility[:100],
                    ))
        
        # Extract data models
        if 'data' in current_section or 'schema' in current_section or 'model' in current_section:
            if line.startswith('-') or line.startswith('*'):
                name = line.lstrip('-* ').split(':')[0].split('(')[0].strip()
                if name and 1 < len(name) < 50 and name not in [s.name for s in schemas]:
                    schemas.append(SchemaEntity(
                        name=name,
                        entity_type="table",
                    ))
        
        # Extract API endpoints
        if 'api' in current_section or 'endpoint' in current_section:
            if line.startswith('-') or line.startswith('*'):
                content = line.lstrip('-* ').strip()
                if '/' in content or 'GET' in content or 'POST' in content:
                    parts = content.split('-')
                    if len(parts) >= 2:
                        method_path = parts[0].strip()
                        purpose = parts[1].strip()[:80]
                        if any(m in method_path for m in ['GET', 'POST', 'PUT', 'DELETE']):
                            method = [m for m in ['GET', 'POST', 'PUT', 'DELETE'] if m in method_path][0]
                            path = method_path.replace(method, '').strip()
                            apis.append(APIEntity(path=path, method=method, purpose=purpose))
        
        # Extract integrations
        if 'integration' in current_section or 'external' in current_section:
            if line.startswith('-') or line.startswith('*'):
                name = line.lstrip('-* ').split(':')[0].strip()
                if name and name not in integrations:
                    integrations.append(name)
        
        # Extract deployment info
        if 'kubernetes' in lower or 'docker' in lower or 'deploy' in current_section:
            if 'kubernetes' in lower:
                deployment_target = "Kubernetes"
            if 'scalab' in current_section and line.startswith('-'):
                scalability_notes = line.lstrip('-* ').strip()[:200]
    
    artifact = SystemArtifact(
        project_name=project_name,
        summary=summary,
        services=services[:8],  # Limit to top services to keep size bounded
        schemas=schemas[:6],
        apis=apis[:8],
        integrations=integrations[:5],
        deployment_target=deployment_target,
        scalability_notes=scalability_notes,
    )
    
    size = artifact.size_estimate()
    logger.info(
        "Backend LLD summarized to artifact: compact=%d chars, ratio=%.2fx",
        size['character_count'],
        12000 / max(1, size['character_count']),  # Approximate original size
    )
    
    return artifact.to_dict()


def create_lld_input_prompt(
    artifact_dict: dict[str, Any],
    user_goal: str = "",
    requirement_doc: str = "",
) -> str:
    """
    Create LLD input prompt from structured artifact.
    
    Instead of passing raw markdown, format artifact as concise YAML-like structure
    that LLM can consume with minimal parsing overhead.
    
    Output: ~5-6k chars (vs. original 12k+ markdown blob)
    """
    lines = [
        "# System Architecture Summary",
        "",
        f"**Project:** {artifact_dict.get('project_name', 'System')}",
        "",
        f"**Summary:** {artifact_dict.get('summary', '')[:200]}",
        "",
        "## Key Services",
    ]
    
    for svc in artifact_dict.get('services', [])[:6]:
        lines.append(f"- **{svc.get('name')}**: {svc.get('responsibility', '')[:80]}")
    
    if artifact_dict.get('schemas'):
        lines.extend(["", "## Data Models"])
        for sch in artifact_dict.get('schemas', [])[:5]:
            lines.append(f"- {sch.get('name')} ({sch.get('entity_type')})")
    
    if artifact_dict.get('apis'):
        lines.extend(["", "## API Endpoints"])
        for api in artifact_dict.get('apis', [])[:6]:
            lines.append(f"- {api.get('method')} {api.get('path')}: {api.get('purpose', '')[:60]}")
    
    if artifact_dict.get('integrations'):
        lines.extend(["", "## Integrations"])
        for integ in artifact_dict.get('integrations', []):
            lines.append(f"- {integ}")
    
    lines.extend([
        "",
        f"**Deployment:** {artifact_dict.get('deployment_target', 'Kubernetes')}",
        "",
    ])
    
    if user_goal:
        lines.extend(["## User Goal", user_goal, ""])
    
    if requirement_doc:
        lines.extend(["## Requirements (Summary)", requirement_doc[:500], ""])
    
    result = '\n'.join(lines)
    logger.info(
        "LLD input prompt created from artifact: %d chars (original est. ~12000+)",
        len(result),
    )
    return result


def measure_payload_reduction(
    original_markdown: str,
    artifact_dict: dict[str, Any],
    artifact_based_prompt: str,
) -> dict[str, Any]:
    """
    Measure compression gains from structured artifact approach.
    
    Returns breakdown of original vs. new representation sizes.
    """
    import json as _json
    
    artifact_json = _json.dumps(artifact_dict, separators=(',', ':'))
    
    return {
        "original_markdown_chars": len(original_markdown),
        "artifact_json_chars": len(artifact_json),
        "artifact_prompt_chars": len(artifact_based_prompt),
        "compression_ratio_markdown_to_artifact": (
            len(original_markdown) / max(1, len(artifact_json))
        ),
        "compression_ratio_markdown_to_prompt": (
            len(original_markdown) / max(1, len(artifact_based_prompt))
        ),
    }
