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
sys.path.insert(0, str(BASE_DIR / "system-analyst-agent"))
sys.path.insert(0, str(BASE_DIR / "low-level-design-agent"))
sys.path.insert(0, str(BASE_DIR))

# System Architecture Agent
# ✅ FIX: import run_system_architect directly — same pattern as backend
from system_architect_agent import run_system_architect, create_context as create_architecture_context

# Frontend Agent
from frontend_graph import build_agent as build_frontend_agent
from frontend_graph import create_context as create_frontend_context
from frontend_graph import run_agent as run_frontend_agent

# Generic Agent
from generic_graph import build_agent as build_generic_agent
from generic_graph import create_context as create_generic_context
from generic_graph import run_agent as run_generic_agent

# Backend LLD Agent
from lld_backend_agent.lldback import run_backend_lld

# Database Imports
from db import (
    init_db,
    get_db,
    save_lld_document,
    get_lld_document,
    get_all_lld_documents,
    save_system_architecture_document,
    get_system_architecture_document,
    get_all_system_architecture_documents,
    save_lld_backend_document,
    get_lld_backend_document,
    get_all_lld_backend_documents,
    get_latest_system_architecture_document,
    save_requirement_document,
    get_requirement_document,
    get_all_requirement_documents,
)
# ── Observability imports ─────────────────────────────────────────────────────
from observability.observability import get_logger, init_observability, new_request_id
import mlflow


# Supervisor, System Analyst, Low-level Design agents
from sup import (
    build_supervisor_agent,
    _canonicalize_combined_output,
    _ensure_agent_outputs,
    _populate_lld_fields_from_output,
)
from analyst_agent import build_agent as build_system_analyst_agent, run_system_analysis
from lld_createagent import run_pipeline as run_lld_pipeline
from reusableagents.context import AgentContext

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


    logger.info("Initialising observability ...")
    init_observability()

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


class SupervisorRequest(BaseModel):
    user_input: str


