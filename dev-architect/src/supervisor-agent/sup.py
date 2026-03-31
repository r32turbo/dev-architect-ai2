import importlib.util
import json
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
from typing import Any

from dotenv import load_dotenv


SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
ADK_ROOT = SRC_DIR / "agent-adk"
SYSTEM_ANALYST_DIR = SRC_DIR / "system-analyst-agent"
SYSTEM_ANALYST_PROMPT_PATH = SYSTEM_ANALYST_DIR / "prompt.py"

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
            # Normalize import paths to avoid class identity mismatches between
            # reusableagents.* and top-level agents/prompts/config modules.
            content = content.replace("reusableagents.agents.react_agent", "agents.react_agent")
            content = content.replace("reusableagents.agents.validator", "agents.validator")
            content = content.replace("reusableagents.config.settings", "config.settings")
            content = content.replace("reusableagents.prompts.base", "prompts.base")
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

    supervisor_mod = __import__("agents.supervisor", fromlist=["SupervisorAgent", "WorkerSpec"])
    react_mod = __import__("agents.react_agent", fromlist=["AgentResponse"])
    llm_mod = __import__("llm.gemini", fromlist=["create_agent_llm"])
    prompts_mod = __import__("prompts.base", fromlist=["PromptBuilder"])
    config_mod = __import__(
        "config.settings",
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

    def run(self, task: str):
        if self._agent is None:
            prompt_module = _load_module("system_analyst_prompt", SYSTEM_ANALYST_PROMPT_PATH)
            sys.modules["prompt"] = prompt_module

            analyst_module = _load_module(
                "system_analyst_main", _resolve_system_analyst_entry_path()
            )
            if hasattr(analyst_module, "load_environment"):
                analyst_module.load_environment()
            self._agent = analyst_module.build_agent()

        result = self._agent.run(user_goal=task)
        output = result.output if hasattr(result, "output") else str(result)
        return self._agent_response_type(output=str(output).strip())


class LLDWorker:
    def __init__(self, agent_response_type: Any) -> None:
        self._agent_response_type = agent_response_type

    def run(self, task: str):
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
                lld_input = sys.stdin.read()

                if str(adk_root) not in sys.path:
                    sys.path.insert(0, str(adk_root))

                app_dir = str(app_path.parent)

                if "reusableagents" not in sys.modules:
                    pkg = types.ModuleType("reusableagents")
                    pkg.__path__ = [str(adk_root)]
                    sys.modules["reusableagents"] = pkg

                # Ensure reusableagents.* and top-level modules resolve to identical objects.
                # This prevents PromptBuilder type identity mismatches in branch LLD code.
                agents_mod = importlib.import_module("agents")
                react_mod = importlib.import_module("agents.react_agent")
                validator_mod = importlib.import_module("agents.validator")
                prompts_pkg_mod = importlib.import_module("prompts")
                prompts_base_mod = importlib.import_module("prompts.base")
                config_mod = importlib.import_module("config")
                config_settings_mod = importlib.import_module("config.settings")

                sys.modules["reusableagents.agents"] = agents_mod
                sys.modules["reusableagents.agents.react_agent"] = react_mod
                sys.modules["reusableagents.agents.validator"] = validator_mod
                sys.modules["reusableagents.prompts"] = prompts_pkg_mod
                sys.modules["reusableagents.prompts.base"] = prompts_base_mod
                sys.modules["reusableagents.config"] = config_mod
                sys.modules["reusableagents.config.settings"] = config_settings_mod

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

                if hasattr(module, "graph"):
                    result = module.graph.invoke({"lld_input": lld_input})
                elif hasattr(module, "run_pipeline"):
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

            completed = subprocess.run(
                [sys.executable, "-c", runner, str(ADK_ROOT), str(lld_app_path)],
                input=task,
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

        return self._agent_response_type(output=json.dumps(payload, ensure_ascii=True))


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
        "LLD Sections",
        "LLD Architecture Analysis",
        "LLD Final Report",
    ]
    parsed = _extract_markdown_sections(str(text or ""))
    return all(section in parsed for section in required_sections)


def _normalize_section_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", str(title or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    aliases = {
        "user goal": "User Goal",
        "system analyst output": "System Analyst Output",
        "system analysis output": "System Analyst Output",
        "lld sections": "LLD Sections",
        "sections": "LLD Sections",
        "lld architecture analysis": "LLD Architecture Analysis",
        "architecture analysis": "LLD Architecture Analysis",
        "lld final report": "LLD Final Report",
        "final report": "LLD Final Report",
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
        "LLD Sections",
        "LLD Architecture Analysis",
        "LLD Final Report",
    ]
    recognized_count = sum(1 for name in recognized_sections if name in parsed)
    if recognized_count < 2:
        return raw

    return _render_combined_output(
        user_goal=parsed.get("User Goal", "").strip() or str(user_goal).strip(),
        system_analyst_output=parsed.get("System Analyst Output", "").strip(),
        lld_sections=parsed.get("LLD Sections", "").strip(),
        lld_architecture_analysis=parsed.get("LLD Architecture Analysis", "").strip(),
        lld_final_report=parsed.get("LLD Final Report", "").strip(),
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
    lld_sections = parsed.get("LLD Sections", "").strip()
    lld_arch = parsed.get("LLD Architecture Analysis", "").strip()
    lld_final = parsed.get("LLD Final Report", "").strip()

    # If only one LLD section appears, preserve it as final report fallback.
    if not lld_final and (lld_sections or lld_arch):
        lld_final = lld_arch or lld_sections

    return _render_combined_output(
        user_goal=user_goal_text,
        system_analyst_output=system_text,
        lld_sections=lld_sections,
        lld_architecture_analysis=lld_arch,
        lld_final_report=lld_final,
    )


def _render_combined_output(
    user_goal: str,
    system_analyst_output: str,
    lld_sections: str,
    lld_architecture_analysis: str,
    lld_final_report: str,
) -> str:
    return (
        "## User Goal\n\n"
        f"{user_goal}\n\n"
        "## System Analyst Output\n\n"
        f"{system_analyst_output}\n\n"
        "## LLD Sections\n\n"
        f"{lld_sections}\n\n"
        "## LLD Architecture Analysis\n\n"
        f"{lld_architecture_analysis}\n\n"
        "## LLD Final Report\n\n"
        f"{lld_final_report}"
    ).strip()


def _run_direct_fallback_pipeline(user_goal: str) -> str:
    (
        _SupervisorAgent,
        _WorkerSpec,
        AgentResponse,
        _create_agent_llm,
        _PromptBuilder,
        _SupervisorConfig,
        _ExecutionMode,
        _GeminiConfig,
    ) = _load_adk_components()

    system_worker = SystemAnalystWorker(AgentResponse)
    lld_worker = LLDWorker(AgentResponse)

    analyst_result = system_worker.run(user_goal)
    analyst_text = str(_extract_output_text(analyst_result)).strip()

    lld_result = lld_worker.run(analyst_text)
    lld_raw = str(_extract_output_text(lld_result)).strip()

    try:
        payload = json.loads(lld_raw) if lld_raw else {}
    except json.JSONDecodeError:
        payload = {
            "sections": "",
            "architecture_analysis": "",
            "final_report": lld_raw,
        }

    return _render_combined_output(
        user_goal=user_goal,
        system_analyst_output=analyst_text,
        lld_sections=str(payload.get("sections", "")).strip(),
        lld_architecture_analysis=str(payload.get("architecture_analysis", "")).strip(),
        lld_final_report=str(payload.get("final_report", "")).strip(),
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
    lld_worker = LLDWorker(AgentResponse)

    prompt_builder = (
        PromptBuilder()
        .add_system(
            "You are a supervisor orchestrating two workers. "
            "You MUST do exactly this sequence: "
            "1) Call system_analyst with the user goal. "
            "2) Pass the FULL system_analyst output as the task input to lld_agent. "
            "3) Return a combined markdown response with these sections only: "
            "User Goal, System Analyst Output, LLD Sections, LLD Architecture Analysis, LLD Final Report. "
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
                name="lld_agent",
                description="Consumes System Analyst output and returns JSON with sections, architecture_analysis, and final_report.",
                agent=lld_worker,
                task_variable="task",
            ),
        ],
        llm=create_agent_llm(gemini_config),
        prompt_builder=prompt_builder,
        config=SupervisorConfig(
            execution_mode=ExecutionMode.SERIAL,
            enable_validation=False,
            max_iterations=8,
        ),
    )


def main() -> None:
    _load_environment()
    print("Starting supervisor pipeline...", flush=True)
    supervisor = build_supervisor_agent()
    pipeline_timeout_seconds = int(os.getenv("SUPERVISOR_PIPELINE_TIMEOUT_SECONDS", "180"))

    user_goal = (
        " ".join(sys.argv[1:]).strip()
        if len(sys.argv) > 1
        else "Create a one page marketing website using NextJS ."
    )

    print("Running supervisor orchestrator...", flush=True)
    completed, run_result = _run_with_timeout(
        supervisor.run,
        pipeline_timeout_seconds,
        task=user_goal,
    )
    if not completed:
        print(
            f"Supervisor orchestrator timed out after {pipeline_timeout_seconds}s; "
            "switching to direct fallback pipeline.",
            flush=True,
        )
        run_result = None

    output = ""
    if isinstance(run_result, Exception):
        print(f"Supervisor orchestrator failed: {run_result}", flush=True)
    elif run_result is not None:
        output = str(_extract_output_text(run_result)).strip()
    output = _normalize_orchestrator_output(output, user_goal)
    if output and not _is_complete_combined_output(output):
        output = _coerce_partial_orchestrator_output(output, user_goal)

    # Some model/tooling paths occasionally return an empty output payload.
    # Retry once before surfacing a no-output message.
    if not output:
        print("Retrying supervisor orchestrator once...", flush=True)
        retry_completed, retry_result = _run_with_timeout(
            supervisor.run,
            pipeline_timeout_seconds,
            task=user_goal,
        )
        if not retry_completed:
            print(
                f"Supervisor retry timed out after {pipeline_timeout_seconds}s; "
                "using direct fallback pipeline.",
                flush=True,
            )
        elif isinstance(retry_result, Exception):
            print(f"Supervisor retry failed: {retry_result}", flush=True)
        else:
            output = str(_extract_output_text(retry_result)).strip()
        output = _normalize_orchestrator_output(output, user_goal)
        if output and not _is_complete_combined_output(output):
            output = _coerce_partial_orchestrator_output(output, user_goal)

    # The supervisor may occasionally stop at an intermediate planning message.
    # Fallback to a deterministic two-step execution so callers always receive
    # the full combined response structure.
    if not _is_complete_combined_output(output):
        print("Running direct fallback pipeline...", flush=True)
        fallback_completed, fallback_result = _run_with_timeout(
            _run_direct_fallback_pipeline,
            pipeline_timeout_seconds,
            user_goal,
        )
        if not fallback_completed:
            output = (
                "Fallback pipeline timed out. "
                "Increase SUPERVISOR_PIPELINE_TIMEOUT_SECONDS and try again."
            )
        elif isinstance(fallback_result, Exception):
            output = f"Fallback pipeline failed: {fallback_result}"
        else:
            output = str(fallback_result).strip()

    print(output if str(output).strip() else "No output generated.")


if __name__ == "__main__":
    main()
