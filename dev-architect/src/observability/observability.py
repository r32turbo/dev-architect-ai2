"""
observability.py

Sets up:
1. Logging      - JSON structured logs to file + console
2. Tracing      - MLflow tracing (using mlflow.trace directly)
3. MLflow runs  - Stores runs and traces in MLflow UI
"""

import os
import uuid
import json
import logging
import logging.handlers
import warnings
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps

# ── Suppress noisy warnings ───────────────────────────────────────────────────
warnings.filterwarnings("ignore")

# ── MLflow is optional for local development ────────────────────────────────
try:
    import mlflow  # type: ignore
    _MLFLOW_AVAILABLE = True
except ImportError:
    mlflow = None  # type: ignore
    _MLFLOW_AVAILABLE = False

if _MLFLOW_AVAILABLE:
    logging.getLogger("mlflow").setLevel(logging.ERROR)

# ── Config ────────────────────────────────────────────────────────────────────
MLFLOW_URI      = os.getenv("MLFLOW_TRACKING_URI",    "http://localhost:5000")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "dev_architect_agent")
SERVICE_NAME    = os.getenv("OTEL_SERVICE_NAME",       "dev-architect-agent")
MLFLOW_ENABLED  = os.getenv("MLFLOW_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

_GCP_PROJECT  = os.getenv("GOOGLE_CLOUD_PROJECT",  "eds-alchemy")
_GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# ── Logs folder ───────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# ── Context variable — stores request_id per request ─────────────────────────
_request_id_var: ContextVar[str] = ContextVar("request_id", default="—")


# ── Logging ───────────────────────────────────────────────────────────────────

class _ContextFilter(logging.Filter):
    """Injects request_id into every log record."""

    def filter(self, record):
        record.request_id = _request_id_var.get("—")
        return True


class _JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines."""

    def format(self, record):
        return json.dumps({
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "level":      record.levelname,
            "logger":     record.name,
            "request_id": getattr(record, "request_id", "—"),
            "message":    record.getMessage(),
        })


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger with:
    - File handler  → DEBUG level  → logs/platform.jsonl (JSON format)
    - Console handler → WARNING level
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    ctx_filter = _ContextFilter()

    # File handler
    fh = logging.handlers.RotatingFileHandler(
        "logs/platform.jsonl",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    fh.setFormatter(_JSONFormatter())
    fh.addFilter(ctx_filter)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.addFilter(ctx_filter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ── Request ID ────────────────────────────────────────────────────────────────

def new_request_id() -> str:
    """Generate a unique ID for each incoming request."""
    rid = str(uuid.uuid4())
    _request_id_var.set(rid)
    return rid


# ── Observability setup ───────────────────────────────────────────────────────

def init_observability() -> None:
    """
    Initialise MLflow tracking and auto-logging.
    Call once at application startup.
    """
    if not _MLFLOW_AVAILABLE or not MLFLOW_ENABLED:
        logging.getLogger(__name__).info(
            "MLflow tracing is disabled; observability will run without tracing."
        )
        return

    # Connect to MLflow server
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    # Enable MLflow auto-tracing for LangChain
    try:
        mlflow.langchain.autolog()
    except Exception as e:
        logging.getLogger(__name__).warning("LangChain autolog failed: %s", e)

    # Enable Gemini auto-logging
    try:
        mlflow.gemini.autolog()
    except Exception:
        logging.getLogger(__name__).warning("Gemini autolog not available.")


# ── Tracing helper ────────────────────────────────────────────────────────────

def trace_agent(agent_type: str):
    """
    Decorator that wraps an agent run function with MLflow tracing.
    Records inputs, outputs, and metrics as a nested span inside the active run.

    Usage:
        @trace_agent("frontend_lld")
        def run(...):
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not _MLFLOW_AVAILABLE or not MLFLOW_ENABLED:
                return fn(*args, **kwargs)

            with mlflow.start_span(name=f"{agent_type}.run") as span:
                span.set_inputs({
                    "agent_type":  agent_type,
                    "user_input":  str(kwargs.get("user_input", ""))[:200],
                    "session_id":  str(kwargs.get("context").session.session_id)
                    if kwargs.get("context") else "—",
                })
                try:
                    result = fn(*args, **kwargs)
                    span.set_outputs({
                        "validation_score":    result.validation_score or 0,
                        "was_refined":         result.was_refined,
                        "refinement_attempts": result.refinement_attempts,
                        "output_length":       len(result.output),
                    })
                    return result
                except Exception as exc:
                    span.set_outputs({"error": str(exc)})
                    raise
        return wrapper
    return decorator