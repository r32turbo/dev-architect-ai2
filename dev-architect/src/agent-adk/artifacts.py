"""
artifacts.py – Canonical Structured Artifact Format for Orchestration

This module defines compact JSON/YAML artifact formats that replace markdown-heavy
information propagation between agents. Artifacts are designed to be:
  - Minimal: only essential system entities (services, APIs, schemas, config)
  - Parseable: machine-readable JSON suitable for downstream consumption
  - Composable: each section can be consumed independently by specialized agents
  - Efficient: ~2-4x more compact than equivalent markdown prose

Primary use case: lld_agent consumes SystemArtifact instead of 12k+ char markdown blobs.
This reduces effective payload by ~70% and enables parallel agent execution.

Expected improvements:
  - lld_agent runtime: ~133s → ~50-60s (55% reduction)
  - Effective downstream payload: ~17k chars → ~5-6k chars
  - Total orchestration runtime: ~225s → ~150-170s
"""

import json
from typing import Any, Optional


class ServiceEntity:
    """Describes a backend service/microservice."""
    def __init__(
        self,
        name: str,
        responsibility: str,
        key_endpoints: Optional[list[str]] = None,
        key_models: Optional[list[str]] = None,
    ):
        self.name = name
        self.responsibility = responsibility
        self.key_endpoints = key_endpoints or []
        self.key_models = key_models or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "responsibility": self.responsibility,
            "key_endpoints": self.key_endpoints,
            "key_models": self.key_models,
        }


class SchemaEntity:
    """Describes a data model or schema."""
    def __init__(
        self,
        name: str,
        entity_type: str,  # "table", "model", "event", "dto"
        key_fields: Optional[list[dict[str, str]]] = None,
    ):
        self.name = name
        self.entity_type = entity_type
        self.key_fields = key_fields or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "key_fields": self.key_fields,
        }


class APIEntity:
    """Describes an API endpoint or contract."""
    def __init__(
        self,
        path: str,
        method: str,
        purpose: str,
        auth_required: bool = True,
    ):
        self.path = path
        self.method = method
        self.purpose = purpose
        self.auth_required = auth_required

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "method": self.method,
            "purpose": self.purpose,
            "auth_required": self.auth_required,
        }


class SystemArtifact:
    """
    Canonical structured artifact summarizing system architecture.
    
    Replaces large narrative markdown blobs with compact JSON structure.
    Designed for downstream consumption by lld_agent, backend_lld, generic_lld.
    
    Total size target: ~4-6k chars (vs. ~15-20k for markdown narrative).
    """
    def __init__(
        self,
        project_name: str,
        summary: str,
        services: Optional[list[ServiceEntity]] = None,
        schemas: Optional[list[SchemaEntity]] = None,
        apis: Optional[list[APIEntity]] = None,
        integrations: Optional[list[str]] = None,
        deployment_target: Optional[str] = None,
        scalability_notes: Optional[str] = None,
    ):
        self.project_name = project_name
        self.summary = summary
        self.services = services or []
        self.schemas = schemas or []
        self.apis = apis or []
        self.integrations = integrations or []
        self.deployment_target = deployment_target or "Kubernetes"
        self.scalability_notes = scalability_notes or ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "summary": self.summary,
            "services": [s.to_dict() for s in self.services],
            "schemas": [sch.to_dict() for sch in self.schemas],
            "apis": [a.to_dict() for a in self.apis],
            "integrations": self.integrations,
            "deployment_target": self.deployment_target,
            "scalability_notes": self.scalability_notes,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize artifact to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_compact_json(self) -> str:
        """Serialize artifact to compact JSON (no whitespace)."""
        return json.dumps(self.to_dict(), separators=(',', ':'))

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SystemArtifact":
        """Deserialize artifact from dict."""
        artifact = SystemArtifact(
            project_name=data.get("project_name", ""),
            summary=data.get("summary", ""),
            integrations=data.get("integrations", []),
            deployment_target=data.get("deployment_target", "Kubernetes"),
            scalability_notes=data.get("scalability_notes", ""),
        )
        
        for svc_dict in data.get("services", []):
            artifact.services.append(ServiceEntity(
                name=svc_dict.get("name", ""),
                responsibility=svc_dict.get("responsibility", ""),
                key_endpoints=svc_dict.get("key_endpoints", []),
                key_models=svc_dict.get("key_models", []),
            ))
        
        for sch_dict in data.get("schemas", []):
            artifact.schemas.append(SchemaEntity(
                name=sch_dict.get("name", ""),
                entity_type=sch_dict.get("entity_type", ""),
                key_fields=sch_dict.get("key_fields", []),
            ))
        
        for api_dict in data.get("apis", []):
            artifact.apis.append(APIEntity(
                path=api_dict.get("path", ""),
                method=api_dict.get("method", ""),
                purpose=api_dict.get("purpose", ""),
                auth_required=api_dict.get("auth_required", True),
            ))
        
        return artifact

    @staticmethod
    def from_json(json_str: str) -> "SystemArtifact":
        """Deserialize artifact from JSON string."""
        data = json.loads(json_str)
        return SystemArtifact.from_dict(data)

    def size_estimate(self) -> dict[str, int]:
        """Estimate artifact size in bytes."""
        compact_json = self.to_compact_json()
        pretty_json = self.to_json(indent=2)
        return {
            "compact_json_bytes": len(compact_json.encode('utf-8')),
            "pretty_json_bytes": len(pretty_json.encode('utf-8')),
            "character_count": len(compact_json),
        }


def extract_artifact_from_markdown(markdown_text: str, project_name: str = "Unknown") -> SystemArtifact:
    """
    Extract structured artifact from markdown output.
    
    This is a simplified extractor for transitioning from markdown to structured artifacts.
    In production, use LLM-based extraction with structured output for higher fidelity.
    
    Current implementation: baseline fallback for backward compatibility.
    """
    lines = markdown_text.split('\n')
    summary = "\n".join(lines[:min(5, len(lines))]).strip()[:200]
    
    artifact = SystemArtifact(
        project_name=project_name,
        summary=summary,
    )
    
    # Minimal extraction: look for service names, API endpoints, model names
    # Full extraction should use LLM with structured output
    for line in lines:
        if 'service' in line.lower() or 'component' in line.lower():
            parts = line.split(':')
            if len(parts) >= 2:
                name = parts[0].strip().replace('#', '').replace('-', '').strip()
                if name and len(name) < 50:
                    artifact.services.append(ServiceEntity(
                        name=name,
                        responsibility=parts[1].strip()[:100],
                    ))
    
    return artifact
