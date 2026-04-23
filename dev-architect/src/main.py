"""
main.py – FastAPI entry point.

Entry points:
  POST /generate/frontend-lld  → Frontend LLD Agent
  POST /generate/generic-lld   → Generic LLD Agent

Run:
    uvicorn main:app --reload
"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ── Add src/ to path so agents can be found ───────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent

# Add specific folders to Python path
sys.path.insert(0, str(BASE_DIR / "frontend-lld-agent"))
sys.path.insert(0, str(BASE_DIR / "generic-lld-agent"))

from frontend_graph import build_agent as build_frontend_agent
from frontend_graph import create_context as create_frontend_context

from generic_graph import build_agent as build_generic_agent
from generic_graph import create_context as create_generic_context

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dev Architect API",
    description="Generates LLD documents from a user prompt.",
    version="1.0.0",
)

# ── Build agents once at startup ──────────────────────────────────────────────
logger.info("Building agents ...")
frontend_agent = build_frontend_agent()
generic_agent  = build_generic_agent()
logger.info("All agents ready.")


# ── Request / Response schemas ────────────────────────────────────────────────

class LLDRequest(BaseModel):
    user_input: str
    requirement_doc: str = ""
    architecture_doc: str = ""


class FrontendLLDResponse(BaseModel):
    frontend_lld: str
    session_id: str
    history_count: int


class GenericLLDResponse(BaseModel):
    generic_lld: str
    session_id: str
    history_count: int


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Dev Architect API is running."}


@app.post("/generate/frontend-lld", response_model=FrontendLLDResponse)
def generate_frontend_lld(request: LLDRequest):
    """Generate a Frontend LLD document from user prompt and optional docs."""
    logger.info("Received /generate/frontend-lld: %s", request.user_input)
    try:
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
        logger.info(
            "Frontend LLD generated. Score: %.2f | History: %d entries",
            response.validation_score or 0,
            len(ctx.history),
        )
        return FrontendLLDResponse(
            frontend_lld=response.output,
            session_id=ctx.session.session_id,
            history_count=len(ctx.history),
        )
    except Exception as e:
        logger.error("Error generating Frontend LLD: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/generic-lld", response_model=GenericLLDResponse)
def generate_generic_lld(request: LLDRequest):
    """Generate a Generic LLD document from user prompt and optional docs."""
    logger.info("Received /generate/generic-lld: %s", request.user_input)
    try:
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
        logger.info(
            "Generic LLD generated. Score: %.2f | History: %d entries",
            response.validation_score or 0,
            len(ctx.history),
        )
        return GenericLLDResponse(
            generic_lld=response.output,
            session_id=ctx.session.session_id,
            history_count=len(ctx.history),
        )
    except Exception as e:
        logger.error("Error generating Generic LLD: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))