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
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore[reportMissingImports]


SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent
ADK_ROOT = SRC_DIR / "agent-adk"
SYSTEM_ANALYST_DIR = SRC_DIR / "system-analyst-agent"
SYSTEM_ANALYST_PROMPT_PATH = SYSTEM_ANALYST_DIR / "prompt.py"
SYSTEM_ARCHITECT_DIR = SRC_DIR / "system_architect_agent"
FRONTEND_LLD_DIR = SRC_DIR / "frontend-lld-agent"
LLD_BACKEND_DIR = SRC_DIR / "lld_backend_agent"
GENERIC_LLD_DIR = SRC_DIR / "generic-lld-agent"

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

logger = logging.getLogger(__name__)


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
    preferred = SYSTEM_ANALYST_DIR / "analyst_agent.py"
    legacy = SYSTEM_ANALYST_DIR / "main.py"
    if preferred.is_file():
        return preferred
    if legacy.is_file():
        return legacy
    raise FileNotFoundError(
        f"System analyst entry file not found. Expected one of: {preferred}, {legacy}"
    )


def _resolve_system_architect_entry_path() -> Path:
    preferred = SYSTEM_ARCHITECT_DIR / "sysaapp.py"
    if preferred.is_file():
        return preferred
    raise FileNotFoundError(f"System architect entry file not found. Expected: {preferred}")


def _resolve_frontend_lld_entry_path() -> Path:
    preferred = FRONTEND_LLD_DIR / "frontend_graph.py"
    if preferred.is_file():
        return preferred
    raise FileNotFoundError(f"Frontend LLD entry file not found. Expected: {preferred}")


def _resolve_lld_backend_entry_path() -> Path:
    preferred = LLD_BACKEND_DIR / "lldbapp.py"
    if preferred.is_file():
        return preferred
    raise FileNotFoundError(f"Backend LLD entry file not found. Expected: {preferred}")