class LLDDocumentResponse(BaseModel):
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
    response_model=LLDDocumentResponse
)
def generate_frontend_lld(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Frontend LLD and save to database.
    """
    request_id = new_request_id()
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

        with mlflow.start_run(run_name="frontend_lld"):
            mlflow.set_tag("agent_type",  "frontend_lld")
            mlflow.set_tag("request_id",  request_id)
            mlflow.set_tag("user_input",  request.user_input[:200])

            response = run_frontend_agent(
                agent=frontend_agent,
                context=ctx,
                user_input=request.user_input,
                requirement_doc=request.requirement_doc,
                architecture_doc=request.architecture_doc,
            )

            mlflow.log_metric("validation_score",    response.validation_score or 0)
            mlflow.log_metric("was_refined",         int(response.was_refined))
            mlflow.log_metric("refinement_attempts", response.refinement_attempts)
            mlflow.log_metric("output_length",       len(response.output))

        doc = save_lld_document(
            db=db,
            agent_type="frontend_lld",
            user_input=request.user_input,
            output=response.output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=str(ctx.session.session_id),
        )

        return LLDDocumentResponse(
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
    response_model=LLDDocumentResponse
)
def generate_generic_lld(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Generic LLD and save to database.
    """
    request_id = new_request_id()
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

        with mlflow.start_run(run_name="generic_lld"):
            mlflow.set_tag("agent_type",  "generic_lld")
            mlflow.set_tag("request_id",  request_id)
            mlflow.set_tag("user_input",  request.user_input[:200])

            response = run_generic_agent(
                agent=generic_agent,
                context=ctx,
                user_input=request.user_input,
                requirement_doc=request.requirement_doc,
                architecture_doc=request.architecture_doc,
            )

            mlflow.log_metric("validation_score",    response.validation_score or 0)
            mlflow.log_metric("was_refined",         int(response.was_refined))
            mlflow.log_metric("refinement_attempts", response.refinement_attempts)
            mlflow.log_metric("output_length",       len(response.output))

        doc = save_lld_document(
            db=db,
            agent_type="generic_lld",
            user_input=request.user_input,
            output=response.output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=str(ctx.session.session_id),
        )

        return LLDDocumentResponse(
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
    response_model=LLDDocumentResponse
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

        return LLDDocumentResponse(
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
    response_model=ArchitectureResponse
)
def generate_architecture(
    request: ArchitectureRequest,
    db: Session = Depends(get_db)
):
    try:
        logger.info("Received architecture request: %s", request.user_input)

<<<<<<< HEAD
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

        return LLDDocumentResponse(
            id=doc.id,
            agent_type="system_architecture",
            user_input=request.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
=======
        # ✅ FIX: Call run_system_architect directly with input_document
        # Retrieve the input from the request to start the agent
        user_input = request.user_input
        requirement_doc = request.requirement_doc.strip()
        requirement_doc_id = request.requirement_doc_id.strip()

        # Retrieve the document from the database if requirement_doc is empty and  requirement_doc_id is not empty
        if not requirement_doc and requirement_doc_id:
            from db import get_requirement_document
            req_doc = get_requirement_document(db=db, doc_id=int(requirement_doc_id))
            if req_doc:
                requirement_doc = req_doc.content
                logger.info("Fetched requirement document from DB for architecture generation: %s", requirement_doc_id)
            else:
                logger.warning("No requirement document found in DB for ID: %s", requirement_doc_id)
    
        # create the context for the system architect agent
        context = AgentContext()
        context.state["user_input"] = user_input
        context.state["requirement_doc"] = requirement_doc

        session_id = ""
        # Check seesion_id in the context state else create a new one
        if context.session and context.session.session_id:
            session_id = context.session.session_id
        else :
            context.session.session_id = str(uuid.uuid4())
            session_id = context.session.session_id

        # call the system architect agent to generate the architecture document with the context
        doc = run_system_architect(context)
        
        return ArchitectureResponse(
            id=doc.id,
            agent_type="system_architecture",
            user_input=user_input,
            output=doc.architecture_document,
            session_id=session_id,
>>>>>>> 1a959f420456e51010b04b7ddcbcb43d3b28eb36
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("System Architecture generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/system-analyst",
    response_model=LLDDocumentResponse,
)
def generate_system_analyst(
    request: LLDRequest,
    db: Session = Depends(get_db),
):
    """
    Run system analyst agent and save result.
    """
    try:
        logger.info("Received system analyst request: %s", request.user_input)

        ctx = AgentContext(state={
            "user_goal": request.user_input,
            "requirement_doc": request.requirement_doc,
            "architecture_doc": request.architecture_doc,
        })

        output = run_system_analysis(user_goal=request.user_input, context=ctx)

        doc = save_lld_document(
            db=db,
            agent_type="system_analyst",
            user_input=request.user_input,
            output=output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=str(ctx.session.session_id),
        )

        return LLDDocumentResponse(
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
    response_model=LLDDocumentResponse,
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

        return LLDDocumentResponse(
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
    response_model=LLDDocumentResponse,
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
        _ensure_agent_outputs(request.user_input, ctx)
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

        return LLDDocumentResponse(
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
    "/requirements",
    response_model=List[LLDDocumentResponse],
)
def list_requirements(db: Session = Depends(get_db)):
    docs = get_all_requirement_documents(db=db)
    return [
        LLDDocumentResponse(
            id=doc.id,
            agent_type="system_analyst",
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )
        for doc in docs
    ]


@app.get(
    "/requirements/{doc_id}",
    response_model=LLDDocumentResponse,
)
def get_requirement(doc_id: int, db: Session = Depends(get_db)):
    doc = get_requirement_document(db=db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Requirement document {doc_id} not found")
    return LLDDocumentResponse(
        id=doc.id,
        agent_type="system_analyst",
        user_input=doc.user_input,
        output=doc.output,
        session_id=doc.session_id or "",
        created_at=str(doc.created_at),
    )


@app.get(
    "/architectures",
    response_model=List[LLDDocumentResponse],
)
def list_architectures(db: Session = Depends(get_db)):
    docs = get_all_system_architecture_documents(db=db)
    return [
        LLDDocumentResponse(
            id=doc.id,
            agent_type="system_architecture",
            user_input=doc.analyst_document,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )
        for doc in docs
    ]


@app.get(
    "/architectures/{doc_id}",
    response_model=LLDDocumentResponse,
)
def get_architecture(doc_id: int, db: Session = Depends(get_db)):
    doc = get_system_architecture_document(db=db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Architecture document {doc_id} not found")
    return LLDDocumentResponse(
        id=doc.id,
        agent_type="system_architecture",
        user_input=doc.analyst_document,
        output=doc.output,
        session_id=doc.session_id or "",
        created_at=str(doc.created_at),
    )


@app.get(
    "/backend-lld-documents",
    response_model=List[LLDDocumentResponse],
)
def list_backend_lld_documents(db: Session = Depends(get_db)):
    docs = get_all_lld_backend_documents(db=db)
    return [
        LLDDocumentResponse(
            id=doc.id,
            agent_type="backend_lld",
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )
        for doc in docs
    ]


@app.get(
    "/backend-lld-documents/{doc_id}",
    response_model=LLDDocumentResponse,
)
def get_backend_lld_document(doc_id: int, db: Session = Depends(get_db)):
    doc = get_lld_backend_document(db=db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Backend LLD document {doc_id} not found")
    return LLDDocumentResponse(
        id=doc.id,
        agent_type="backend_lld",
        user_input=doc.user_input,
        output=doc.output,
        session_id=doc.session_id or "",
        created_at=str(doc.created_at),
    )


@app.get(
    "/documents",
    response_model=List[LLDDocumentResponse]
)
def list_documents(
    agent_type: str = None,
    db: Session = Depends(get_db)
):
    """
    Get all saved documents.
    Optional filter by agent_type.
    """
    docs = get_all_lld_documents(
        db=db,
        agent_type=agent_type
    )

    return [
        LLDDocumentResponse(
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
    "/documents/{doc_id}",
    response_model=LLDDocumentResponse
)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db)
):
    """
    Get single document by ID.
    """
    doc = get_lld_document(
        db=db,
        doc_id=doc_id
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )

    return LLDDocumentResponse(
        id=doc.id,
        agent_type=doc.agent_type,
        user_input=doc.user_input,
        output=doc.output,
        session_id=doc.session_id or "",
        created_at=str(doc.created_at),
    )