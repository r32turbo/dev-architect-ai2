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

<<<<<<< HEAD
try:
    from .models import Base, LLDDocument, SystemArchitectureDocument, LLDBackendDocument, SystemRequirementDocument
except ImportError:
    from models import Base, LLDDocument, SystemArchitectureDocument, LLDBackendDocument, SystemRequirementDocument
=======
from models import Base, LLDDocument, SystemArchitectureDocument, LLDBackendDocument, SystemRequirementDocument
>>>>>>> 1a959f420456e51010b04b7ddcbcb43d3b28eb36

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

def get_requirment_document(db: Session, doc_id: int) -> Optional[SystemRequirementDocument]:
    """Retrieve a single System Requirement document by ID."""
    return db.query(SystemRequirementDocument).filter(SystemRequirementDocument.id == doc_id).first()

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


# ── SYSTEM ARCHITECT AGENT CRUD HELPERS ───────────────────────────────────────

def save_system_architecture_document(
    db: Session,
    architecture_document: str,
    session_id: str = "",
) -> SystemArchitectureDocument:
    """
    Save a generated System Architecture document to the database.

    Parameters
    ----------
    db                 : SQLAlchemy session
    architecture_document : the architecture document (output)
    session_id         : AgentContext session ID

    Returns
    -------
    SystemArchitectureDocument : the saved record
    """
    doc = SystemArchitectureDocument(
        architecture_document=architecture_document,
        session_id=session_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(
        "Saved SystemArchitectureDocument to database. ID=%d session_id=%s",
        doc.id, session_id,
    )
    return doc


def get_system_architecture_document(db: Session, doc_id: int) -> Optional[SystemArchitectureDocument]:
    """Retrieve a single System Architecture document by ID."""
    return db.query(SystemArchitectureDocument).filter(SystemArchitectureDocument.id == doc_id).first()


# ── LLD BACKEND AGENT CRUD HELPERS ─────────────────────────────────────────────

def save_lld_backend_document(
    db: Session,
    user_input: str,
    output: str,
    requirement_doc: str = "",
    architecture_doc_id: int = None,
    session_id: str = "",
) -> LLDBackendDocument:
    """
    Save a generated Backend LLD document to the database.

    Parameters
    ----------
    db                 : SQLAlchemy session
    user_input         : original user request
    output             : generated backend LLD markdown content
    requirement_doc    : requirements document input
    architecture_doc_id: foreign key reference to SystemArchitectureDocument
    session_id         : AgentContext session ID

    Returns
    -------
    LLDBackendDocument : the saved record
    """
    doc = LLDBackendDocument(
        user_input=user_input,
        requirement_doc=requirement_doc,
        architecture_doc_id=architecture_doc_id,
        output=output,
        session_id=session_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(
        "Saved LLDBackendDocument to database. ID=%d session_id=%s",
        doc.id, session_id,
    )
    return doc


def get_lld_backend_document(db: Session, doc_id: int) -> Optional[LLDBackendDocument]:
    """Retrieve a single Backend LLD document by ID."""
    return db.query(LLDBackendDocument).filter(LLDBackendDocument.id == doc_id).first()


def get_all_lld_backend_documents(db: Session) -> List[LLDBackendDocument]:
    """Retrieve all Backend LLD documents."""
    return db.query(LLDBackendDocument).order_by(LLDBackendDocument.created_at.desc()).all()


def get_lld_backend_documents_by_architecture(db: Session, architecture_doc_id: int) -> List[LLDBackendDocument]:
    """Retrieve all Backend LLD documents linked to a specific System Architecture document."""
    return db.query(LLDBackendDocument).filter(
        LLDBackendDocument.architecture_doc_id == architecture_doc_id
    ).order_by(LLDBackendDocument.created_at.desc()).all()


def get_latest_lld_backend_document(db: Session) -> Optional[LLDBackendDocument]:
    """Retrieve the most recent Backend LLD document."""
    return db.query(LLDBackendDocument).order_by(LLDBackendDocument.created_at.desc()).first()


# ── SYSTEM REQUIREMENT DOCUMENT CRUD HELPERS ─────────────────────────────────

def save_requirement_document(
    db: Session,
    user_input: str,
    output: str,
    session_id: str = "",
) -> SystemRequirementDocument:
    """
    Save a generated System Requirement document to the database.

    Parameters
    ----------
    db             : SQLAlchemy session
    user_input     : original user request
    output         : generated requirement markdown content
    session_id     : AgentContext session ID

    Returns
    -------
    SystemRequirementDocument : the saved record
    """
    doc = SystemRequirementDocument(
        user_input=user_input,
        output=output,
        session_id=session_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(
        "Saved SystemRequirementDocument to database. ID=%d session_id=%s",
        doc.id, session_id,
    )
    return doc


def get_requirement_document(db: Session, doc_id: int) -> Optional[SystemRequirementDocument]:
    """Retrieve a single Requirement document by ID."""
    return db.query(SystemRequirementDocument).filter(SystemRequirementDocument.id == doc_id).first()


def get_all_requirement_documents(db: Session) -> List[SystemRequirementDocument]:
    """Retrieve all Requirement documents."""
    return db.query(SystemRequirementDocument).order_by(SystemRequirementDocument.created_at.desc()).all()


def get_latest_requirement_document(db: Session) -> Optional[SystemRequirementDocument]:
    """Retrieve the most recent Requirement document."""
    return db.query(SystemRequirementDocument).order_by(SystemRequirementDocument.created_at.desc()).first()