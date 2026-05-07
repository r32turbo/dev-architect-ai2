import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import textwrap
import types
import warnings
import time
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

try:
    from database.db import (
        SessionLocal,
        save_requirement_document,
        save_system_architecture_document,
        save_lld_document,
        save_lld_backend_document,
    )
except ImportError:
    from db import (  # type: ignore[reportMissingImports]
        SessionLocal,
        save_requirement_document,
        save_system_architecture_document,
        save_lld_document,
        save_lld_backend_document,
    )

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore[reportMissingImports]


SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent
ADK_ROOT = SRC_DIR / "agent-adk"
SYSTEM_ANALYST_DIR = SRC_DIR / "system_analyst_agent"
SYSTEM_ANALYST_PROMPT_PATH = SYSTEM_ANALYST_DIR / "prompts.py"
SYSTEM_ARCHITECT_DIR = SRC_DIR / "system_architect_agent"
FRONTEND_LLD_DIR = SRC_DIR / "frontend-lld-agent"
LLD_BACKEND_DIR = SRC_DIR / "lld_backend_agent"
GENERIC_LLD_DIR = SRC_DIR / "generic-lld-agent"

_CACHED_SYSTEM_ANALYST_ENTRY_PATH: Path | None = None
_CACHED_SYSTEM_ARCHITECT_ENTRY_PATH: Path | None = None
_CACHED_FRONTEND_LLD_ENTRY_PATH: Path | None = None
_CACHED_LLD_BACKEND_ENTRY_PATH: Path | None = None
_CACHED_GENERIC_LLD_ENTRY_PATH: Path | None = None

# Hide known ChatVertexAI deprecation warnings from terminal output.
warnings.filterwarnings(
    "ignore",
    message=r".*ChatVertexAI.*deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*Use \[`ChatGoogleGenerativeAI`\].*",
    category=DeprecationWarning,
)
try:
    from langchain_core._api.deprecation import LangChainDeprecationWarning

    warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
except Exception:
    pass

if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

logger = logging.getLogger(__name__)

# Configure root logger to write to a single overwrite file per run and to stdout.
try:
    log_path_env = os.getenv("SUPERVISOR_OUTPUT_PATH", "").strip()
    if log_path_env:
        candidate = Path(log_path_env)
        if candidate.is_dir():
            log_file_path = candidate / "sup_output.txt"
        else:
            log_file_path = candidate
    else:
        log_file_path = WORKSPACE_ROOT / "sup_output.txt"

    # Ensure parent exists
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
    # Use original stdout so we can safely replace sys.stdout later
    stream_handler = logging.StreamHandler(sys.__stdout__)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Replace existing handlers so repeated imports don't duplicate output
    root_logger.handlers = [file_handler, stream_handler]
    root_logger.setLevel(logging.INFO)
    logger.info("Supervisor logging initialized, writing to %s", str(log_file_path))
except Exception:
    # If logging configuration fails, continue without file logging
    logger.exception("Failed to configure file logging for supervisor output")
else:
    try:
        # Tee printed output (print/print-like) to the same file so plain prints are captured.
        class _Tee:
            def __init__(self, *streams):
                self._streams = streams

            def write(self, data):
                for s in self._streams:
                    try:
                        s.write(data)
                    except Exception:
                        pass

            def flush(self):
                for s in self._streams:
                    try:
                        s.flush()
                    except Exception:
                        pass

        # Open a separate file object for plain text writes (append to avoid truncating logging header)
        file_obj = open(log_file_path, mode="a", encoding="utf-8")
        sys.stdout = _Tee(sys.__stdout__, file_obj)
        sys.stderr = _Tee(sys.__stderr__, file_obj)
    except Exception:
        logger.exception("Failed to tee stdout/stderr to supervisor log file")


def _resolve_chunk_size() -> int:
    value = str(os.getenv("SUPERVISOR_OUTPUT_CHUNK_SIZE", "6000")).strip()
    try:
        size = int(value)
    except ValueError:
        size = 6000
    return max(500, size)


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    payload = str(text or "")
    if not payload:
        return []
    return [payload[i : i + chunk_size] for i in range(0, len(payload), chunk_size)]


def _store_agent_chunks(agent_key: str, output: str, context: "AgentContext | None") -> None:
    if context is None or not callable(getattr(context, "set_state", None)):
        return
    chunks = _chunk_text(str(output or ""), _resolve_chunk_size())
    context.set_state(f"{agent_key}.output_chunks", chunks)
    context.set_state(f"{agent_key}.output_chunk_count", len(chunks))


def _context_session_id(context: "AgentContext | None") -> str:
    session = getattr(context, "session", None)
    return str(getattr(session, "session_id", "") or "")


def _close_db(db: Any) -> None:
    try:
        db.close()
    except Exception:
        pass


def _save_requirement_output(user_input: str, output: str, context: "AgentContext | None") -> int | None:
    db = SessionLocal()
    try:
        doc = save_requirement_document(
            db=db,
            user_input=str(user_input or "").strip(),
            output=str(output or "").strip(),
            session_id=_context_session_id(context),
        )
        return doc.id
    except Exception as exc:
        logger.warning("Failed to save requirement output: %s", exc)
        return None
    finally:
        _close_db(db)


def _save_architecture_output(user_input: str, output: str, context: "AgentContext | None") -> int | None:
    db = SessionLocal()
    try:
        doc = save_system_architecture_document(
            db=db,
            analyst_document=str(user_input or "").strip(),
            output=str(output or "").strip(),
            session_id=_context_session_id(context),
        )
        return doc.id
    except Exception as exc:
        logger.warning("Failed to save architecture output: %s", exc)
        return None
    finally:
        _close_db(db)


def _save_lld_output(
    agent_type: str,
    user_input: str,
    output: str,
    context: "AgentContext | None",
    requirement_doc: str = "",
    architecture_doc: str = "",
) -> int | None:
    db = SessionLocal()
    try:
        doc = save_lld_document(
            db=db,
            agent_type=agent_type,
            user_input=str(user_input or "").strip(),
            output=str(output or "").strip(),
            requirement_doc=str(requirement_doc or "").strip(),
            architecture_doc=str(architecture_doc or "").strip(),
            session_id=_context_session_id(context),
        )
        return doc.id
    except Exception as exc:
        logger.warning("Failed to save %s output: %s", agent_type, exc)
        return None
    finally:
        _close_db(db)


def _save_backend_output(
    user_input: str,
    output: str,
    context: "AgentContext | None",
    requirement_doc: str = "",
    architecture_doc_id: int | None = None,
) -> int | None:
    db = SessionLocal()
    try:
        doc = save_lld_backend_document(
            db=db,
            user_input=str(user_input or "").strip(),
            output=str(output or "").strip(),
            requirement_doc=str(requirement_doc or "").strip(),
            architecture_doc_id=architecture_doc_id,
            session_id=_context_session_id(context),
        )
        return doc.id
    except Exception as exc:
        logger.warning("Failed to save backend LLD output: %s", exc)
        return None
    finally:
        _close_db(db)


def _write_full_output(text: str) -> Path | None:
    raw_path = str(os.getenv("SUPERVISOR_OUTPUT_PATH", "")).strip()
    output_path = Path(raw_path) if raw_path else WORKSPACE_ROOT / "supervisor_output_latest.txt"
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(text or ""), encoding="utf-8")
        return output_path
    except Exception as exc:
        logger.warning("Failed to write supervisor output file: %s", exc)
        return None


def _print_chunked_output(text: str) -> None:
    payload = str(text or "")
    if not payload:
        print("No output generated.")
        return

    chunks = _chunk_text(payload, _resolve_chunk_size())
    if len(chunks) <= 1:
        print(payload)
        return

    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        print(f"\n--- OUTPUT CHUNK {index}/{total} ---\n")
        print(chunk)


def _resolve_system_analyst_entry_path() -> Path:
    global _CACHED_SYSTEM_ANALYST_ENTRY_PATH
    if _CACHED_SYSTEM_ANALYST_ENTRY_PATH is not None:
        return _CACHED_SYSTEM_ANALYST_ENTRY_PATH
    preferred = SYSTEM_ANALYST_DIR / "analyst_agent.py"
    legacy = SYSTEM_ANALYST_DIR / "main.py"
    if preferred.is_file():
        _CACHED_SYSTEM_ANALYST_ENTRY_PATH = preferred
        return preferred
    if legacy.is_file():
        _CACHED_SYSTEM_ANALYST_ENTRY_PATH = legacy
        return legacy
    raise FileNotFoundError(
        f"System analyst entry file not found. Expected one of: {preferred}, {legacy}"
    )