def _resolve_generic_lld_entry_path() -> Path:
    preferred = GENERIC_LLD_DIR / "generic_graph.py"
    if preferred.is_file():
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

    def run(self, task: str, context: "AgentContext | None" = None):
        # Avoid long MLflow retries (localhost:5000) during supervisor runs.
        # Users can still explicitly enable this by setting value to 1.
        os.environ.setdefault("SYSTEM_ANALYST_OBSERVABILITY_ENABLED", "0")
        if context is not None and callable(getattr(context, "record", None)):
            context.record(
                agent_name="system_analyst_worker",
                event="started",
                detail=str(task)[:160],
            )
        if self._agent is None:
            prompt_module = _load_module("system_analyst_prompt", SYSTEM_ANALYST_PROMPT_PATH)
            sys.modules["prompt"] = prompt_module

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
                context.set_state("user_goal", str(task).strip())
            try:
                output = run_in_module(context=context)
            except TypeError as exc:
                if "required positional argument" not in str(exc):
                    raise
                output = run_in_module(user_goal=task, context=context)
        else:
            goal = str(task).strip()
            if isinstance(getattr(context, "state", None), dict):
                goal = str(context.state.get("user_goal", goal)).strip() or goal
            run_kwargs = {"user_goal": goal}
            if context is not None:
                run_kwargs["context"] = context
            result = self._agent.run(**run_kwargs)
            output = result.output if hasattr(result, "output") else str(result)
        _store_agent_chunks("system_analyst", str(output).strip(), context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("system_analyst.output", str(output).strip())
            context.record(agent_name="system_analyst_worker", event="completed")
        return self._agent_response_type(output=str(output).strip())


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
                context_state = dict(context.state)
            subprocess_input = json.dumps(
                {
                    "lld_input": task,
                    "context_state": context_state,
                },
                ensure_ascii=True,
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
            self._module = _load_module(
                "system_architect_main", _resolve_system_architect_entry_path()
            )
            if hasattr(self._module, "load_environment"):
                self._module.load_environment()

        run_in_module = getattr(self._module, "run_system_architect", None)
        if not callable(run_in_module):
            raise RuntimeError("System architect module does not expose run_system_architect")

        output = str(run_in_module(input_document=task, context=context)).strip()
        _store_agent_chunks("system_architect", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("system_architect.output", output)
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
        requirement_doc = str(state.get("system_analyst.output", "")).strip() or str(task).strip()
        architecture_doc = str(state.get("system_architect.output", "")).strip() or str(task).strip()

        result = self._agent.run(
            context=context,
            user_input=user_input,
            requirement_doc=requirement_doc,
            architecture_doc=architecture_doc,
        )
        output = result.output if hasattr(result, "output") else str(result)
        output = str(output).strip()

        _store_agent_chunks("frontend_lld", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("frontend_lld.output", output)
            context.record(agent_name="frontend_lld_worker", event="completed")
        return self._agent_response_type(output=output)


class BackendLLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type

    def run(self, task: str, context: "AgentContext | None" = None):
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

                payload = {}
                raw_input = sys.stdin.read()
                try:
                    payload = json.loads(raw_input) if raw_input.strip() else {}
                except json.JSONDecodeError:
                    payload = {"lld_input": raw_input}

                lld_input = str(payload.get("lld_input", ""))
                context_state = payload.get("context_state", {})

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
                context_state = dict(context.state)

            lld_input = str(task).strip()
            if isinstance(getattr(context, "state", None), dict):
                lld_input = str(context.state.get("lld.final_report", lld_input)).strip() or lld_input

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
            context.record(agent_name="backend_lld_worker", event="completed")
        return self._agent_response_type(output=output)


class GenericLLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type

    def run(self, task: str, context: "AgentContext | None" = None):
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

            payload = {
                "user_input": str(state.get("user_goal", task)).strip() or str(task).strip(),
                "requirement_doc": str(state.get("system_analyst.output", task)).strip() or str(task).strip(),
                "architecture_doc": str(state.get("backend_lld.output", "")).strip()
                or str(state.get("lld.final_report", "")).strip()
                or str(task).strip(),
                "context_state": dict(state),
            }

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

        _store_agent_chunks("generic_lld", output, context)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state("generic_lld.output", output)
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
    parsed = _extract_markdown_sections(str(text or ""))
    state = getattr(context, "state", None)
    state = state if isinstance(state, dict) else {}

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
        str(parsed.get("architecture_analysis", "")).strip(),
    )
    context.set_state("lld.final_report", str(parsed.get("final_report", "")).strip())


def _ensure_agent_outputs(user_goal: str, context: "AgentContext | None") -> None:
    """Run missing worker stages directly so final output always contains all agent sections."""
    state = getattr(context, "state", None)
    if not isinstance(state, dict):
        return

    _, _, AgentResponse, _, _, _, _, _ = _load_adk_components()
    stage_timeout_seconds = int(os.getenv("SUPERVISOR_STAGE_TIMEOUT_SECONDS", "240"))
    if stage_timeout_seconds < 30:
        stage_timeout_seconds = 30

    def _missing(key: str) -> bool:
        return not str(state.get(key, "")).strip()

    def _run_stage(func: Any, stage_name: str, state_key: str, *args: Any) -> None:
        completed, result = _run_with_timeout(func, stage_timeout_seconds, *args, context=context)
        if completed and not isinstance(result, Exception):
            return
        message = f"[{stage_name} timed out after {stage_timeout_seconds}s]"
        if isinstance(result, Exception):
            message = f"[{stage_name} failed: {result}]"
        if callable(getattr(context, "set_state", None)):
            context.set_state(state_key, message)
            _store_agent_chunks(state_key.replace(".output", ""), message, context)

    if _missing("system_analyst.output"):
        _run_stage(SystemAnalystWorker(AgentResponse).run, "system_analyst", "system_analyst.output", user_goal)

    analyst_output = str(state.get("system_analyst.output", "")).strip() or user_goal
    if _missing("system_architect.output"):
        _run_stage(
            SystemArchitectWorker(AgentResponse).run,
            "system_architect_agent",
            "system_architect.output",
            analyst_output,
        )

    architect_output = str(state.get("system_architect.output", "")).strip() or analyst_output
    if _missing("frontend_lld.output"):
        _run_stage(
            FrontendLLDWorker(AgentResponse).run,
            "frontend_lld_agent",
            "frontend_lld.output",
            architect_output,
        )

    frontend_output = str(state.get("frontend_lld.output", "")).strip() or architect_output
    if _missing("lld.output"):
        _run_stage(LLDWorker(AgentResponse).run, "lld_agent", "lld.output", frontend_output)
    _populate_lld_fields_from_output(context)

    lld_final_report = str(state.get("lld.final_report", "")).strip() or frontend_output
    if _missing("backend_lld.output"):
        _run_stage(
            BackendLLDWorker(AgentResponse).run,
            "backend_lld_agent",
            "backend_lld.output",
            lld_final_report,
        )

    backend_output = str(state.get("backend_lld.output", "")).strip() or lld_final_report
    if _missing("generic_lld.output"):
        _run_stage(
            GenericLLDWorker(AgentResponse).run,
            "generic_lld_agent",
            "generic_lld.output",
            backend_output,
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

    prompt_builder = (
        PromptBuilder()
        .add_system(
            "You are a supervisor orchestrating four workers. "
            "You MUST do exactly this sequence: "
            "1) Call system_analyst with the user goal. "
            "2) Pass the FULL system_analyst output as the task input to system_architect_agent. "
            "3) Pass the FULL system_architect_agent output as the task input to frontend_lld_agent. "
            "4) Pass the FULL frontend_lld_agent output as the task input to lld_agent. "
            "5) Pass the FULL lld_agent output as the task input to backend_lld_agent. "
            "6) Pass the FULL backend_lld_agent output as the task input to generic_lld_agent. "
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
        timeout_seconds=int(os.getenv("SUPERVISOR_MODEL_TIMEOUT_SECONDS", "120")),
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
    pipeline_timeout_seconds = int(os.getenv("SUPERVISOR_PIPELINE_TIMEOUT_SECONDS", "900"))
    if pipeline_timeout_seconds < 300:
        pipeline_timeout_seconds = 300

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
