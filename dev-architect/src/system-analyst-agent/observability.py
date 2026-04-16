import logging
import os


def setup_logging() -> None:
    """Configure application-wide logging once, or update level if already configured."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    else:
        root_logger.setLevel(log_level)


def setup_mlflow() -> None:
    """Configure MLflow if installed; no-op when unavailable."""
    try:
        import mlflow  # type: ignore[reportMissingImports]
    except Exception as exc:  # pragma: no cover - depends on runtime environment
        logging.getLogger(__name__).debug("MLflow unavailable, skipping setup: %s", exc)
        return

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "course_skeleton_agent")

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    mlflow.langchain.autolog(run_tracer_inline=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