def _resolve_system_architect_entry_path() -> Path:
    global _CACHED_SYSTEM_ARCHITECT_ENTRY_PATH
    if _CACHED_SYSTEM_ARCHITECT_ENTRY_PATH is not None:
        return _CACHED_SYSTEM_ARCHITECT_ENTRY_PATH
    preferred = SYSTEM_ARCHITECT_DIR / "sysaapp.py"
    if preferred.is_file():
        _CACHED_SYSTEM_ARCHITECT_ENTRY_PATH = preferred
        return preferred
    raise FileNotFoundError(f"System architect entry file not found. Expected: {preferred}")


def _resolve_frontend_lld_entry_path() -> Path:
    global _CACHED_FRONTEND_LLD_ENTRY_PATH
    if _CACHED_FRONTEND_LLD_ENTRY_PATH is not None:
        return _CACHED_FRONTEND_LLD_ENTRY_PATH
    preferred = FRONTEND_LLD_DIR / "frontend_graph.py"
    if preferred.is_file():
        _CACHED_FRONTEND_LLD_ENTRY_PATH = preferred
        return preferred
    raise FileNotFoundError(f"Frontend LLD entry file not found. Expected: {preferred}")


def _resolve_lld_backend_entry_path() -> Path:
    global _CACHED_LLD_BACKEND_ENTRY_PATH
    if _CACHED_LLD_BACKEND_ENTRY_PATH is not None:
        return _CACHED_LLD_BACKEND_ENTRY_PATH
    preferred = LLD_BACKEND_DIR / "lldbapp.py"
    if preferred.is_file():
        _CACHED_LLD_BACKEND_ENTRY_PATH = preferred
        return preferred
    raise FileNotFoundError(f"Backend LLD entry file not found. Expected: {preferred}")


def _resolve_generic_lld_entry_path() -> Path:
    global _CACHED_GENERIC_LLD_ENTRY_PATH
    if _CACHED_GENERIC_LLD_ENTRY_PATH is not None:
        return _CACHED_GENERIC_LLD_ENTRY_PATH
    preferred = GENERIC_LLD_DIR / "generic_graph.py"
    if preferred.is_file():
        _CACHED_GENERIC_LLD_ENTRY_PATH = preferred
        return preferred
    raise FileNotFoundError(f"Generic LLD entry file not found. Expected: {preferred}")


def _ensure_reusableagents_package() -> None:
    """Expose src/agent-adk as importable package name `reusableagents`."""
    pkg = sys.modules.get("reusableagents")
    if pkg is not None:
        return

    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(ADK_ROOT)]
    sys.modules["reusableagents"] = reusableagents_pkg


def _resolve_lld_app_path() -> Path:
    """Resolve LLD app path, verifying all required files exist."""
    required_files = ["prompts.py", "state.py"]
    entrypoint_names = ["lld_createagent.py", "app.py"]

    env_path = os.getenv("LLD_APP_PATH")
    if env_path:
        candidate = Path(env_path)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        if candidate.is_file():
            parent_dir = candidate.parent
            entrypoint_ok = candidate.name in entrypoint_names
            all_exist = all((parent_dir / f).is_file() for f in required_files)
            if entrypoint_ok and all_exist:
                return candidate

    candidates = [
        SRC_DIR / "low-level-design-agent" / "lld_createagent.py",
        SRC_DIR / "low-level-design-agent" / "app.py",
        SRC_DIR / "fb-lld-creatingagent" / "app.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            parent_dir = candidate.parent
            all_exist = all((parent_dir / f).is_file() for f in required_files)
            if all_exist:
                return candidate

    raise FileNotFoundError(
        f"Could not find complete LLD app (needs entrypoint in {entrypoint_names} and {', '.join(required_files)}). "
        "Set LLD_APP_PATH to your complete low-level-design-agent entrypoint path, "
        "or the missing files will be loaded from the fb-lld-creatingagent branch."
    )





def _materialize_lld_app_from_branch(branch_name: str) -> Path:
    rel_files = {
        "lld_createagent.py": "dev-architect/src/low-level-design-agent/lld_createagent.py",
        "prompts.py": "dev-architect/src/low-level-design-agent/prompts.py",
        "state.py": "dev-architect/src/low-level-design-agent/state.py",
    }

    temp_dir = Path(tempfile.mkdtemp(prefix="lld_from_branch_"))

    for local_name, rel_path in rel_files.items():
        try:
            completed = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "show", f"{branch_name}:{rel_path}"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            if local_name != "lld_createagent.py":
                raise
            legacy_rel_path = "dev-architect/src/low-level-design-agent/app.py"
            completed = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "show", f"{branch_name}:{legacy_rel_path}"],
                capture_output=True,
                text=True,
                check=True,
            )
        content = completed.stdout
        if local_name == "lld_createagent.py":
            # Normalize imports to reusableagents.* so all modules resolve to
            # the same class identities at runtime.
            content = content.replace("agents.react_agent", "reusableagents.agents.react_agent")
            content = content.replace("agents.validator", "reusableagents.agents.validator")
            content = content.replace("config.settings", "reusableagents.config.settings")
            content = content.replace("prompts.base", "reusableagents.prompts.base")
            content = content.replace("enable_validation=True", "enable_validation=False")
        (temp_dir / local_name).write_text(content, encoding="utf-8")

    return temp_dir / "lld_createagent.py"


