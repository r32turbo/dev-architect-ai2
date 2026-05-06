"""
system_architect.py – System Architecture Agent (STRICT HLD MODE)
"""

from __future__ import annotations

import os
import sys
import types
import importlib
import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from ..database.db import get_db, get_requirment_document, save_system_architecture_document

# ✅ IMPORT STATE
try:
    from .state import ArchitectState
except ImportError:
    from state import ArchitectState

# ✅ REGISTER ADK PATHS EARLY
ADK_ROOT = Path(__file__).resolve().parents[1] / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))

if "reusableagents" not in sys.modules:
    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(ADK_ROOT)]
    sys.modules["reusableagents"] = reusableagents_pkg

try:
    from reusableagents.context import AgentContext, SessionInfo, AuthInfo  # type: ignore
except ImportError:  # pragma: no cover
    AgentContext = None  # type: ignore
    SessionInfo = None  # type: ignore
    AuthInfo = None  # type: ignore

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore

# Define the system prompt
SYSTEM_ARCHITECT_PROMPT = """
You are a System Architecture Agent responsible for generating a High-Level Design (HLD) document.

STRICT INSTRUCTIONS:
- Output MUST be in the exact format given below.
- DO NOT skip any section.
- DO NOT add extra sections.
- DO NOT include placeholders like "appears to be".
- Use clear, professional, and complete statements.
- Replace generic examples with actual system-specific details based on the input.
- Maintain proper headings, numbering, and formatting exactly as shown.

OUTPUT FORMAT:

# System Architecture Report

## 1. System Overview
Provide a brief and clear description of the system, including its purpose and target users.

## 2. Functional Requirements
List all core functionalities of the system as bullet points.

## 3. Non-Functional Requirements
Specify performance, scalability, reliability, and security requirements.

## 4. High-Level Architecture
Describe the overall system structure including:
- Client (Web/Mobile)
- Backend Services
- Database
- External APIs
Also specify whether the system follows Monolithic or Microservices architecture.

## 5. System Components

### 5.1 Frontend
- Technology used
- Responsibilities:
  - UI rendering
  - API communication

### 5.2 Backend
- Technology used
- Responsibilities:
  - Business logic
  - Authentication
  - API handling

### 5.3 Database
- Type (SQL/NoSQL)
- Data stored:
  - Users
  - Transactions
  - Logs

### 5.4 APIs
- Type (REST/GraphQL)
- Purpose and usage

## 6. Data Flow
Provide step-by-step flow of how data moves through the system:
1. User sends request
2. API Gateway receives request
3. Backend processes logic
4. Database interaction
5. Response returned to user

## 7. Technology Stack
- Frontend:
- Backend:
- Database:
- Cloud/Hosting:

## 8. Scalability Considerations
- Load balancing
- Horizontal scaling
- Caching mechanisms (e.g., Redis)

## 9. Security Considerations
- Authentication (JWT/OAuth)
- Data encryption
- API security

## 10. Deployment Architecture
- Cloud infrastructure
- Containerization (Docker)
- CI/CD pipelines
"""

# ✅ CHUNKING UTILITY (ADDED)
def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[str]:
    """
    Split text into chunks with optional overlap.
    """
    overlap = min(overlap, chunk_size - 1)
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Find a good break point (sentence end)
            for i in range(min(overlap, chunk_size)):
                if text[end - i] in '.!?\n':
                    end -= i
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(0, end - overlap) if end < len(text) else end
    return chunks

warnings.filterwarnings(
    "ignore",
    message=r".*deprecated.*",
    category=Warning,
)

ADK_ROOT = Path(__file__).resolve().parents[1] / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))

if "reusableagents" not in sys.modules:
    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(ADK_ROOT)]
    sys.modules["reusableagents"] = reusableagents_pkg

logger = logging.getLogger(__name__)

# ---------------- LOAD ADK ----------------
def load_adk_components():
    react_mod = importlib.import_module("reusableagents.agents.react_agent")
    prompts_mod = importlib.import_module("reusableagents.prompts.base")
    config_mod = importlib.import_module("reusableagents.config.settings")
    validator_mod = importlib.import_module("reusableagents.agents.validator")
    llm_mod = importlib.import_module("reusableagents.llm.gemini")

    return (
        react_mod.ReusableReActAgent,
        prompts_mod.PromptBuilder,
        config_mod.AgentConfig,
        validator_mod.OutputValidator,
        config_mod.GeminiConfig,
        llm_mod.create_agent_llm,
        llm_mod.create_validator_llm,
    )

