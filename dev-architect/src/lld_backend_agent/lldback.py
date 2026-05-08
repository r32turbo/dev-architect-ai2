"""
pp.py – Backend LLD Agent (STRICT GENERATOR MODE)
"""

from __future__ import annotations

import sys
import types
import importlib
import logging
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# ============================================================
# ✅ REGISTER ADK
# ============================================================

def register_agent_adk():
    if "reusableagents" in sys.modules:
        return

    base_path = Path(__file__).resolve()

    for i in range(1, 4):
        path = base_path.parents[i] / "agent-adk"
        if path.exists():
            pkg = types.ModuleType("reusableagents")
            pkg.__path__ = [str(path)]
            sys.modules["reusableagents"] = pkg
            return

    raise ModuleNotFoundError("agent-adk folder not found")


register_agent_adk()

# ✅ KEY FIX: import build_backend_lld_prompt instead of BACKEND_LLD_PROMPT
from .prompts import build_backend_lld_prompt, BACKEND_LLD_TASK
from .optimizer import optimize_backend_lld_output

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore


# ============================================================
# ✅ LOAD COMPONENTS
# ============================================================

def load_adk_components():
    react_mod   = importlib.import_module("reusableagents.agents.react_agent")
    config_mod  = importlib.import_module("reusableagents.config.settings")
    valid_mod   = importlib.import_module("reusableagents.agents.validator")
    llm_mod     = importlib.import_module("reusableagents.llm.gemini")

    return (
        react_mod.ReusableReActAgent,
        config_mod.AgentConfig,
        valid_mod.OutputValidator,
        config_mod.GeminiConfig,
        llm_mod.create_agent_llm,
        llm_mod.create_validator_llm,
    )


# ============================================================
# ✅ BUILD AGENT
# ✅ KEY FIX: accepts prompt parameter so lld_input is baked in
# ============================================================

def build_agent(prompt):
    (
        ReusableReActAgent,
        AgentConfig,
        OutputValidator,
        GeminiConfig,
        create_agent_llm,
        create_validator_llm,
    ) = load_adk_components()

    gemini_config = GeminiConfig(
        project_id="eds-alchemy",
        location="us-central1",
        agent_model="gemini-2.5-flash-lite",
        validator_model="gemini-2.5-flash-lite",
        agent_temperature=0.0,
        validator_temperature=0.0,
        max_output_tokens=int(os.getenv("BACKEND_LLD_MAX_OUTPUT_TOKENS", "4096")),
    )

    agent_llm     = create_agent_llm(gemini_config)
    validator_llm = create_validator_llm(gemini_config)
    validator     = OutputValidator(llm=validator_llm)

    enable_validation = str(
        os.getenv("BACKEND_LLD_ENABLE_VALIDATION", "false")
    ).strip().lower() in {"1", "true", "yes", "on"}

    return ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=prompt,          # ✅ baked-in prompt passed here
        validator=validator,
        config=AgentConfig(
            max_react_iterations=int(os.getenv("BACKEND_LLD_MAX_REACT_ITERATIONS", "2")),
            enable_validation=enable_validation,
            validation_score_threshold=0.5,
            max_refinement_attempts=int(os.getenv("BACKEND_LLD_MAX_REFINEMENT_ATTEMPTS", "0")),
        ),
    )


# ============================================================
# ✅ DEFAULT INPUT
# ============================================================

LLD_INPUT = """
This document provides details for a one-page marketing website built with Next.js.
The website includes hero section, about, services, and contact with Google Maps integration.
Focus on static content, performance, SEO, and responsiveness.
"""


# ============================================================
# ✅ CHUNKING UTILITY
# ============================================================