def _load_environment() -> None:
    for path in [Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break


def _load_module(module_name: str, file_path: Path) -> ModuleType:
    module_dir = str(file_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _warmup_worker(worker: Any, module_loader: Any, module_name: str, file_path: Path) -> None:
    try:
        module = module_loader(module_name, file_path)
        if hasattr(module, "load_environment"):
            module.load_environment()
        build_agent = getattr(module, "build_agent", None)
        if callable(build_agent):
            worker._module = module
            worker._agent = build_agent()
            logger.info("Prewarmed %s", module_name)
    except Exception as exc:
        logger.warning("Failed to prewarm %s: %s", module_name, exc)


def _load_adk_components():
    _ensure_reusableagents_package()

    supervisor_mod = __import__(
        "reusableagents.agents.supervisor",
        fromlist=["SupervisorAgent", "WorkerSpec"],
    )
    react_mod = __import__("reusableagents.agents.react_agent", fromlist=["AgentResponse"])
    llm_mod = __import__("reusableagents.llm.gemini", fromlist=["create_agent_llm"])
    prompts_mod = __import__("reusableagents.prompts.base", fromlist=["PromptBuilder"])
    config_mod = __import__(
        "reusableagents.config.settings",
        fromlist=["SupervisorConfig", "ExecutionMode", "GeminiConfig"],
    )

    return (
        supervisor_mod.SupervisorAgent,
        supervisor_mod.WorkerSpec,
        react_mod.AgentResponse,
        llm_mod.create_agent_llm,
        prompts_mod.PromptBuilder,
        config_mod.SupervisorConfig,
        config_mod.ExecutionMode,
        config_mod.GeminiConfig,
    )


class SystemAnalystWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type
        self._agent = None

    def run(
        self,
        task: str | None = None,
        context: "AgentContext | None" = None,
        user_input: str | None = None,
    ):
        resolved_user_input = str(user_input if user_input is not None else task or "").strip()
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="system_analyst_worker",
                event="started",
                detail=resolved_user_input[:160],
            )
        try:
            if self._agent is None:
                prompt_module = _load_module("system_analyst_prompt", SYSTEM_ANALYST_PROMPT_PATH)
                sys.modules["prompt"] = prompt_module
                sys.modules["prompts"] = prompt_module

                analyst_module = _load_module(
                    "system_analyst_main", _resolve_system_analyst_entry_path()
                )
                if hasattr(analyst_module, "load_environment"):
                    analyst_module.load_environment()
                self._agent = analyst_module.build_agent()
                self._module = analyst_module

            output = ""
            run_in_module = getattr(getattr(self, "_module", None), "run_system_analysis", None)
            if callable(run_in_module):
                if context is not None and callable(getattr(context, "set_state", None)):
                    context.set_state("user_goal", resolved_user_input)
                try:
                    output = run_in_module(context=context)
                except TypeError as exc:
                    if "required positional argument" not in str(exc):
                        raise
                    output = run_in_module(user_goal=resolved_user_input, context=context)
            else:
                goal = resolved_user_input
                if isinstance(getattr(context, "state", None), dict):
                    goal = str(context.state.get("user_goal", goal)).strip() or goal
                run_kwargs = {"user_goal": goal}
                if context is not None:
                    run_kwargs["context"] = context
                result = self._agent.run(**run_kwargs)
                output = result.output if hasattr(result, "output") else str(result)
            requirement_doc_id = _save_requirement_output(resolved_user_input, output, context)
            _store_agent_chunks("system_analyst", str(output).strip(), context)
            if context is not None and callable(getattr(context, "set_state", None)):
                context.set_state("requirement_doc", str(output).strip())
                context.set_state("system_analyst.output", str(output).strip())
                if requirement_doc_id is not None:
                    context.set_state("system_requirement.document_id", requirement_doc_id)
                context.record(agent_name="system_analyst_worker", event="completed")
                return self._agent_response_type(output=str(output).strip())
        finally:
            # compatibility no-op: previous observability cleanup removed
            pass

class LLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type

    def run(self, task: str, context: "AgentContext | None" = None):
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="lld_worker",
                event="started",
                detail=str(task)[:160],
            )
        try:
            # Prefer local LLD app so local prompt/code edits are applied.
            # Set LLD_FORCE_BRANCH=1 to always load branch materialization.
            force_branch = os.getenv("LLD_FORCE_BRANCH", "0").strip().lower() in {
                "1", "true", "yes", "on"
            }
            if force_branch:
                branch_name = os.getenv("LLD_SOURCE_BRANCH", "fb-lld-creatingagent")
                lld_app_path = _materialize_lld_app_from_branch(branch_name)
            else:
                try:
                    lld_app_path = _resolve_lld_app_path()
                except FileNotFoundError:
                    branch_name = os.getenv("LLD_SOURCE_BRANCH", "fb-lld-creatingagent")
                    lld_app_path = _materialize_lld_app_from_branch(branch_name)

            runner = textwrap.dedent(
                """
                import importlib.util
                import json
                import sys
                import types
                from pathlib import Path

                adk_root = Path(sys.argv[1])
                app_path = Path(sys.argv[2])
                payload = {}
                raw_input = sys.stdin.read()
                try:
                    payload = json.loads(raw_input) if raw_input.strip() else {}
                except json.JSONDecodeError:
                    payload = {"lld_input": raw_input}
                lld_input = str(payload.get("lld_input", ""))
                context_state = payload.get("context_state", {})

                if str(adk_root) not in sys.path:
                    sys.path.insert(0, str(adk_root))

                app_dir = str(app_path.parent)

                if "reusableagents" not in sys.modules:
                    pkg = types.ModuleType("reusableagents")
                    pkg.__path__ = [str(adk_root)]
                    sys.modules["reusableagents"] = pkg

                # Ensure reusableagents.* and top-level modules resolve to identical objects.
                # This prevents PromptBuilder type identity mismatches in branch LLD code.
                reusable_agents_mod = importlib.import_module("reusableagents.agents")
                react_mod = importlib.import_module("reusableagents.agents.react_agent")
                validator_mod = importlib.import_module("reusableagents.agents.validator")
                reusable_prompts_mod = importlib.import_module("reusableagents.prompts")
                prompts_base_mod = importlib.import_module("reusableagents.prompts.base")
                reusable_config_mod = importlib.import_module("reusableagents.config")
                config_settings_mod = importlib.import_module("reusableagents.config.settings")

                sys.modules["agents"] = reusable_agents_mod
                sys.modules["agents.react_agent"] = react_mod
                sys.modules["agents.validator"] = validator_mod
                sys.modules["prompts"] = reusable_prompts_mod
                sys.modules["prompts.base"] = prompts_base_mod
                sys.modules["config"] = reusable_config_mod
                sys.modules["config.settings"] = config_settings_mod

                # Pre-load ADK prompts package to prevent branch prompts.py from shadowing it
                prompts_pkg_path = adk_root / "prompts"
                if prompts_pkg_path.is_dir() and str(adk_root) in sys.path:
                    # Load prompts as a package so "from prompts.base" works
                    try:
                        import prompts.base
                    except ImportError:
                        pass

                package_name = "lld_runtime_pkg"
                if package_name not in sys.modules:
                    pkg = types.ModuleType(package_name)
                    pkg.__path__ = [app_dir]
                    sys.modules[package_name] = pkg

                spec = importlib.util.spec_from_file_location(
                    f"{package_name}.app",
                    app_path,
                    submodule_search_locations=[app_dir],
                )
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load LLD app from {app_path}")

                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                context_obj = None
                if isinstance(context_state, dict):
                    try:
                        context_mod = importlib.import_module("reusableagents.context")
                        context_obj = context_mod.AgentContext(state=context_state)
                    except Exception:
                        context_obj = None

                if hasattr(module, "graph"):
                    result = module.graph.invoke({"lld_input": lld_input})
                elif hasattr(module, "run_pipeline"):
                    try:
                        result = module.run_pipeline(lld_input, context=context_obj)
                    except TypeError as exc:
                        if "unexpected keyword argument 'context'" not in str(exc):
                            raise
                        result = module.run_pipeline(lld_input)
                else:
                    raise RuntimeError("LLD module does not expose graph or run_pipeline")
                print(
                    json.dumps(
                        {
                            "sections": str(result.get("sections", "")).strip(),
                            "architecture_analysis": str(result.get("architecture_analysis", "")).strip(),
                            "final_report": str(result.get("final_report", "")).strip(),
                        }
                    )
                )
                """
            ).strip()

            context_state: dict[str, Any] = {}

            if isinstance(getattr(context, "state", None), dict):
                s = context.state

                context_state = {
                    "user_goal": s.get("user_goal", ""),
                    "system_architect.document_id": s.get(
                        "system_architect.document_id"
                    ),
                    "requirement_doc": s.get("requirement_doc", "")[:2000],
                    "architecture_doc": s.get("architecture_doc", "")[:2000],
                }

            MAX_LLD_INPUT_CHARS = int(os.getenv("LLD_MAX_INPUT_CHARS", "12000"))

            if len(task) > MAX_LLD_INPUT_CHARS:
                logger.warning(
                    "lld_agent input is %d chars, truncating to %d to avoid timeout",
                    len(task),
                    MAX_LLD_INPUT_CHARS,
                )

                task = (
                    task[:MAX_LLD_INPUT_CHARS]
                    + "\n\n[... truncated for LLD processing ...]"
                )

            subprocess_input = json.dumps(
                {
                    "lld_input": task,
                    "context_state": context_state,
                },
                ensure_ascii=True,
            )

            logger.info(
                "Running %s with input chars=%d context chars=%d",
                "lld_agent",
                len(task),
                len(json.dumps(context_state)),
            )

            completed = subprocess.run(
                [sys.executable, "-c", runner, str(ADK_ROOT), str(lld_app_path)],
                input=subprocess_input,
                capture_output=True,
                text=True,
                check=True,
            )

            stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
            if not stdout_lines:
                raise RuntimeError("LLD subprocess produced no output")

            payload = json.loads(stdout_lines[-1])
            # Normalize generic model apologies into explicit failure text.
            final_report_text = str(payload.get("final_report", ""))
            if "i am sorry" in final_report_text.lower() and "error" in final_report_text.lower():
                payload["final_report"] = (
                    "LLD execution failed with a model-generated error response: "
                    f"{final_report_text}"
                )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr or stdout or str(exc)
            payload = {
                "sections": "",
                "architecture_analysis": "",
                "final_report": f"LLD subprocess execution failed: {details}",
            }
        except Exception as exc:
            payload = {
                "sections": "",
                "architecture_analysis": "",
                "final_report": f"LLD execution failed: {exc}",
            }

        output = json.dumps(payload, ensure_ascii=True)
        _store_agent_chunks("lld", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("lld.output", output)
            context.record(agent_name="lld_worker", event="completed")
        return self._agent_response_type(output=output)


class SystemArchitectWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type
        self._module = None

    def run(self, task: str, context: "AgentContext | None" = None):
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="system_architect_worker",
                event="started",
                detail=str(task)[:160],
            )

        if self._module is None:
            try:
                # Import as a package module first so relative imports in sysaapp.py
                # resolve correctly and do not fall back to ADK prompts package.
                self._module = __import__(
                    "system_architect_agent.sysaapp",
                    fromlist=["run_system_architect"],
                )
            except Exception:
                self._module = _load_module(
                    "system_architect_main", _resolve_system_architect_entry_path()
                )

            if hasattr(self._module, "load_environment"):
                self._module.load_environment()

        run_in_module = getattr(self._module, "run_system_architect", None)
        if not callable(run_in_module):
            raise RuntimeError("System architect module does not expose run_system_architect")

        state = getattr(context, "state", None)
        state = state if isinstance(state, dict) else {}

        user_input = str(state.get("user_goal", "")).strip() or str(task).strip()
        requirement_doc = (
            str(state.get("requirement_doc", "")).strip()
            or str(state.get("system_analyst.output", "")).strip()
            or str(task).strip()
        )

        try:
            output = str(
                run_in_module(
                    user_input=user_input,
                    requirement_doc=requirement_doc,
                    context=context,
                )
            ).strip()
        except TypeError as exc:
            # Backward-compatible fallback for older function signatures.
            if "unexpected keyword argument" not in str(exc):
                raise
            output = str(run_in_module(input_document=task, context=context)).strip()

        architecture_doc_id = _save_architecture_output(task, output, context)
        _store_agent_chunks("system_architect", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("architecture_doc", output)
            context.set_state("system_architect.output", output)
            if architecture_doc_id is not None:
                context.set_state("system_architect.document_id", architecture_doc_id)
            context.record(agent_name="system_architect_worker", event="completed")
        return self._agent_response_type(output=output)


class FrontendLLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type
        self._module = None
        self._agent = None

    def run(self, task: str, context: "AgentContext | None" = None):
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="frontend_lld_worker",
                event="started",
                detail=str(task)[:160],
            )

        if self._module is None:
            self._module = _load_module("frontend_lld_main", _resolve_frontend_lld_entry_path())
        if self._agent is None:
            build_agent = getattr(self._module, "build_agent", None)
            if not callable(build_agent):
                raise RuntimeError("Frontend LLD module does not expose build_agent")
            self._agent = build_agent()

        state = getattr(context, "state", None)
        state = state if isinstance(state, dict) else {}
        user_input = str(state.get("user_goal", "")).strip() or str(task).strip()
        # Prefer explicit context fields when provided by the API caller.
        requirement_doc = (
            str(state.get("requirement_doc", "")).strip()
            or str(state.get("system_analyst.output", "")).strip()
            or str(task).strip()
        )
        architecture_doc = (
            str(state.get("architecture_doc", "")).strip()
            or str(state.get("system_architect.output", "")).strip()
            or str(task).strip()
        )

        result = self._agent.run(
            context=context,
            user_input=user_input,
            requirement_doc=requirement_doc,
            architecture_doc=architecture_doc,
        )
        output = result.output if hasattr(result, "output") else str(result)
        output = str(output).strip()

        frontend_doc_id = _save_lld_output(
            "frontend_lld",
            user_input,
            output,
            context,
            requirement_doc=requirement_doc,
            architecture_doc=architecture_doc,
        )

        _store_agent_chunks("frontend_lld", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("frontend_lld.output", output)
            if frontend_doc_id is not None:
                context.set_state("frontend_lld.document_id", frontend_doc_id)
            context.record(agent_name="frontend_lld_worker", event="completed")
        return self._agent_response_type(output=output)


class BackendLLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type

    def run(self, task: str, context: "AgentContext | None" = None):
        # TODO: backend_lld_agent currently receives large markdown blobs as task input.
        # TODO: Future improvement: consume structured JSON artifacts (sections, APIs, schema summaries)
        # TODO: instead of raw generated markdown to eliminate payload bloat and re-parsing overhead.
        # TODO: This would reduce input size by 90%+ and enable type-safe processing.
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="backend_lld_worker",
                event="started",
                detail=str(task)[:160],
            )

        try:
            backend_app_path = _resolve_lld_backend_entry_path()
            runner = textwrap.dedent(
                """
                import importlib.util
                import json
                import sys
                import types
                from pathlib import Path

                adk_root = Path(sys.argv[1])
                backend_app_path = Path(sys.argv[2])
                backend_dir = backend_app_path.parent
                backend_root = backend_dir.parent

                payload = {}
                raw_input = sys.stdin.read()
                try:
                    payload = json.loads(raw_input) if raw_input.strip() else {}
                except json.JSONDecodeError:
                    payload = {"lld_input": raw_input}

                lld_input = str(payload.get("lld_input", ""))
                context_state = payload.get("context_state", {})

                if str(backend_root) not in sys.path:
                    sys.path.insert(0, str(backend_root))
                if str(backend_dir) not in sys.path:
                    sys.path.insert(0, str(backend_dir))
                if str(adk_root) not in sys.path:
                    sys.path.insert(0, str(adk_root))

                if "reusableagents" not in sys.modules:
                    pkg = types.ModuleType("reusableagents")
                    pkg.__path__ = [str(adk_root)]
                    sys.modules["reusableagents"] = pkg

                prompts_spec = importlib.util.spec_from_file_location(
                    "prompts",
                    backend_dir / "prompts.py",
                )
                prompts_module = importlib.util.module_from_spec(prompts_spec)
                sys.modules["prompts"] = prompts_module
                prompts_spec.loader.exec_module(prompts_module)

                backend_spec = importlib.util.spec_from_file_location(
                    "backend_runtime",
                    backend_app_path,
                )
                backend_module = importlib.util.module_from_spec(backend_spec)
                backend_spec.loader.exec_module(backend_module)

                context_obj = None
                if isinstance(context_state, dict):
                    try:
                        context_mod = importlib.import_module("reusableagents.context")
                        context_obj = context_mod.AgentContext(state=context_state)
                    except Exception:
                        context_obj = None

                if context_obj is not None:
                    output = backend_module.run_backend_lld(lld_input=lld_input, context=context_obj)
                else:
                    output = backend_module.run_backend_lld(lld_input=lld_input)

                print(json.dumps({"backend_output": str(output).strip()}))
                """
            ).strip()

            context_state: dict[str, Any] = {}

            if isinstance(getattr(context, "state", None), dict):
                s = context.state

                context_state = {
                    "user_goal": s.get("user_goal", ""),
                    "system_architect.document_id": s.get(
                        "system_architect.document_id"
                    ),
                    "requirement_doc": s.get("requirement_doc", "")[:2000],
                    "architecture_doc": s.get("architecture_doc", "")[:2000],
                }

            # CRITICAL FIX: Incoming task parameter (summarized payload) has HIGHEST priority
            # and MUST NOT be overwritten by full context.state["lld.output"]
            lld_input = str(task).strip()
            lld_input_original_size = len(lld_input)
            
            logger.debug(
                "BackendLLDWorker.run() received task with %d chars (summarized from upstream)",
                lld_input_original_size
            )
            
            # Only fall back to context.state if task is empty, and CAP the fallback
            if not lld_input and isinstance(getattr(context, "state", None), dict):
                state_dict = context.state
                
                # Fallback chain with caps to prevent re-inflating the payload
                fallback_lld = (
                    str(state_dict.get("lld.output", ""))[:4000]
                    or str(state_dict.get("system_architect.output", ""))[:4000]
                    or str(state_dict.get("requirement_doc", "")).strip()
                )
                if fallback_lld:
                    lld_input = fallback_lld
                    logger.info(
                        "BackendLLDWorker: task was empty, using fallback from context.state (capped to 4000 chars)"
                    )

            # DEFENSIVE: Apply hard cap before subprocess to ensure summarized payload is never re-inflated
            backend_lld_max_chars = int(os.getenv("BACKEND_LLD_MAX_INPUT_CHARS", "8000"))
            if len(lld_input) > backend_lld_max_chars:
                logger.warning(
                    "BackendLLDWorker: lld_input exceeds BACKEND_LLD_MAX_INPUT_CHARS=%d, truncating from %d to %d chars",
                    backend_lld_max_chars,
                    len(lld_input),
                    backend_lld_max_chars
                )
                lld_input = lld_input[:backend_lld_max_chars] + "\n\n[... truncated for backend processing ...]"

            logger.info(
                "BackendLLDWorker final payload: original_received=%d chars, after_processing=%d chars, context=%d chars",
                lld_input_original_size,
                len(lld_input),
                len(json.dumps(context_state))
            )

            completed = subprocess.run(
                [sys.executable, "-c", runner, str(ADK_ROOT), str(backend_app_path)],
                input=json.dumps({"lld_input": lld_input, "context_state": context_state}, ensure_ascii=True),
                capture_output=True,
                text=True,
                check=True,
            )
            stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
            if not stdout_lines:
                raise RuntimeError("Backend LLD subprocess produced no output")
            payload = json.loads(stdout_lines[-1])
            output = str(payload.get("backend_output", "")).strip()
            backend_architecture_doc_id = None
            if isinstance(getattr(context, "state", None), dict):
                raw_arch_id = context.state.get("system_architect.document_id")
                if raw_arch_id is not None:
                    try:
                        backend_architecture_doc_id = int(raw_arch_id)
                    except (TypeError, ValueError):
                        backend_architecture_doc_id = None
            backend_doc_id = _save_backend_output(
                lld_input,
                output,
                context,
                requirement_doc=str(getattr(context, "state", {}).get("requirement_doc", "")) if isinstance(getattr(context, "state", None), dict) else "",
                architecture_doc_id=backend_architecture_doc_id,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr or stdout or str(exc)
            output = f"Backend LLD subprocess execution failed: {details}"
        except Exception as exc:
            output = f"Backend LLD execution failed: {exc}"

        _store_agent_chunks("backend_lld", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("backend_lld.output", output)
            if 'backend_doc_id' in locals() and backend_doc_id is not None:
                context.set_state("backend_lld.document_id", backend_doc_id)
            context.record(agent_name="backend_lld_worker", event="completed")
        return self._agent_response_type(output=output)


class GenericLLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type

    def run(self, task: str, context: "AgentContext | None" = None):
        # TODO: generic_lld_agent receives summarized backend output as task parameter.
        # TODO: Future: decouple from backend stage entirely - run in parallel from system_architect.
        # TODO: This would enable independent LLD variants (frontend, backend, generic, mobile, API-only)
        # TODO: running concurrently with 70% runtime reduction and isolated failure domains.
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="generic_lld_worker",
                event="started",
                detail=str(task)[:160],
            )

        try:
            generic_path = _resolve_generic_lld_entry_path()
            runner = textwrap.dedent(
                """
                import importlib.util
                import json
                import sys
                import types
                from pathlib import Path

                adk_root = Path(sys.argv[1])
                generic_path = Path(sys.argv[2])
                generic_dir = generic_path.parent

                payload = {}
                raw_input = sys.stdin.read()
                try:
                    payload = json.loads(raw_input) if raw_input.strip() else {}
                except json.JSONDecodeError:
                    payload = {"task": raw_input}

                user_input = str(payload.get("user_input", ""))
                requirement_doc = str(payload.get("requirement_doc", ""))
                architecture_doc = str(payload.get("architecture_doc", ""))
                context_state = payload.get("context_state", {})

                if str(generic_dir) not in sys.path:
                    sys.path.insert(0, str(generic_dir))
                if str(adk_root) not in sys.path:
                    sys.path.insert(0, str(adk_root))

                if "reusableagents" not in sys.modules:
                    pkg = types.ModuleType("reusableagents")
                    pkg.__path__ = [str(adk_root)]
                    sys.modules["reusableagents"] = pkg

                spec = importlib.util.spec_from_file_location("generic_runtime", generic_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                context_obj = None
                if isinstance(context_state, dict):
                    try:
                        context_mod = importlib.import_module("reusableagents.context")
                        context_obj = context_mod.AgentContext(state=context_state)
                    except Exception:
                        context_obj = None

                agent = module.build_agent()
                kwargs = {
                    "user_input": user_input,
                    "requirement_doc": requirement_doc,
                    "architecture_doc": architecture_doc,
                }
                if context_obj is not None:
                    kwargs["context"] = context_obj

                result = agent.run(**kwargs)
                output = result.output if hasattr(result, "output") else str(result)
                print(json.dumps({"generic_output": str(output).strip()}))
                """
            ).strip()

            state = getattr(context, "state", None)
            state = state if isinstance(state, dict) else {}

            # Log received task size for generic LLD agent
            task_size = len(str(task))
            logger.info(
                "GenericLLDWorker.run() received task with %d chars (from summarization layer)",
                task_size
            )

            # Build payload for generic LLD subprocess, preferring explicit context keys.
            # IMPORTANT: task is the summarized backend_lld output passed from upstream
            payload = {
                "user_input": str(state.get("user_goal", task)).strip() or str(task).strip(),
                "requirement_doc": (
                    str(state.get("requirement_doc", "")).strip()
                    or str(state.get("system_analyst.output", task)).strip()
                    or str(task).strip()
                ),
                "architecture_doc": (
                    str(state.get("architecture_doc", "")).strip()
                    or str(state.get("system_architect.output", "")).strip()
                    or str(state.get("lld.final_report", "")).strip()
                    or str(task).strip()
                ),
                "context_state": {
                    "user_goal": state.get("user_goal", ""),
                    "system_architect.document_id": state.get(
                        "system_architect.document_id"
                    ),
                },
            }
            
            # Defensive cap on architecture_doc to prevent re-inflation
            generic_lld_max_input = int(os.getenv("GENERIC_LLD_MAX_INPUT_CHARS", "6000"))
            if len(payload.get("architecture_doc", "")) > generic_lld_max_input:
                original_arch_size = len(payload.get("architecture_doc", ""))
                payload["architecture_doc"] = payload["architecture_doc"][:generic_lld_max_input]
                logger.info(
                    "GenericLLDWorker: architecture_doc capped from %d to %d chars",
                    original_arch_size,
                    generic_lld_max_input
                )
            
            payload_json_size = len(json.dumps(payload))
            logger.info(
                "GenericLLDWorker final payload: task_received=%d chars, total_payload=%d chars",
                task_size,
                payload_json_size
            )

            completed = subprocess.run(
                [sys.executable, "-c", runner, str(ADK_ROOT), str(generic_path)],
                input=json.dumps(payload, ensure_ascii=True),
                capture_output=True,
                text=True,
                check=True,
            )
            stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
            if not stdout_lines:
                raise RuntimeError("Generic LLD subprocess produced no output")
            output_payload = json.loads(stdout_lines[-1])
            output = str(output_payload.get("generic_output", "")).strip()
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr or stdout or str(exc)
            output = f"Generic LLD subprocess execution failed: {details}"
        except Exception as exc:
            output = f"Generic LLD execution failed: {exc}"

        generic_doc_id = _save_lld_output(
            "generic_lld",
            task,
            output,
            context,
            requirement_doc=str(state.get("requirement_doc", "")),
            architecture_doc=str(state.get("architecture_doc", "")) or str(state.get("backend_lld.output", "")),
        )
        _store_agent_chunks("generic_lld", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("generic_lld.output", output)
            if 'generic_doc_id' in locals() and generic_doc_id is not None:
                context.set_state("generic_lld.document_id", generic_doc_id)
            context.record(agent_name="generic_lld_worker", event="completed")
        return self._agent_response_type(output=output)


def _extract_output_text(result: Any) -> str:
    return result.output if hasattr(result, "output") else str(result)


def _run_with_timeout(func: Any, timeout_seconds: int, *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Run a callable with a timeout. Returns (completed, result_or_exc)."""
    holder: dict[str, Any] = {}

    def _target() -> None:
        try:
            holder["result"] = func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            holder["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        return False, TimeoutError(f"Operation timed out after {timeout_seconds}s")
    if "error" in holder:
        return True, holder["error"]
    return True, holder.get("result")


def _is_complete_combined_output(text: str) -> bool:
    required_sections = [
        "User Goal",
        "System Analyst Output",
        "System Architect Output",
        "Frontend LLD Output",
        "LLD Sections",
        "LLD Architecture Analysis",
        "LLD Final Report",
        "Backend LLD Output",
        "Generic LLD Output",
    ]
    parsed = _extract_markdown_sections(str(text or ""))
    return all(section in parsed and bool(str(parsed.get(section, "")).strip()) for section in required_sections)


def _normalize_section_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", str(title or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    aliases = {
        "user goal": "User Goal",
        "system analyst output": "System Analyst Output",
        "system analysis output": "System Analyst Output",
        "system architect output": "System Architect Output",
        "system architecture output": "System Architect Output",
        "frontend lld output": "Frontend LLD Output",
        "frontend output": "Frontend LLD Output",
        "lld sections": "LLD Sections",
        "sections": "LLD Sections",
        "lld architecture analysis": "LLD Architecture Analysis",
        "architecture analysis": "LLD Architecture Analysis",
        "lld final report": "LLD Final Report",
        "final report": "LLD Final Report",
        "backend lld output": "Backend LLD Output",
        "backend output": "Backend LLD Output",
        "generic lld output": "Generic LLD Output",
        "generic output": "Generic LLD Output",
    }
    return aliases.get(cleaned, "")


def _extract_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    heading_re = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")

    for line in str(text or "").splitlines():
        match = heading_re.match(line)
        if match:
            normalized_title = _normalize_section_title(match.group(1))
            if normalized_title:
                current = normalized_title
                sections.setdefault(current, [])
                continue
            current = None
            continue

        if current is not None:
            sections[current].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _normalize_orchestrator_output(text: str, user_goal: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""

    parsed = _extract_markdown_sections(raw)
    if not parsed:
        return raw

    recognized_sections = [
        "User Goal",
        "System Analyst Output",
        "System Architect Output",
        "Frontend LLD Output",
        "LLD Sections",
        "LLD Architecture Analysis",
        "LLD Final Report",
        "Backend LLD Output",
        "Generic LLD Output",
    ]
    recognized_count = sum(1 for name in recognized_sections if name in parsed)
    if recognized_count < 2:
        return raw

    return _render_combined_output(
        user_goal=parsed.get("User Goal", "").strip() or str(user_goal).strip(),
        system_analyst_output=parsed.get("System Analyst Output", "").strip(),
        system_architect_output=parsed.get("System Architect Output", "").strip(),
        frontend_lld_output=parsed.get("Frontend LLD Output", "").strip(),
        lld_sections=parsed.get("LLD Sections", "").strip(),
        lld_architecture_analysis=parsed.get("LLD Architecture Analysis", "").strip(),
        lld_final_report=parsed.get("LLD Final Report", "").strip(),
        backend_lld_output=parsed.get("Backend LLD Output", "").strip(),
        generic_lld_output=parsed.get("Generic LLD Output", "").strip(),
    )


def _coerce_partial_orchestrator_output(text: str, user_goal: str) -> str:
    """Coerce partial orchestrator markdown into canonical combined output."""
    raw = str(text or "").strip()
    if not raw:
        return ""

    normalized = _normalize_orchestrator_output(raw, user_goal)
    if _is_complete_combined_output(normalized):
        return normalized

    parsed = _extract_markdown_sections(raw)
    if not parsed:
        return raw

    user_goal_text = parsed.get("User Goal", "").strip() or str(user_goal).strip()
    system_text = parsed.get("System Analyst Output", "").strip()
    system_architect_text = parsed.get("System Architect Output", "").strip()
    frontend_lld_text = parsed.get("Frontend LLD Output", "").strip()
    lld_sections = parsed.get("LLD Sections", "").strip()
    lld_arch = parsed.get("LLD Architecture Analysis", "").strip()
    lld_final = parsed.get("LLD Final Report", "").strip()
    backend_lld_output = parsed.get("Backend LLD Output", "").strip()
    generic_lld_output = parsed.get("Generic LLD Output", "").strip()

    return _render_combined_output(
        user_goal=user_goal_text,
        system_analyst_output=system_text,
        system_architect_output=system_architect_text,
        frontend_lld_output=frontend_lld_text,
        lld_sections=lld_sections,
        lld_architecture_analysis=lld_arch,
        lld_final_report=lld_final,
        backend_lld_output=backend_lld_output,
        generic_lld_output=generic_lld_output,
    )


def _render_combined_output(
    user_goal: str,
    system_analyst_output: str,
    system_architect_output: str,
    frontend_lld_output: str,
    lld_sections: str,
    lld_architecture_analysis: str,
    lld_final_report: str,
    backend_lld_output: str,
    generic_lld_output: str,
) -> str:
    return (
        "## User Goal\n\n"
        f"{user_goal}\n\n"
        "## System Analyst Output\n\n"
        f"{system_analyst_output}\n\n"
        "## System Architect Output\n\n"
        f"{system_architect_output}\n\n"
        "## Frontend LLD Output\n\n"
        f"{frontend_lld_output}\n\n"
        "## LLD Sections\n\n"
        f"{lld_sections}\n\n"
        "## LLD Architecture Analysis\n\n"
        f"{lld_architecture_analysis}\n\n"
        "## LLD Final Report\n\n"
        f"{lld_final_report}\n\n"
        "## Backend LLD Output\n\n"
        f"{backend_lld_output}\n\n"
        "## Generic LLD Output\n\n"
        f"{generic_lld_output}"
    ).strip()


def _value_or_placeholder(text: str, label: str) -> str:
    value = str(text or "").strip()
    if value:
        return value
    return f"[No output produced by {label}]"


def _render_agent_output_report(context: "AgentContext | None") -> str:
    state = getattr(context, "state", None)
    state = state if isinstance(state, dict) else {}

    system_analyst_output = _value_or_placeholder(
        str(state.get("system_analyst.output", "")),
        "system_analyst",
    )
    system_architect_output = _value_or_placeholder(
        str(state.get("system_architect.output", "")),
        "system_architect_agent",
    )
    frontend_lld_output = _value_or_placeholder(
        str(state.get("frontend_lld.output", "")),
        "frontend_lld_agent",
    )
    backend_lld_output = _value_or_placeholder(
        str(state.get("backend_lld.output", "")),
        "backend_lld_agent",
    )
    generic_lld_output = _value_or_placeholder(
        str(state.get("generic_lld.output", "")),
        "generic_lld_agent",
    )

    lld_output_raw = str(state.get("lld.output", "")).strip()
    lld_output = lld_output_raw
    if lld_output_raw:
        try:
            parsed = json.loads(lld_output_raw)
            if isinstance(parsed, dict):
                lld_output = (
                    "sections:\n"
                    + str(parsed.get("sections", "")).strip()
                    + "\n\narchitecture_analysis:\n"
                    + str(parsed.get("architecture_analysis", "")).strip()
                    + "\n\nfinal_report:\n"
                    + str(parsed.get("final_report", "")).strip()
                ).strip()
        except json.JSONDecodeError:
            lld_output = lld_output_raw
    lld_output = _value_or_placeholder(lld_output, "lld_agent")

    return (
        "## Agent Outputs\n\n"
        "### system_analyst\n\n"
        f"{system_analyst_output}\n\n"
        "### system_architect_agent\n\n"
        f"{system_architect_output}\n\n"
        "### frontend_lld_agent\n\n"
        f"{frontend_lld_output}\n\n"
        "### lld_agent\n\n"
        f"{lld_output}\n\n"
        "### backend_lld_agent\n\n"
        f"{backend_lld_output}\n\n"
        "### generic_lld_agent\n\n"
        f"{generic_lld_output}"
    ).strip()


def _canonicalize_combined_output(
    text: str,
    user_goal: str,
    context: "AgentContext | None" = None,
) -> str:
    """Normalize final output into canonical sections without synthetic fallbacks."""
    # Check if supervisor validation failed
    state = getattr(context, "state", None)
    state = state if isinstance(state, dict) else {}
    
    if state.get("supervisor.validation_failed"):
        error_reason = state.get("supervisor.validation_error", "Output validation failed")
        return f"## Supervisor Execution Failed\n\nThe supervisor pipeline terminated due to output validation failure:\n\n**Reason:** {error_reason}\n\nThe backend LLD agent produced output that does not match the user's goal. Please review the input goal and retry."
    
    parsed = _extract_markdown_sections(str(text or ""))

    def _pick(primary: str, *fallbacks: str) -> str:
        for candidate in (primary, *fallbacks):
            value = str(candidate or "").strip()
            if value:
                return value
        return ""

    user_goal_text = _pick(
        parsed.get("User Goal", ""),
        str(user_goal),
        str(state.get("user_goal", "")),
    )
    system_text = _pick(
        parsed.get("System Analyst Output", ""),
        str(state.get("system_analyst.output", "")),
    )
    system_architect_text = _pick(
        parsed.get("System Architect Output", ""),
        str(state.get("system_architect.output", "")),
    )
    frontend_lld_text = _pick(
        parsed.get("Frontend LLD Output", ""),
        str(state.get("frontend_lld.output", "")),
    )

    lld_output = state.get("lld.output")
    lld_dict = lld_output if isinstance(lld_output, dict) else {}
    if not lld_dict and isinstance(lld_output, str):
        try:
            loaded = json.loads(lld_output)
            lld_dict = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            lld_dict = {}

    lld_sections = _pick(
        parsed.get("LLD Sections", ""),
        str(lld_dict.get("sections", "")),
        str(state.get("lld.sections", "")),
    )
    lld_architecture_analysis = _pick(
        parsed.get("LLD Architecture Analysis", ""),
        str(lld_dict.get("architecture_analysis", "")),
        str(state.get("lld.architecture_analysis", "")),
    )
    lld_final_report = _pick(
        parsed.get("LLD Final Report", ""),
        str(lld_dict.get("final_report", "")),
        str(state.get("lld.final_report", "")),
    )
    backend_lld_output = _pick(
        parsed.get("Backend LLD Output", ""),
        str(state.get("backend_lld.output", "")),
    )
    generic_lld_output = _pick(
        parsed.get("Generic LLD Output", ""),
        str(state.get("generic_lld.output", "")),
    )

    return _render_combined_output(
        user_goal=user_goal_text,
        system_analyst_output=system_text,
        system_architect_output=system_architect_text,
        frontend_lld_output=frontend_lld_text,
        lld_sections=lld_sections,
        lld_architecture_analysis=lld_architecture_analysis,
        lld_final_report=lld_final_report,
        backend_lld_output=backend_lld_output,
        generic_lld_output=generic_lld_output,
    )


def _is_backend_lld_output_relevant(
    backend_output: str,
    user_goal: str,
) -> tuple[bool, str]:

    output_stripped = str(backend_output or "").strip()

    if len(output_stripped) < 200:
        return (
            False,
            "Backend LLD output is too short or empty (< 200 chars)",
        )

    lower = output_stripped.lower()

    apology_patterns = [
        "i am unable to",
        "i cannot provide",
        "i'm sorry, i cannot",
        "i apologize, but i",
    ]

    for pattern in apology_patterns:
        if pattern in lower:
            return (
                False,
                f"Model refusal detected: '{pattern}'",
            )

    return True, ""


def _populate_lld_fields_from_output(context: "AgentContext | None") -> None:
    if context is None or not callable(getattr(context, "set_state", None)):
        return
    state = getattr(context, "state", None)
    if not isinstance(state, dict):
        return
    raw = str(state.get("lld.output", "")).strip()
    if not raw:
        return
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(parsed, dict):
        return

    context.set_state("lld.sections", str(parsed.get("sections", "")).strip())
    context.set_state(
        "lld.architecture_analysis",
        str(parsed.get("architecture_analysis", "")).strip()
    )
    context.set_state("lld.final_report", str(parsed.get("final_report", "")).strip())


def _summarize_for_downstream(text: str, max_chars: int = 4000, focus: str = "general") -> str:
    """
    Compress verbose agent output for downstream consumption.
    
    Extracts only essential information to prevent context explosion:
    - Architecture decisions and constraints
    - Service/component lists (not full implementations)
    - Database schema summaries (not full SQL)
    - API contracts (not full endpoint details)
    - Key technology choices and reasons
    
    Args:
        text: Full verbose output from upstream agent
        max_chars: Maximum output size (default 4000 chars)
        focus: "backend" for backend-focused summary, "generic" for generic-focused, "general" otherwise
    
    Returns:
        Compressed summary, truncated if necessary
    """
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    
    # For JSON lld.output, extract the most relevant field
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            if focus == "backend":
                # For backend_lld_agent: prioritize architecture_analysis + final_report
                content = (
                    str(parsed.get("architecture_analysis", ""))[:2000]
                    + "\n\n"
                    + str(parsed.get("final_report", ""))[:2000]
                )
            elif focus == "generic":
                # For generic_lld_agent: prioritize architecture_analysis + sections
                content = (
                    str(parsed.get("architecture_analysis", ""))[:2000]
                    + "\n\n"
                    + str(parsed.get("sections", ""))[:2000]
                )
            else:
                # Default: all fields concatenated
                content = (
                    str(parsed.get("sections", ""))[:1500]
                    + "\n\n"
                    + str(parsed.get("architecture_analysis", ""))[:1500]
                    + "\n\n"
                    + str(parsed.get("final_report", ""))[:1000]
                )
            return content[:max_chars]
    except (json.JSONDecodeError, ValueError):
        pass
    
    # For non-JSON text, intelligently truncate
    sentences = text.split(". ")
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) + 2 <= max_chars:
            summary += sentence + ". "
        else:
            break
    
    if not summary.strip():
        # Fallback: just slice the text
        summary = text[:max_chars]
    
    return summary.strip()


def _ensure_agent_outputs(user_goal: str, context: "AgentContext | None") -> None:
    """Run missing worker stages directly so final output always contains all agent sections.
    
    ARCHITECTURE NOTES:
    - Current: Sequential pipeline system_analyst → system_architect → frontend_lld + lld + backend_lld + generic_lld
    - Issue: Context accumulation and output explosion due to chaining full reports downstream
    - Optimization: frontend_lld_agent and lld_agent both frontend-oriented (redundant); consider merging
    - Future: Convert to parallel execution: system_architect → [frontend_lld, backend_lld, generic_lld] concurrently
    - Benefit: 70% runtime reduction, eliminate downstream context bloat, independent failure isolation
    """
    state = getattr(context, "state", None)
    if not isinstance(state, dict):
        return

    _, _, AgentResponse, _, _, _, _, _ = _load_adk_components()
    stage_timeout_seconds = int(os.getenv("SUPERVISOR_STAGE_TIMEOUT_SECONDS", "120"))
    if stage_timeout_seconds < 30:
        stage_timeout_seconds = 30
    backend_stage_timeout_seconds = int(
        os.getenv("SUPERVISOR_BACKEND_STAGE_TIMEOUT_SECONDS", str(max(stage_timeout_seconds, 180)))
    )
    if backend_stage_timeout_seconds < 30:
        backend_stage_timeout_seconds = 30

    def _missing(key: str) -> bool:
        return not str(state.get(key, "")).strip()

    def _run_stage(
        func: Any,
        stage_name: str,
        state_key: str,
        *args: Any,
        timeout_seconds: int | None = None,
    ) -> None:
            effective_timeout = timeout_seconds if timeout_seconds is not None else stage_timeout_seconds
            start_ts = time.time()
            
            # Log profiling info for this stage
            input_size = 0
            if args:
                # First positional arg is usually the task/input
                input_size = len(str(args[0]))
            
            logger.info(
                "Starting supervisor stage: %s (timeout=%ss, input_size=%d chars)",
                stage_name,
                effective_timeout,
                input_size
            )
            
            completed, result = _run_with_timeout(func, effective_timeout, *args, context=context)
            elapsed = time.time() - start_ts
            
            if completed and not isinstance(result, Exception):
                output_size = len(str(state.get(state_key, "")))
                logger.info(
                    "Completed supervisor stage: %s in %.3fs (input=%d chars, output=%d chars)",
                    stage_name,
                    elapsed,
                    input_size,
                    output_size
                )
                return

            # Stage timed out or failed
            message = f"[{stage_name} timed out after {effective_timeout}s]"
            if isinstance(result, Exception):
                message = f"[{stage_name} failed: {result}]"
                logger.warning("Supervisor stage %s failed after %.3fs: %s", stage_name, elapsed, result)
            else:
                logger.warning(
                    "Supervisor stage %s timed out after %.3fs (limit %ss, input_size=%d chars)",
                    stage_name,
                    elapsed,
                    effective_timeout,
                    input_size
                )

            if callable(getattr(context, "set_state", None)):
                context.set_state(state_key, message)
                _store_agent_chunks(state_key.replace(".output", ""), message, context)

    def _check_stage_failed(stage_name: str, output: str) -> bool:
        """Check if a stage output indicates failure (error message format)."""
        output_str = str(output or "").strip()
        # Error messages from _run_stage start with "[stage_name"
        if output_str.startswith("[") and ("timed out" in output_str or "failed:" in output_str):
            logger.error("Agent stage failed: %s", output_str)
            if context is not None and callable(getattr(context, "set_state", None)):
                context.set_state("supervisor.stage_failed", True)
                context.set_state("supervisor.failed_stage", stage_name)
                context.set_state("supervisor.failure_reason", output_str)
            return True
        return False

    if _missing("system_analyst.output"):
        _run_stage(SystemAnalystWorker(AgentResponse).run, "system_analyst", "system_analyst.output", user_goal)
    
    if _check_stage_failed("system_analyst", state.get("system_analyst.output", "")):
        return

    analyst_output = str(state.get("system_analyst.output", "")).strip() or user_goal
    if _missing("system_architect.output"):
        _run_stage(
            SystemArchitectWorker(AgentResponse).run,
            "system_architect_agent",
            "system_architect.output",
            analyst_output,
        )
    
    if _check_stage_failed("system_architect_agent", state.get("system_architect.output", "")):
        return

    architect_output = str(state.get("system_architect.output", "")).strip() or analyst_output
    if _missing("frontend_lld.output"):
        # TODO: frontend_lld_agent and lld_agent are both frontend-oriented. 
        # TODO: Consider future optimization: merge them or run frontend/backend/generic LLD agents independently in parallel instead of sequential chaining.
        _run_stage(
            FrontendLLDWorker(AgentResponse).run,
            "frontend_lld_agent",
            "frontend_lld.output",
            architect_output,
        )
    
    if _check_stage_failed("frontend_lld_agent", state.get("frontend_lld.output", "")):
        return

    frontend_output = str(state.get("frontend_lld.output", "")).strip() or architect_output
    lld_task = (
        str(state.get("requirement_doc", "")).strip()
        or str(state.get("system_analyst.output", "")).strip()
        or user_goal
    )
    architect_summary = str(state.get("system_architect.output", ""))[:3000]
    lld_task = f"{lld_task}\n\n---\n\nArchitecture Summary:\n{architect_summary}"

    if _missing("lld.output"):
        # TODO: Possible future optimization: merge frontend_lld_agent and lld_agent since both are frontend-oriented.
        # TODO: Consider running frontend/backend/generic LLD agents independently in parallel instead of sequential chaining.
        _run_stage(
            LLDWorker(AgentResponse).run,
            "lld_agent",
            "lld.output",
            lld_task,
            timeout_seconds=int(os.getenv("SUPERVISOR_LLD_STAGE_TIMEOUT_SECONDS", "180")),
        )
    
    if _check_stage_failed("lld_agent", state.get("lld.output", "")):
        return
    
    _populate_lld_fields_from_output(context)

    lld_output = str(state.get("lld.output", "")).strip() or frontend_output
    
    # Summarize lld_agent output for backend_lld_agent to prevent context explosion
    backend_lld_max_input = int(os.getenv("BACKEND_LLD_MAX_INPUT_CHARS", "8000"))
    lld_output_for_backend = _summarize_for_downstream(
        lld_output, 
        max_chars=backend_lld_max_input, 
        focus="backend"
    )
    
    lld_original_size = len(lld_output)
    lld_summarized_size = len(lld_output_for_backend)
    
    if _missing("backend_lld.output"):
        logger.info(
            "backend_lld_agent preparation: original lld size=%d, summarized size=%d (reduction=%.1f%%)",
            lld_original_size,
            lld_summarized_size,
            100.0 * (1.0 - lld_summarized_size / max(lld_original_size, 1)) if lld_original_size > 0 else 0
        )
        _run_stage(
            BackendLLDWorker(AgentResponse).run,
            "backend_lld_agent",
            "backend_lld.output",
            lld_output_for_backend,
            timeout_seconds=backend_stage_timeout_seconds,
        )
    
    if _check_stage_failed("backend_lld_agent", state.get("backend_lld.output", "")):
        return

    backend_output = str(state.get("backend_lld.output", "")).strip() or lld_output
    
    # Validate backend LLD output relevance
    is_relevant, reason = _is_backend_lld_output_relevant(backend_output, user_goal)
    if not is_relevant:
        logger.warning("Backend LLD output validation failed: %s", reason)
        error_msg = f"Backend LLD output is off-topic. Reason: {reason}"
        logger.error(error_msg)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("supervisor.validation_failed", True)
            context.set_state("supervisor.validation_error", reason)
        return
    
    backend_output_for_generic = backend_output
    generic_lld_max_input = int(os.getenv("GENERIC_LLD_MAX_INPUT_CHARS", "6000"))
    
    # Summarize backend_lld_agent output for generic_lld_agent to prevent further context explosion
    if len(backend_output) > generic_lld_max_input:
        backend_output_for_generic = _summarize_for_downstream(
            backend_output,
            max_chars=generic_lld_max_input,
            focus="generic"
        )
        logger.info(
            "generic_lld_agent preparation: original backend_lld size=%d, summarized size=%d (reduction=%.1f%%)",
            len(backend_output),
            len(backend_output_for_generic),
            100.0 * (1.0 - len(backend_output_for_generic) / max(len(backend_output), 1))
        )
    
    if _missing("generic_lld.output"):
        _run_stage(
            GenericLLDWorker(AgentResponse).run,
            "generic_lld_agent",
            "generic_lld.output",
            backend_output_for_generic,
        )


def build_supervisor_agent():
    (
        SupervisorAgent,
        WorkerSpec,
        AgentResponse,
        create_agent_llm,
        PromptBuilder,
        SupervisorConfig,
        ExecutionMode,
        GeminiConfig,
    ) = _load_adk_components()

    system_worker = SystemAnalystWorker(AgentResponse)
    system_architect_worker = SystemArchitectWorker(AgentResponse)
    frontend_lld_worker = FrontendLLDWorker(AgentResponse)
    lld_worker = LLDWorker(AgentResponse)
    backend_lld_worker = BackendLLDWorker(AgentResponse)
    generic_lld_worker = GenericLLDWorker(AgentResponse)

    # Warm up workers once so request-time execution reuses preloaded modules and agents.
    try:
        prompt_module = _load_module("system_analyst_prompt", SYSTEM_ANALYST_PROMPT_PATH)
        sys.modules["prompt"] = prompt_module
        sys.modules["prompts"] = prompt_module
        analyst_module = _load_module("system_analyst_main", _resolve_system_analyst_entry_path())
        if hasattr(analyst_module, "load_environment"):
            analyst_module.load_environment()
        system_worker._module = analyst_module
        system_worker._agent = analyst_module.build_agent()
        logger.info("Prewarmed system_analyst worker")
    except Exception as exc:
        logger.warning("Failed to prewarm system_analyst worker: %s", exc)

    try:
        architect_module = __import__(
            "system_architect_agent.sysaapp",
            fromlist=["run_system_architect"],
        )
        if hasattr(architect_module, "load_environment"):
            architect_module.load_environment()
        system_architect_worker._module = architect_module
        logger.info("Prewarmed system_architect worker")
    except Exception as exc:
        logger.warning("Failed to prewarm system_architect worker: %s", exc)

    _warmup_worker(
        frontend_lld_worker,
        _load_module,
        "frontend_lld_main",
        _resolve_frontend_lld_entry_path(),
    )

    _warmup_worker(
        generic_lld_worker,
        _load_module,
        "generic_lld_main",
        _resolve_generic_lld_entry_path(),
    )

    prompt_builder = (
        PromptBuilder()
        .add_system(
            "You are a supervisor orchestrating four workers. "
            "You MUST do exactly this sequence: "
            "1) Call system_analyst with the user goal. "
            "2) Pass the system_analyst output to system_architect_agent. "
            "3) Pass only the architecture doc to frontend_lld_agent. "
            "4) Pass only the system_analyst output to lld_agent — do NOT pass frontend LLD output. "
            "5) Pass the lld_agent output to backend_lld_agent. "
            "6) Pass the backend_lld_agent output to generic_lld_agent. "
            "7) Return a combined markdown response with these sections only: "
            "User Goal, System Analyst Output, System Architect Output, Frontend LLD Output, LLD Sections, LLD Architecture Analysis, LLD Final Report, Backend LLD Output, Generic LLD Output. "
            "Do not skip steps and do not invent tool outputs. "
            "If any worker returns an error message, include it verbatim under the corresponding section. "
            "Do not apologize or replace errors with generic text.",
            name="orchestration",
        )
        .add_user("{task}", name="task")
    )

    gemini_config = GeminiConfig(
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GEMINI_PROJECT_ID", "eds-alchemy")),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("GEMINI_LOCATION", "us-central1")),
        agent_model="gemini-2.5-flash-lite",
        validator_model="gemini-2.5-flash-lite",
        max_output_tokens=int(os.getenv("SUPERVISOR_MAX_OUTPUT_TOKENS", "16384")),
        timeout_seconds=int(os.getenv("SUPERVISOR_MODEL_TIMEOUT_SECONDS", "60")),
    )

    return SupervisorAgent(
        workers=[
            WorkerSpec(
                name="system_analyst",
                description="Generates detailed system analysis from a user goal.",
                agent=system_worker,
                task_variable="task",
            ),
            WorkerSpec(
                name="system_architect_agent",
                description="Consumes System Analyst output and returns system architecture output.",
                agent=system_architect_worker,
                task_variable="task",
            ),
            WorkerSpec(
                name="frontend_lld_agent",
                description="Consumes architecture and requirement docs to generate frontend LLD output.",
                agent=frontend_lld_worker,
                task_variable="task",
            ),
            WorkerSpec(
                name="lld_agent",
                description="Consumes Frontend LLD output and returns JSON with sections, architecture_analysis, and final_report.",
                agent=lld_worker,
                task_variable="task",
            ),
            WorkerSpec(
                name="backend_lld_agent",
                description="Consumes LLD output and returns backend-oriented LLD output.",
                agent=backend_lld_worker,
                task_variable="task",
            ),
            WorkerSpec(
                name="generic_lld_agent",
                description="Consumes backend output and returns final generic LLD output.",
                agent=generic_lld_worker,
                task_variable="task",
            ),
        ],
        llm=create_agent_llm(gemini_config),
        prompt_builder=prompt_builder,
        config=SupervisorConfig(
            execution_mode=ExecutionMode.SERIAL,
            enable_validation=False,
            max_iterations=10,
        ),
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    _load_environment()
    logger.info("Starting supervisor pipeline")
    supervisor = build_supervisor_agent()
    pipeline_timeout_seconds = int(os.getenv("SUPERVISOR_PIPELINE_TIMEOUT_SECONDS", "240"))
    if pipeline_timeout_seconds < 120:
        pipeline_timeout_seconds = 120

    user_goal = (
        " ".join(sys.argv[1:]).strip()
        if len(sys.argv) > 1
        else "Create a one page marketing website using NextJS ."
    )

    shared_context = None
    try:
        context_mod = __import__("reusableagents.context", fromlist=["AgentContext"])
        shared_context = context_mod.AgentContext(state={"user_goal": user_goal})
    except Exception:
        shared_context = None

    logger.info("Running supervisor orchestrator")
    completed, run_result = _run_with_timeout(
        supervisor.run,
        pipeline_timeout_seconds,
        task=user_goal,
        context=shared_context,
    )
    if not completed:
        logger.warning(f"Supervisor orchestrator timed out after {pipeline_timeout_seconds}s")
        run_result = None

    output = ""
    if isinstance(run_result, Exception):
        logger.error("Supervisor orchestrator failed: %s", run_result)
    elif run_result is not None:
        output = str(_extract_output_text(run_result)).strip()

    # Ensure all downstream agent outputs exist even if orchestration stopped early.
    _ensure_agent_outputs(user_goal=user_goal, context=shared_context)
    _populate_lld_fields_from_output(shared_context)

    output = _normalize_orchestrator_output(output, user_goal)
    output = _canonicalize_combined_output(output, user_goal=user_goal, context=shared_context)
    if output and not _is_complete_combined_output(output):
        output = _coerce_partial_orchestrator_output(output, user_goal)
        output = _canonicalize_combined_output(output, user_goal=user_goal, context=shared_context)
    agent_report = _render_agent_output_report(shared_context)
    combined_output = output if str(output).strip() else "No output generated."
    final_output = f"{agent_report}\n\n---\n\n## Combined Output\n\n{combined_output}".strip()
    output_file = _write_full_output(final_output)
    _print_chunked_output(final_output)
    if output_file is not None:
        print(f"\nFull output saved to: {output_file}")


if __name__ == "__main__":
    main()
