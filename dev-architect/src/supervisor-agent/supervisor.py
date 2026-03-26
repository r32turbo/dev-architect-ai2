import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import types
from pathlib import Path
from types import ModuleType
from typing import Any

from dotenv import load_dotenv


SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
ADK_ROOT = SRC_DIR / "agent-adk"
SYSTEM_ANALYST_DIR = SRC_DIR / "system-analyst-agent"
SYSTEM_ANALYST_MAIN_PATH = SYSTEM_ANALYST_DIR / "main.py"
SYSTEM_ANALYST_PROMPT_PATH = SYSTEM_ANALYST_DIR / "prompt.py"

if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))


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
    required_files = ["app.py", "prompts.py", "state.py"]

    env_path = os.getenv("LLD_APP_PATH")
    if env_path:
        candidate = Path(env_path)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        if candidate.is_file():
            parent_dir = candidate.parent
            all_exist = all((parent_dir / f).is_file() for f in required_files)
            if all_exist:
                return candidate

    candidates = [
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
        f"Could not find complete LLD app (needs {', '.join(required_files)}). "
        "Set LLD_APP_PATH to the app.py path of your complete low-level-design-agent, "
        "or the missing files will be loaded from the fb-lld-creatingagent branch."
    )





def _materialize_lld_app_from_branch(branch_name: str) -> Path:
    rel_files = {
        "app.py": "dev-architect/src/low-level-design-agent/app.py",
        "prompts.py": "dev-architect/src/low-level-design-agent/prompts.py",
        "state.py": "dev-architect/src/low-level-design-agent/state.py",
    }

    temp_dir = Path(tempfile.mkdtemp(prefix="lld_from_branch_"))

    for local_name, rel_path in rel_files.items():
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{branch_name}:{rel_path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        content = completed.stdout
        if local_name == "app.py":
            # Normalize import paths to avoid class identity mismatches between
            # reusableagents.* and top-level agents/prompts/config modules.
            content = content.replace("reusableagents.agents.react_agent", "agents.react_agent")
            content = content.replace("reusableagents.agents.validator", "agents.validator")
            content = content.replace("reusableagents.config.settings", "config.settings")
            content = content.replace("reusableagents.prompts.base", "prompts.base")
            content = content.replace("enable_validation=True", "enable_validation=False")
        (temp_dir / local_name).write_text(content, encoding="utf-8")

    return temp_dir / "app.py"


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

            analyst_module = _load_module("system_analyst_main", SYSTEM_ANALYST_MAIN_PATH)
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
            # Always use branch version for subprocess isolation to avoid module collisions.
            # The branch version is guaranteed to have all required files and dependencies.
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

                if not hasattr(module, "graph"):
                    raise RuntimeError("LLD module does not expose graph")

                result = module.graph.invoke({"lld_input": lld_input})
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
    supervisor = build_supervisor_agent()

    user_goal = (
        " ".join(sys.argv[1:]).strip()
        if len(sys.argv) > 1
        else "Create a one page marketing website using NextJS ."
    )

    result = supervisor.run(task=user_goal)
    output = result.output if hasattr(result, "output") else str(result)
    print(output if str(output).strip() else "No output generated.")


if __name__ == "__main__":
    main()