# ---------------- ENV ----------------
def load_environment():
    for path in [Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

# ---------------- BUILD AGENT ----------------
def build_agent(context: "AgentContext | None" = None):
    (
        ReusableReActAgent,
        PromptBuilder,
        AgentConfig,
        OutputValidator,
        GeminiConfig,
        create_agent_llm,
        create_validator_llm,
    ) = load_adk_components()

    gemini_config = GeminiConfig(
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "eds-alchemy"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        agent_model=os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"),
        validator_model=os.getenv("GEMINI_VALIDATOR_MODEL", "gemini-2.5-flash-lite"),
        agent_temperature=0.0,
        validator_temperature=0.0,
    )

    agent_llm = create_agent_llm(gemini_config)
    validator_llm = create_validator_llm(gemini_config)

    validator = OutputValidator(llm=validator_llm)

    prompt_builder = (
        PromptBuilder()
        .add_system(SYSTEM_ARCHITECT_PROMPT)
        .add_user("System Analyst Document:\n\n{input_document}")
    )

    return ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=prompt_builder,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=5,
            enable_validation=False,
            max_refinement_attempts=2,
        ),
    )


def create_context(
    user_input: str = "",
    requirement_doc: str = "",
    user_id: str = "api-user",
    session_metadata: dict | None = None,
) -> "AgentContext":
    """
    Create an AgentContext for the System Architecture Agent.
    """
    global AgentContext, SessionInfo, AuthInfo

    if AgentContext is None or SessionInfo is None or AuthInfo is None:
        try:
            from reusableagents.context import AgentContext as _AgentContext, SessionInfo as _SessionInfo, AuthInfo as _AuthInfo  # type: ignore
            AgentContext, SessionInfo, AuthInfo = _AgentContext, _SessionInfo, _AuthInfo
        except ImportError as exc:
            raise ImportError(
                "reusableagents.context imports failed; ensure the agent ADK is available"
            ) from exc

    metadata = {
        "source": "system_architect_agent",
        "requirement_doc": requirement_doc,
    }
    if session_metadata:
        metadata.update(session_metadata)

    return AgentContext(
        session=SessionInfo(metadata=metadata),
        auth=AuthInfo(
            user_id=user_id,
            roles=["lld-generator"],
            permissions=["generate", "read"],
        ),
        state={
            "user_input": user_input,
            "requirement_doc": requirement_doc,
        },
    )

# ---------------- NORMALIZATION ----------------
def normalize_output(text: str) -> str:
    return str(text or "").strip()

# ---------------- MAIN EXECUTION ----------------

def run_system_architect(
    context: "AgentContext | None" = None,
) -> str:
    load_environment()

    agent = build_agent(context)

    # Get input documents from context.state
    requirement_document = context.state.get("requirement_document") if context else None
    user_input = context.state.get("user_input") if context else None

    if not requirement_document:
        # try to retrieve the requirment document from the database
        db = get_db()
        doc = get_requirment_document(db, doc_id=int(context.session.metadata.get("requirement_doc", 0)))
        if doc:
            requirement_document = doc.requirment_document
            logger.info("Fetched requirement document from DB for architecture generation. ID=%d", doc.id)
        else:
            # Raise error if no input document is found
            raise ValueError("No requirment document found in context or database for architecture generation")

    if context and callable(getattr(context, "record", None)):
        context.record(
            agent_name="system_architect_agent",
            event="started",
            detail=str(requirement_document)[:150],
        )

    # 🔥 CHUNKING: If input is too long, process in chunks
    chunks = chunk_text(requirement_document, chunk_size=32000, overlap=500)
    if len(chunks) == 1:
        # Single chunk, process as before
        result = agent.run(
            user_input=user_input,
            requirement_document=requirement_document,
            context=context if context else None
        )
        output = normalize_output(
            result.output if hasattr(result, "output") else result
        )
    else:
        # Multiple chunks, process each and combine
        outputs = []
        for chunk in chunks:
            result = agent.run(
                input_document=chunk,
                context=context if context else None
            )
            outputs.append(normalize_output(
                result.output if hasattr(result, "output") else result
            ))
        output = "\n\n".join(outputs)
    # Save output to database
    db = get_db()
    doc = save_system_architecture_document(
        db=db,
        architecture_document=output,
        session_id=context.session.id if context else ""
    )

    # ✅ SAVE OUTPUT TO STATE ALSO
    context.state.set_output(output)
    if context and callable(getattr(context, "set_state", None)):
        context.set_state("system_architect.output", output)

    if context and callable(getattr(context, "record", None)):
        context.record(
            agent_name="system_architect_agent",
            event="completed"
        )

    return doc

# ---------------- MAIN ----------------
def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logger.info("Starting System Architect Agent")

    # ✅ NO NEED TO PASS INPUT NOW
    output = run_system_architect()

    if output:
        print("\n========== SYSTEM ARCHITECTURE OUTPUT ==========\n")
        print(output)
    else:
        print("No output generated.")

if __name__ == "__main__":
    main()