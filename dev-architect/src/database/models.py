"""
models.py
SQLAlchemy table definitions for the Dev Architect system.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SystemArchitectureDocument(Base):
    """
    Stores the output of the System Architect Agent run.

    Columns:
      id                : auto-increment primary key
      analyst_document  : the input analyst document
      output            : the generated architecture document (full markdown)
      session_id        : the AgentContext session ID
      created_at        : timestamp of when the document was created
    """
    __tablename__ = "system_architecture_documents"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    analyst_document  = Column(Text, nullable=False)
    output            = Column(Text, nullable=False)
    session_id        = Column(String(100), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SystemArchitectureDocument id={self.id} "
            f"created_at={self.created_at}>"
        )


class LLDBackendDocument(Base):
    """
    Stores the output of the LLD Backend Agent run.

    Columns:
      id                   : auto-increment primary key
      user_input           : the original user request
      requirement_doc      : the requirements document passed as input
      architecture_doc_id  : foreign key reference to SystemArchitectureDocument
      output               : the generated backend LLD document (full markdown)
      session_id           : the AgentContext session ID
      created_at           : timestamp of when the document was created
    """
    __tablename__ = "lld_backend_documents"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    user_input           = Column(Text, nullable=False)
    requirement_doc      = Column(Text, nullable=True)
    architecture_doc_id  = Column(Integer, ForeignKey("system_architecture_documents.id"), nullable=True)
    output               = Column(Text, nullable=False)
    session_id           = Column(String(100), nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<LLDBackendDocument id={self.id} "
            f"created_at={self.created_at}>"
        )


class LLDDocument(Base):
    """
    Stores the output of each LLD agent run (Frontend/Generic).

    Columns:
      id           : auto-increment primary key
      agent_type   : which agent generated this (e.g. 'frontend_lld', 'generic_lld')
      user_input   : the original user request
      requirement_doc  : the requirements document passed as input
      architecture_doc : the architecture document passed as input
      output       : the generated LLD document (full markdown)
      session_id   : the AgentContext session ID
      created_at   : timestamp of when the document was created
    """
    __tablename__ = "lld_documents"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    agent_type       = Column(String(50), nullable=False)
    user_input       = Column(Text, nullable=False)
    requirement_doc  = Column(Text, nullable=True)
    architecture_doc = Column(Text, nullable=True)
    output           = Column(Text, nullable=False)
    session_id       = Column(String(100), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<LLDDocument id={self.id} agent_type={self.agent_type!r} "
            f"created_at={self.created_at}>"
        )