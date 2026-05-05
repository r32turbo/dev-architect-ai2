"""
main.py – FastAPI entry point.

Entry points:
  POST /generate/frontend-lld  → generates and saves Frontend LLD to DB
  POST /generate/generic-lld   → generates and saves Generic LLD to DB
  GET  /documents              → retrieve all saved documents
  GET  /documents/{id}         → retrieve a specific document by ID

Run:
    uvicorn main:app --reload
"""

import logging
import sys
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

# ── Add folders to Python path ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR / "frontend-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "generic-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "database"))
sys.path.insert(0, str(BASE_DIR / "supervisor-agent"))
sys.path.insert(0, str(BASE_DIR / "system-analyst-agent"))
sys.path.insert(0, str(BASE_DIR / "low-level-design-agent"))

# Frontend Agent
from frontend_graph import build_agent as build_frontend_agent
from frontend_graph import create_context as create_frontend_context

# Generic Agent
from generic_graph import build_agent as build_generic_agent
from generic_graph import create_context as create_generic_context

# Database
from db import (
    init_db,
    get_db,
    save_lld_document,
    get_lld_document,
    get_all_lld_documents,
)

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


class LLDDocumentResponse(BaseModel):
    id: int
    agent_type: str
    user_input: str
    output: str
    session_id: str
    created_at: str

    class Config:
        from_attributes = True


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
            },
        )

        response = frontend_agent.run(
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

        return LLDDocumentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("Frontend LLD generation failed")
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
    try:
        logger.info(
            "Received generic LLD request: %s",
            request.user_input
        )

        ctx = create_generic_context(
            user_id="api-user",
            session_metadata={
                "source": "fastapi",
                "endpoint": "/generate/generic-lld",
            },
        )

        response = generic_agent.run(
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

        return LLDDocumentResponse(
            id=doc.id,
            agent_type=doc.agent_type,
            user_input=doc.user_input,
            output=doc.output,
            session_id=doc.session_id or "",
            created_at=str(doc.created_at),
        )

    except Exception as e:
        logger.exception("Generic LLD generation failed")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


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
    request: LLDRequest,
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
            "requirement_doc": request.requirement_doc,
            "architecture_doc": request.architecture_doc,
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
        logger.exception("Supervisor generation failed")
        raise HTTPException(status_code=500, detail=str(e))


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