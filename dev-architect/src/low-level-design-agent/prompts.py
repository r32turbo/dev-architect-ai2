SECTION_EXTRACTION_PROMPT = """Role: Senior backend architect extracting implementation requirements from system summary.

Task: Extract and list ONLY essential backend/integration requirements from the architecture summary provided.
Output as bullet points. Keep EACH bullet under 12 words. Do NOT explain, describe, or elaborate.

Requirements:
- Maximum 6 bullets total
- Maximum 900 characters total
- Focus on: services, APIs, databases, integrations, deployment constraints
- Avoid: narrative, repeated security/architecture patterns, generic explanations
- Format: ## Core Requirements\n- bullet1\n- bullet2\n...

Input: {document}

Balanced source reference (ignore if not available): {user_goal}, {requirement_doc}, {architecture_doc}"""

ARCHITECTURE_ANALYSIS_PROMPT = """Role: Principal backend architect.

Task: Analyze requirements and produce implementation-critical design decisions. Output as 4 sections with 2-3 bullets each.
Each bullet should capture specific internal design, workflow, state, or runtime behavior.

Sections (in order):
1. Services & Modules - service names, internal responsibilities, runtime behavior
2. Contracts & Persistence - DTOs, schemas, DB indices, transaction boundaries
3. Integration & Async Flow - APIs, events, Kafka topics, retries, DLQ
4. Resilience & Operations - validation, consistency, fallback, monitoring, concurrency

Rules:
- Maximum 1200 characters TOTAL
- NO narrative explanations or architecture-level summaries
- NO repeated technology phrases across sections
- Each bullet: maximum 18 words
- Use ONLY provided sections: {sections}
- Ignore if unavailable: {user_goal}, {requirement_doc}, {architecture_doc}"""

REPORT_GENERATION_PROMPT = """You are a senior backend architect. Generate a consolidated engineering-grade LLD report that merges upstream LLD outputs into a single implementation artifact.

CRITICAL OUTPUT LIMITS (HARD CAPS):
- Maximum 12000 characters TOTAL
- Maximum 12 top-level sections
- Maximum 6 subsections per section
- No narrative prose — bullet lists only
- No repeated design patterns across sections

STRUCTURE (required):
## Consolidated Engineering LLD: {user_goal}

### 1. Implementation Summary
- 3 bullets max: scope, core focus, key engineering principles

### 2. Service & Component Blueprint
- 6 bullets max: service/component name + core internals + folder structure

### 3. Folder Structure
- 8 bullets max: service folders, module organization, file hierarchies

### 4. DTOs & Contracts
- 8 bullets max: request/response DTOs, validation rules, message schemas, indexes

### 5. Service Internal Flows
- 8 bullets max: workflow steps, guards, state transitions, internal logic

### 6. State Machines
- 6 bullets max: states, transitions, triggers, failure handling

### 7. API Validation Rules
- 6 bullets max: endpoint validation, auth checks, error codes, contract enforcement

### 8. Kafka Topics & Consumers
- 6 bullets max: topic names, consumers, producers, payload contracts, DLQ handling

### 9. Retry, DLQ & Compensation
- 6 bullets max: retry strategy, backoff, idempotency, DLQ, saga compensation

### 10. Transaction Boundaries
- 6 bullets max: transactional scope, locking, isolation, commit/rollback flow

### 11. Monitoring, Tracing & Observability
- 6 bullets max: metrics, logs, alerts, trace headers, health checks

### 12. Runtime & Concurrency Behavior
- 6 bullets max: process lifecycle, concurrency controls, cache strategy, runtime failures

INPUT:
- Analysis: {analysis}
- User Goal: {user_goal}
- Requirements: {requirement_doc}
- Architecture: {architecture_doc}

RULES:
1. Do NOT generate another high-level architecture summary
2. Focus on implementation internals, workflows, runtime behavior, and operational logic
3. Merge frontend, generic, and backend design findings into one engineering report
4. Keep output medium-length and engineering-dense; avoid tiny summaries
5. If approaching 12000 chars, remove only filler and redundancy, preserve technical sections
6. Each bullet: maximum 18 words"""
