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

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

# ── Add folders to Python path ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR / "frontend-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "generic-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "database"))
sys.path.insert(0, str(BASE_DIR))

# ── Agent imports ─────────────────────────────────────────────────────────────
from frontend_graph import build_agent as build_frontend_agent
from frontend_graph import create_context as create_frontend_context
from frontend_graph import run_agent as run_frontend_agent

from generic_graph import build_agent as build_generic_agent
from generic_graph import create_context as create_generic_context
from generic_graph import run_agent as run_generic_agent

# ── Database imports ──────────────────────────────────────────────────────────
from db import (
    init_db,
    get_db,
    save_lld_document,
    get_lld_document,
    get_all_lld_documents,
)

# ── Observability imports ─────────────────────────────────────────────────────
from observability.observability import get_logger, init_observability, new_request_id
import mlflow

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
)
logger = get_logger(__name__)

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dev Architect API",
    description="Generates and stores LLD documents using AI agents",
    version="1.0.0",
)

# ── Global agents ─────────────────────────────────────────────────────────────
frontend_agent = None
generic_agent  = None


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    global frontend_agent, generic_agent

    logger.info("Initialising observability ...")
    init_observability()

    logger.info("Initialising database ...")
    init_db()

    logger.info("Building agents ...")
    frontend_agent = build_frontend_agent()
    generic_agent  = build_generic_agent()

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
    return {"status": "ok", "message": "Dev Architect API is running"}


@app.post("/generate/frontend-lld", response_model=LLDDocumentResponse)
def generate_frontend_lld(
    request: LLDRequest,
    db: Session = Depends(get_db),
):
    """Generate Frontend LLD and save to database."""
    request_id = new_request_id()
    logger.info("Received frontend LLD request. request_id=%s", request_id)

    try:
        ctx = create_frontend_context(
            user_id="api-user",
            session_metadata={
                "source":     "fastapi",
                "endpoint":   "/generate/frontend-lld",
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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/generic-lld", response_model=LLDDocumentResponse)
def generate_generic_lld(
    request: LLDRequest,
    db: Session = Depends(get_db),
):
    """Generate Generic LLD and save to database."""
    request_id = new_request_id()
    logger.info("Received generic LLD request. request_id=%s", request_id)

    try:
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents", response_model=List[LLDDocumentResponse])
def list_documents(
    agent_type: str = None,
    db: Session = Depends(get_db),
):
    """Get all saved documents. Optional filter by agent_type."""
    docs = get_all_lld_documents(db=db, agent_type=agent_type)
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


@app.get("/documents/{doc_id}", response_model=LLDDocumentResponse)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
):
    """Get single document by ID."""
    doc = get_lld_document(db=db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return LLDDocumentResponse(
        id=doc.id,
        agent_type=doc.agent_type,
        user_input=doc.user_input,
        output=doc.output,
        session_id=doc.session_id or "",
        created_at=str(doc.created_at),
    )