def chunk_text(text: str, chunk_size: int = 8000, overlap: int = 500) -> list[str]:
    env_chunk_size = str(os.getenv("BACKEND_LLD_CHUNK_SIZE", "")).strip()
    env_overlap = str(os.getenv("BACKEND_LLD_CHUNK_OVERLAP", "")).strip()
    if env_chunk_size:
        try:
            chunk_size = max(2000, int(env_chunk_size))
        except ValueError:
            pass
    if env_overlap:
        try:
            overlap = max(0, int(env_overlap))
        except ValueError:
            pass

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for i in range(min(overlap, chunk_size)):
                if end - i > start and text[end - i] in ".!?\n":
                    end = end - i + 1
                    break
            else:
                while end > start and text[end - 1] not in " \t\n":
                    end -= 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if overlap > 0 else end

    return chunks


def _resolve_lld_input(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:
    # Priority: explicit lld_input param > requirement_doc in context > lld_input in context
    if str(lld_input or "").strip():
        return str(lld_input).strip()

    if isinstance(getattr(context, "state", None), dict):
        # Accept an explicit requirements doc if provided by the caller
        req = str(context.state.get("requirement_doc", "")).strip()
        if req:
            return req

        # Accept system analyst or prior LLD outputs as fallback
        for key in ("lld.output", "system_analyst.output", "system_architect.output", "lld_input"):
            val = str(context.state.get(key, "")).strip()
            if val:
                return val

    return ""


def _extract_response_text(response: object) -> str:
    if hasattr(response, "output"):
        raw_output = response.output
    else:
        raw_output = response

    if isinstance(raw_output, str):
        return raw_output

    return str(raw_output or "")


def _backend_output_needs_refinement(output: str) -> bool:
    if not output:
        return True

    min_chars = int(os.getenv("BACKEND_LLD_MIN_OUTPUT_CHARS", "4500"))
    if len(output) < min_chars:
        return True

    required_sections = [
        "## 1. Service Architecture",
        "## 2. Data Models & Database Design",
        "## 3. API Design",
        "## 4. Event-Driven Architecture",
        "## 5. Workflows & State Transitions",
        "## 6. Security & Auth",
        "## 7. Scalability & Deployment",
        "## 8. Observability",
        "## 9. Reliability & Error Handling",
    ]
    normalized = _normalize_for_validation(output)
    return any(section.lower() not in normalized for section in required_sections)


def _normalize_for_validation(text: str) -> str:
    return text.lower()


# ============================================================
# ✅ RUN AGENT
# ✅ KEY FIX: build_backend_lld_prompt(chunk) called per chunk
#    so lld_input is always baked into the prompt — no {task}
#    substitution needed or relied upon.
# ============================================================

def run_backend_lld(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:

    resolved_input = _resolve_lld_input(lld_input, context)

    if not resolved_input:
        raise ValueError("lld_input is required")

    chunks = chunk_text(resolved_input, chunk_size=8000, overlap=500)
    outputs = []
    max_output_per_chunk = int(os.getenv("BACKEND_LLD_MAX_OUTPUT_PER_CHUNK", "18000"))
    
    for i, chunk in enumerate(chunks):

        # ✅ Build a fresh prompt with this chunk baked in
        prompt = build_backend_lld_prompt(chunk)

        # ✅ Build a fresh agent with that prompt
        agent = build_agent(prompt)

        # ✅ task string is now just a trigger label — the real
        #    content is already inside the user prompt above
        task_label = (
            f"Generate Backend LLD"
            if len(chunks) == 1
            else f"Generate Backend LLD — part {i + 1} of {len(chunks)}"
        )

        run_kwargs = {
            "task": task_label,
            "state": {"lld_input": chunk},
        }

        if context is not None:
            run_kwargs["context"] = context

        response = agent.run(**run_kwargs)

        raw_output = response.output if hasattr(response, "output") else response
        output = _extract_response_text(response)

        logger.warning(
            "Backend LLD response=%s raw_output_type=%s raw_output_len=%s normalized_output_len=%d normalized_output_preview=%r",
            type(response).__name__,
            type(raw_output).__name__,
            len(raw_output) if hasattr(raw_output, "__len__") else "n/a",
            len(output),
            output[:120],
        )

        # Enforce per-chunk output cap
        output_size = len(output)
        if output_size > max_output_per_chunk:
            logger.warning(
                "Backend LLD chunk %d exceeded output cap: %d > %d chars, truncating",
                i + 1,
                output_size,
                max_output_per_chunk,
            )
            sample = output[:max_output_per_chunk]
            logger.warning(
                "Backend LLD truncation sample len=%d preview_end=%r",
                len(sample),
                sample[-120:],
            )
            output = sample + "\n\n[... truncated ...]"
            logger.warning(
                "Backend LLD truncated output len=%d preview=%r",
                len(output),
                output[:120],
            )
        
        logger.info(
            "Backend LLD chunk %d: generated %d chars (cap=%d), token_est=%d",
            i + 1,
            len(output),
            max_output_per_chunk,
            len(output) // 4,
        )
        
        outputs.append(output)

    combined = "\n\n---\n\n".join(outputs)

    # Strip accidental review-style words to reduce verbosity
    blacklist = ["review", "strength", "weakness"]
    for word in blacklist:
        combined = combined.replace(word, "")

    max_total_output = int(os.getenv("BACKEND_LLD_MAX_TOTAL_OUTPUT", "18000"))
    combined_size = len(combined)

    # Validate the full generated output before compressing/truncating.
    if _backend_output_needs_refinement(combined):
        logger.warning(
            "Backend LLD output failed validation (length=%d). Retrying once with an expansion hint.",
            len(combined),
        )
        prompt = build_backend_lld_prompt(resolved_input).add_system(
            "The previous response was too brief or omitted required backend sections. "
            "Regenerate again with complete implementation detail for all required sections. "
            "Keep the same Markdown structure and preserve technical depth."
        )
        agent = build_agent(prompt)
        retry_task_label = "Regenerate Backend LLD with full required sections"

        retry_kwargs = {
            "task": retry_task_label,
            "state": {"lld_input": resolved_input},
        }
        if context is not None:
            retry_kwargs["context"] = context

        retry_response = agent.run(**retry_kwargs)

        retry_raw_output = retry_response.output if hasattr(retry_response, "output") else retry_response
        retry_output = _extract_response_text(retry_response)

        logger.warning(
            "Backend LLD retry response=%s raw_output_type=%s raw_output_len=%s normalized_output_len=%d normalized_output_preview=%r",
            type(retry_response).__name__,
            type(retry_raw_output).__name__,
            len(retry_raw_output) if hasattr(retry_raw_output, "__len__") else "n/a",
            len(retry_output),
            retry_output[:120],
        )

        if retry_output and not _backend_output_needs_refinement(retry_output):
            combined = retry_output.strip()
            combined_size = len(combined)
        else:
            logger.warning(
                "Backend LLD retry did not produce a valid expanded result; keeping original output."
            )

        if combined_size > max_total_output:
            combined = combined[:max_total_output] + "\n\n[... final output truncated ...]"

    # Compress valid backend output down to the target 6k-10k range if needed.
    if len(combined) > 10000:
        combined = optimize_backend_lld_output(combined, target_min=6000, target_max=10000)

    max_total_output = int(os.getenv("BACKEND_LLD_MAX_TOTAL_OUTPUT", "18000"))
    combined_size = len(combined)
    if combined_size > max_total_output:
        logger.warning(
            "Backend LLD total output exceeded cap: %d > %d chars, truncating final output",
            combined_size,
            max_total_output,
        )
        combined = combined[:max_total_output] + "\n\n[... final output truncated ...]"

    logger.info(
        "Backend LLD profiling: total=%d chars (cap=%d), token_est=%d, compression_applied",
        len(combined),
        max_total_output,
        len(combined) // 4,
    )

    return combined.strip()


# ============================================================
# ✅ MAIN
# ============================================================

def main():
    try:
        output = run_backend_lld(lld_input=LLD_INPUT)
        print(output)
    except Exception:
        logger.exception("Execution failed")
        raise


# ============================================================
# ✅ ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()