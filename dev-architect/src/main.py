"""
main.py – FastAPI entry point.

Entry points:
  POST /generate/frontend-lld  → generates and saves Frontend LLD to DB
  POST /generate/generic-lld   → generates and saves Generic LLD to DB
  POST /generate/backend-lld   → generates and saves Backend LLD to DB
  POST /generate/architecture  → generates and saves System Architecture to DB
  GET  /documents              → retrieve all saved documents
  GET  /documents/{id}         → retrieve a specific document by ID

Run:
    uvicorn main:app --reload
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

# ── Add folders to Python path ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR / "system_architect_agent"))
sys.path.insert(0, str(BASE_DIR / "frontend-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "generic-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "lld_backend_agent"))
sys.path.insert(0, str(BASE_DIR / "database"))
sys.path.insert(0, str(BASE_DIR / "supervisor-agent"))
sys.path.insert(0, str(BASE_DIR / "system_analyst_agent"))
sys.path.insert(0, str(BASE_DIR / "low-level-design-agent"))
sys.path.insert(0, str(BASE_DIR))
# Ensure the agent ADK is importable for reusableagents.context
ADK_ROOT = BASE_DIR / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))

# Dynamic loader helper to import modules by file path (avoids relying on
# hyphenated folder names or sys.path heuristics during static analysis).
import importlib.util

def _load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module

# System Architecture Agent
# ✅ FIX: import run_system_architect directly — same pattern as backend
from system_architect_agent import run_system_architect, create_context as create_architecture_context

# Frontend Agent
# Frontend Agent (loaded by file path)
_frontend_mod = _load_module_from_path(BASE_DIR / "frontend-lld-agent" / "frontend_graph.py", "frontend_graph")
build_frontend_agent = getattr(_frontend_mod, "build_agent")
create_frontend_context = getattr(_frontend_mod, "create_context")
run_frontend_agent = getattr(_frontend_mod, "run_agent")

# Generic Agent (loaded by file path)
_generic_mod = _load_module_from_path(BASE_DIR / "generic-lld-agent" / "generic_graph.py", "generic_graph")
build_generic_agent = getattr(_generic_mod, "build_agent")
create_generic_context = getattr(_generic_mod, "create_context")
run_generic_agent = getattr(_generic_mod, "run_agent")

# Backend LLD Agent
from lld_backend_agent.lldback import run_backend_lld

# Database Imports (loaded by file path)
_db_mod = _load_module_from_path(BASE_DIR / "database" / "db.py", "db")
init_db = getattr(_db_mod, "init_db")
get_db = getattr(_db_mod, "get_db")
save_lld_document = getattr(_db_mod, "save_lld_document")
get_lld_document = getattr(_db_mod, "get_lld_document")
get_all_lld_documents = getattr(_db_mod, "get_all_lld_documents")
save_system_architecture_document = getattr(_db_mod, "save_system_architecture_document")
get_system_architecture_document = getattr(_db_mod, "get_system_architecture_document")
get_all_system_architecture_documents = getattr(_db_mod, "get_all_system_architecture_documents")
save_lld_backend_document = getattr(_db_mod, "save_lld_backend_document")
get_lld_backend_document = getattr(_db_mod, "get_lld_backend_document")
get_all_lld_backend_documents = getattr(_db_mod, "get_all_lld_backend_documents")
get_latest_system_architecture_document = getattr(_db_mod, "get_latest_system_architecture_document")
save_requirement_document = getattr(_db_mod, "save_requirement_document")
get_requirement_document = getattr(_db_mod, "get_requirement_document")
get_all_requirement_documents = getattr(_db_mod, "get_all_requirement_documents")
# Supervisor, System Analyst, Low-level Design agents
_sup_mod = _load_module_from_path(BASE_DIR / "supervisor-agent" / "sup.py", "sup")
build_supervisor_agent = getattr(_sup_mod, "build_supervisor_agent")
_canonicalize_combined_output = getattr(_sup_mod, "_canonicalize_combined_output")
_ensure_agent_outputs = getattr(_sup_mod, "_ensure_agent_outputs")
_run_with_timeout = getattr(_sup_mod, "_run_with_timeout")
_is_complete_combined_output = getattr(_sup_mod, "_is_complete_combined_output")
_populate_lld_fields_from_output = getattr(_sup_mod, "_populate_lld_fields_from_output")

# System Analyst Agent (explicit import of implementation)
from system_analyst_agent.analyst_agent import build_agent as build_system_analyst_agent, run_system_analysis

# Low-level LLD pipeline
_lld_mod = _load_module_from_path(BASE_DIR / "low-level-design-agent" / "lld_createagent.py", "lld_createagent")
run_lld_pipeline = getattr(_lld_mod, "run_pipeline")

# Agent ADK context
import importlib
AgentContext = importlib.import_module("reusableagents.context").AgentContext

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dev Architect API",
    description="Generates and stores LLD documents using AI agents",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Request validation failed: %s %s", request.url.path, exc)
    # Return structured JSON so clients (and logs) show the exact validation errors
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Global agents
frontend_agent = None
generic_agent = None
supervisor_agent = None
system_analyst_agent = None
lld_app = None
# ✅ No global backend_agent or architecture_agent
# Both use their own run_* functions that build internally per call


# ── Startup Event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    global frontend_agent, generic_agent
    global supervisor_agent, system_analyst_agent, lld_app


    logger.info("Initializing database...")
    init_db()

    logger.info("Building agents...")
    frontend_agent = build_frontend_agent()
    generic_agent = build_generic_agent()
    # ✅ No backend_agent or architecture_agent at startup
    # They build internally per request via run_* functions

    try:
        logger.info("Building supervisor agent...")
        supervisor_agent = build_supervisor_agent()
    except Exception:
        logger.exception("Failed to build supervisor agent; continuing")

    try:
        logger.info("Building system analyst agent (warmup)...")
        system_analyst_agent = build_system_analyst_agent()
    except Exception:
        logger.exception("Failed to build system analyst agent; continuing")

    logger.info("All agents ready.")


# ── Pydantic Models ───────────────────────────────────────────────────────────
class LLDRequest(BaseModel):
    user_input: str
    requirement_doc: str = ""
    architecture_doc: str = ""
class AgentRequest(BaseModel):
    user_input: str
    requirement_doc: str = ""
    requirement_doc_id: str = ""

    architecture_doc: str = ""
    architecture_doc_id: str = ""  
class AgentResponse(BaseModel):
    id: int
    agent_type: str
    user_input: str
    output: str
    output_doc_id: str = ""
    session_id: str
    created_at: str


class SupervisorRequest(BaseModel):
    user_input: str


class SystemAnalystRequest(BaseModel):
    user_input: str


class AgentResponse(BaseModel):
    id: int
    agent_type: str
    user_input: str
    output: str
    session_id: str
    created_at: str


    class Config:
        from_attributes = True

# Models for System Architecture generation

class ArchitectureRequest(BaseModel):
    user_input: str
    requirement_doc_id: str = ""
    requirement_doc: str = ""


class ArchitectureResponse(BaseModel):
    id: int
    agent_type: str
    user_input: str
    output: str
    session_id: str
    created_at: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Dev Architect API is running"
    }


@app.post(
    "/generate/frontend-lld",
    response_model=AgentResponse
)
def generate_frontend_lld(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Frontend LLD and save to database.
    """
    request_id = str(uuid.uuid4())
    try:
        logger.info(
            "Received frontend LLD request: %s",
            request.user_input
        )

        ctx = create_frontend_context(
            user_id="api-user",
            session_metadata={
                "source": "fastapi",
                "endpoint": "/generate/frontend-lld",
                "request_id": request_id,
            },
        )

        response = run_frontend_agent(
            agent=frontend_agent,
            context=ctx,
            user_input=request.user_input,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
        )

        doc = save_lld_document(
            db=db,
            agent_type="frontend_lld",
            user_input=request.user_input,
            output=response.output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=str(ctx.session.session_id),
        )

        return AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
         logger.exception("Frontend LLD generation failed. request_id=%s", request_id)
         raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post(
    "/generate/generic-lld",
    response_model=AgentResponse
)
def generate_generic_lld(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Generic LLD and save to database.
    """
    request_id = str(uuid.uuid4())
    try:
        logger.info("Received generic LLD request. request_id=%s", request_id)
        logger.info(
            "Received generic LLD request: %s",
            request.user_input
        )

        ctx = create_generic_context(
            user_id="api-user",
            session_metadata={
                "source":     "fastapi",
                "endpoint":   "/generate/generic-lld",
                "request_id": request_id,
            },
        )

        response = run_generic_agent(
            agent=generic_agent,
            context=ctx,
            user_input=request.user_input,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
        )

        doc = save_lld_document(
            db=db,
            agent_type="generic_lld",
            user_input=request.user_input,
            output=response.output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=str(ctx.session.session_id),
        )

        return AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("Generic LLD generation failed. request_id=%s", request_id)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post(
    "/generate/backend-lld",
    response_model=AgentResponse
)
def generate_backend_lld(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    try:
        logger.info("Received backend LLD request: %s", request.user_input)

        # Combine user_input + requirement_doc if provided
        lld_input = request.user_input
        if request.requirement_doc.strip():
            lld_input = f"{request.user_input}\n\n{request.requirement_doc}"

        output = run_backend_lld(lld_input=lld_input)

        session_id = str(uuid.uuid4())
        
        # Get latest architecture if available
        arch_doc = get_latest_system_architecture_document(db=db)
        arch_doc_id = arch_doc.id if arch_doc else None

        doc = save_lld_backend_document(
            db=db,
            user_input=request.user_input,
            output=output,
            requirement_doc=request.requirement_doc,
            architecture_doc_id=arch_doc_id,
            session_id=session_id,
        )

        return AgentResponse(
            id=doc.id,
            agent_type="backend_lld",
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("Backend LLD generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/architecture",
    response_model=AgentResponse
)
def generate_architecture(
    request: ArchitectureRequest,
    db: Session = Depends(get_db)
):
    try:
        logger.info("Received architecture request: %s", request.user_input)

        # ✅ FIX: Create context from request and pass separately
        session_id = str(uuid.uuid4())
        context = create_architecture_context(
            user_input=request.user_input,
            requirement_doc=request.requirement_doc,
            user_id="api-user",
            session_metadata={"session_id": session_id}
        )

        output = run_system_architect(
            user_input=request.user_input,
            requirement_doc=request.requirement_doc,
            context=context
        )

        doc = save_system_architecture_document(
            db=db,
            analyst_document=request.user_input,
            output=output,
            session_id=session_id,
        )

        return AgentResponse(
            id=doc.id,
            agent_type="system_architecture",
            user_input=request.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("System Architecture generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/system-analyst",
    response_model=AgentResponse,
)
def generate_system_analyst(
    request: SystemAnalystRequest,
    db: Session = Depends(get_db),
):
    """
    Run system analyst agent and save result. Endpoint requires only `user_input`.
    """
    try:
        logger.info("Received system analyst request: %s", request.user_input)

        ctx = AgentContext(state={"user_goal": request.user_input})

        output = run_system_analysis(context=ctx)

        doc = save_lld_document(
            db=db,
            agent_type="system_analyst",
            user_input=request.user_input,
            output=output,
            requirement_doc="",
            architecture_doc="",
            session_id=str(ctx.session.session_id),
        )

        return AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("System analyst generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/low-level-design",
    response_model=AgentResponse,
)
def generate_low_level_design(
    request: LLDRequest,
    db: Session = Depends(get_db),
):
    """
    Run low-level design pipeline and save final report.
    """
    try:
        logger.info("Received LLD request: %s", request.user_input)

        ctx = AgentContext(state={"user_goal": request.user_input})

        ctx.state["requirement_doc"] = request.requirement_doc
        ctx.state["architecture_doc"] = request.architecture_doc

        result = run_lld_pipeline(
            request.user_input,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            context=ctx,
        )
        final_report = str(result.get("final_report", "")).strip()

        doc = save_lld_document(
            db=db,
            agent_type="low_level_design",
            user_input=request.user_input,
            output=final_report,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=str(ctx.session.session_id),
        )

        return AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("LLD generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/supervisor",
    response_model=AgentResponse,
)
def generate_supervisor(
    request: SupervisorRequest,
    db: Session = Depends(get_db),
):
    """
    Run the supervisor orchestrator and save combined output.
    """
    try:
        logger.info("Received supervisor request: %s", request.user_input)

        if supervisor_agent is None:
            raise RuntimeError("Supervisor agent not initialized")

        ctx = AgentContext(state={
            "user_goal": request.user_input,
        })

        response = supervisor_agent.run(task=request.user_input, context=ctx)
        raw_output = response.output if hasattr(response, "output") else str(response)

        if not _is_complete_combined_output(str(raw_output or "")):
            ensure_timeout = int(
                os.getenv("SUPERVISOR_ENSURE_TIMEOUT_SECONDS", "600")
            )

            completed_ensure, _ = _run_with_timeout(
                _ensure_agent_outputs,
                ensure_timeout,
                user_goal=request.user_input,
                context=ctx,
            )

            if not completed_ensure:
                logger.warning(
                    "_ensure_agent_outputs timed out after %ss — some sections may be missing",
                    ensure_timeout,
                )
        _populate_lld_fields_from_output(ctx)
        output = _canonicalize_combined_output(
            str(raw_output or "").strip(),
            user_goal=request.user_input,
            context=ctx,
        ).strip()

        if not output:
            raise RuntimeError("Supervisor completed without producing output")

        doc = save_lld_document(
            db=db,
            agent_type="supervisor",
            user_input=request.user_input,
            output=str(output).strip(),
            requirement_doc="",
            architecture_doc="",
            session_id=str(ctx.session.session_id),
        )

        return AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("Supervisor generation failed")
        raise HTTPException(status_code=500, detail=str(e))




@app.get(
    "/documents",
    response_model=List[AgentResponse]
)
def get_all_documents(
    db: Session = Depends(get_db)
):
    """Retrieve all documents across all agent types."""
    docs = get_all_lld_documents(db=db)
    arch_docs = get_all_system_architecture_documents(db=db)
    backend_docs = get_all_lld_backend_documents(db=db)
    
    result = []
    
    # Add LLD documents
    for doc in docs:
        result.append(AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        ))
    
    # Add architecture documents
    for doc in arch_docs:
        result.append(AgentResponse(
            id=doc.id,
            agent_type="system_architecture",
            user_input=doc.analyst_document,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        ))
    
    # Add backend LLD documents
    for doc in backend_docs:
        result.append(AgentResponse(
            id=doc.id,
            agent_type="backend_lld",
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        ))
    
    return result


@app.get(
    "/documents/agent/{agent_type}",
    response_model=List[AgentResponse]
)
def get_documents_by_agent(
    agent_type: str,
    db: Session = Depends(get_db)
):
    """Retrieve all documents of a specific agent type."""
    docs = []

    if agent_type == "backend_lld":
        docs = get_all_lld_backend_documents(db=db)
        return [
            AgentResponse(
                id=doc.id,
                agent_type="backend_lld",
                user_input=doc.user_input,
                output=doc.output,
                session_id=doc.session_id or "",
                created_at=str(doc.created_at),
            )
            for doc in docs
        ]
    elif agent_type == "system_architecture":
        docs = get_all_system_architecture_documents(db=db)
        return [
            AgentResponse(
                id=doc.id,
                agent_type="system_architecture",
                user_input=doc.analyst_document,
                output=doc.output,
                session_id=doc.session_id or "",
                created_at=str(doc.created_at),
            )
            for doc in docs
        ]
    else:
        docs = get_all_lld_documents(
            db=db,
            agent_type=agent_type
        )

    return [
        AgentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )
        for doc in docs
    ]


@app.get(
    "/documents/agent/{agent_type}/id/{doc_id}",
    response_model=AgentResponse
)
def get_document_by_agent_and_id(
    agent_type: str,
    doc_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve a specific document by agent type and document ID."""
    # Query by agent_type and ID from the default LLD table
    if agent_type in ["frontend_lld", "generic_lld", "system_analyst", "low_level_design", "supervisor"]:
        doc = get_lld_document(db=db, doc_id=doc_id)
        if doc and doc.agent_type == agent_type:
            return AgentResponse(
                id=doc.id,
                agent_type=doc.agent_type,
                user_input=doc.user_input,
                output=doc.output,
                session_id=doc.session_id or "",
                created_at=str(doc.created_at),
            )
    elif agent_type == "system_architecture":
        doc = get_system_architecture_document(db=db, doc_id=doc_id)
        if doc:
            return AgentResponse(
                id=doc.id,
                agent_type="system_architecture",
                user_input=doc.analyst_document,
                output=doc.output,
                session_id=doc.session_id or "",
                created_at=str(doc.created_at),
            )
    elif agent_type == "backend_lld":
        doc = get_lld_backend_document(db=db, doc_id=doc_id)
        if doc:
            return AgentResponse(
                id=doc.id,
                agent_type="backend_lld",
                user_input=doc.user_input,
                output=doc.output,
                session_id=doc.session_id or "",
                created_at=str(doc.created_at),
            )

    raise HTTPException(
        status_code=404,
        detail=f"Document {doc_id} not found for agent type {agent_type}"
    )


@app.get(
    "/documents/{doc_id}",
    response_model=AgentResponse
)
def get_document_by_id(
    doc_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve a document by ID across all agent types."""
    # Check architecture documents
    doc = get_system_architecture_document(db=db, doc_id=doc_id)

    if doc:
        return AgentResponse(
            id=doc.id,
            agent_type="system_architecture",
            user_input=doc.analyst_document,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    # Check backend LLD documents
    doc = get_lld_backend_document(db=db, doc_id=doc_id)

    if doc:
        return AgentResponse(
            id=doc.id,
            agent_type="backend_lld",
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    # Check default documents
    doc = get_lld_document(db=db, doc_id=doc_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )

    return AgentResponse(
        id=doc.id,
        agent_type=doc.agent_type,
        user_input=doc.user_input,
        output=doc.output,
        session_id=doc.session_id or "",
        created_at=str(doc.created_at),
    )