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

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

# ── Add folders to Python path ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR / "system_architect_agent"))
sys.path.insert(0, str(BASE_DIR / "frontend-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "generic-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "lld_backend_agent"))
sys.path.insert(0, str(BASE_DIR / "database"))

# System Architecture Agent
# ✅ FIX: import run_system_architect directly — same pattern as backend
from system_architect_agent import run_system_architect

# Frontend Agent
from frontend_graph import build_agent as build_frontend_agent
from frontend_graph import create_context as create_frontend_context

# Generic Agent
from generic_graph import build_agent as build_generic_agent
from generic_graph import create_context as create_generic_context

# Backend LLD Agent
from lld_backend_agent.lldback import run_backend_lld

# Database
from db import (
    init_db,
    get_db,
    save_lld_document,
    get_lld_document,
    get_all_lld_documents,
)

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

# Global agents
frontend_agent = None
generic_agent = None
# ✅ No global backend_agent or architecture_agent
# Both use their own run_* functions that build internally per call


# ── Startup Event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    global frontend_agent, generic_agent

    logger.info("Initializing database...")
    init_db()

    logger.info("Building agents...")
    frontend_agent = build_frontend_agent()
    generic_agent = build_generic_agent()
    # ✅ No backend_agent or architecture_agent at startup
    # They build internally per request via run_* functions

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
    try:
        logger.info("Received frontend LLD request: %s", request.user_input)

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
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/generic-lld",
    response_model=LLDDocumentResponse
)
def generate_generic_lld(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    try:
        logger.info("Received generic LLD request: %s", request.user_input)

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
        raise HTTPException(status_code=500, detail=str(e))


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

        doc = save_lld_document(
            db=db,
            agent_type="backend_lld",
            user_input=request.user_input,
            output=output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=session_id,
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
        logger.exception("Backend LLD generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate/architecture",
    response_model=LLDDocumentResponse
)
def generate_architecture(
    request: LLDRequest,
    db: Session = Depends(get_db)
):
    try:
        logger.info("Received architecture request: %s", request.user_input)

        # ✅ FIX: Call run_system_architect directly with input_document
        # Combine user_input + requirement_doc if provided
        input_document = request.user_input
        if request.requirement_doc.strip():
            input_document = f"{request.user_input}\n\n{request.requirement_doc}"

        output = run_system_architect(input_document=input_document)

        session_id = str(uuid.uuid4())

        doc = save_lld_document(
            db=db,
            agent_type="system_architecture",
            user_input=request.user_input,
            output=output,
            requirement_doc=request.requirement_doc,
            architecture_doc=request.architecture_doc,
            session_id=session_id,
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
        logger.exception("System Architecture generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/documents",
    response_model=List[LLDDocumentResponse]
)
def list_documents(
    agent_type: str = None,
    db: Session = Depends(get_db)
):
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


@app.get(
    "/documents/{doc_id}",
    response_model=LLDDocumentResponse
)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db)
):
    doc = get_lld_document(db=db, doc_id=doc_id)

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