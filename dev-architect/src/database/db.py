"""
db.py
Database connection, session factory, and helper functions.
Uses SQLite via SQLAlchemy.
"""
import logging
from pathlib import Path
from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models import Base, LLDDocument

logger = logging.getLogger(__name__)

# ── Database file location ────────────────────────────────────────────────────
# Stored in src/dev_architect.db (one level up from this file)
DB_PATH = Path(__file__).resolve().parent.parent / "dev_architect.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ── Engine and session factory ────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialised at: %s", DB_PATH)


def get_db() -> Session:
    """Yield a database session. Used as a FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def save_lld_document(
    db: Session,
    agent_type: str,
    user_input: str,
    output: str,
    requirement_doc: str = "",
    architecture_doc: str = "",
    session_id: str = "",
) -> LLDDocument:
    """
    Save a generated LLD document to the database.

    Parameters
    ----------
    db             : SQLAlchemy session
    agent_type     : 'frontend_lld' or 'generic_lld'
    user_input     : original user request
    output         : generated LLD markdown content
    requirement_doc: requirements document input
    architecture_doc: architecture document input
    session_id     : AgentContext session ID

    Returns
    -------
    LLDDocument : the saved record
    """
    doc = LLDDocument(
        agent_type=agent_type,
        user_input=user_input,
        requirement_doc=requirement_doc,
        architecture_doc=architecture_doc,
        output=output,
        session_id=session_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(
        "Saved %s document to database. ID=%d session_id=%s",
        agent_type, doc.id, session_id,
    )
    return doc


def get_lld_document(db: Session, doc_id: int) -> Optional[LLDDocument]:
    """Retrieve a single LLD document by ID."""
    return db.query(LLDDocument).filter(LLDDocument.id == doc_id).first()


def get_all_lld_documents(db: Session, agent_type: str = None) -> List[LLDDocument]:
    """
    Retrieve all LLD documents, optionally filtered by agent type.

    Parameters
    ----------
    agent_type : if provided, filter by 'frontend_lld' or 'generic_lld'
    """
    query = db.query(LLDDocument)
    if agent_type:
        query = query.filter(LLDDocument.agent_type == agent_type)
    return query.order_by(LLDDocument.created_at.desc()).all()