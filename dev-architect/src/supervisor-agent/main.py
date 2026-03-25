import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

try:
    from .prompts import COMBINED_OUTPUT_TEMPLATE
    from .state import SupervisorState
except ImportError:
    current_dir = Path(__file__).resolve().parent

    prompts_spec = importlib.util.spec_from_file_location(
        "supervisor_agent_prompts", current_dir / "prompts.py"
    )
    if prompts_spec is None or prompts_spec.loader is None:
        raise RuntimeError("Unable to load supervisor prompts module")
    prompts_module = importlib.util.module_from_spec(prompts_spec)
    prompts_spec.loader.exec_module(prompts_module)

    state_spec = importlib.util.spec_from_file_location(
        "supervisor_agent_state", current_dir / "state.py"
    )
    if state_spec is None or state_spec.loader is None:
        raise RuntimeError("Unable to load supervisor state module")
    state_module = importlib.util.module_from_spec(state_spec)
    state_spec.loader.exec_module(state_module)

    COMBINED_OUTPUT_TEMPLATE = prompts_module.COMBINED_OUTPUT_TEMPLATE
    SupervisorState = state_module.SupervisorState


SRC_DIR = Path(__file__).resolve().parents[1]
SYSTEM_ANALYST_DIR = SRC_DIR / "system-analyst-agent"
LLD_DIR = SRC_DIR / "low-level-design-agent"
SYSTEM_ANALYST_MAIN_PATH = SYSTEM_ANALYST_DIR / "main.py"
LLD_APP_PATH = LLD_DIR / "app.py"


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


def run_system_analyst(state: dict[str, str]) -> dict[str, str]:
    prompt_module = _load_module("system_analyst_prompt", SYSTEM_ANALYST_DIR / "prompt.py")
    sys.modules["prompt"] = prompt_module

    system_analyst_module = _load_module("system_analyst_main", SYSTEM_ANALYST_MAIN_PATH)
    if hasattr(system_analyst_module, "load_environment"):
        system_analyst_module.load_environment()

    analyst_agent = system_analyst_module.build_agent()
    result = analyst_agent.run(user_goal=state["user_goal"])
    output = result.output if hasattr(result, "output") else str(result)

    return {"system_analyst_output": str(output).strip()}


def run_lld_agent(state: dict[str, str]) -> dict[str, str]:
    lld_runner = textwrap.dedent(
        """
        import importlib.util
        import json
        import sys

        app_path = sys.argv[1]
        lld_input = sys.stdin.read()

        spec = importlib.util.spec_from_file_location("low_level_design_app", app_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load LLD app from {app_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

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
        [sys.executable, "-c", lld_runner, str(LLD_APP_PATH)],
        input=state["system_analyst_output"],
        capture_output=True,
        text=True,
        check=True,
    )

    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not stdout_lines:
        raise RuntimeError("LLD subprocess produced no output.")

    lld_output = json.loads(stdout_lines[-1])

    return {
        "lld_sections": str(lld_output.get("sections", "")).strip(),
        "lld_architecture_analysis": str(lld_output.get("architecture_analysis", "")).strip(),
        "lld_final_report": str(lld_output.get("final_report", "")).strip(),
    }


def combine_output(state: dict[str, str]) -> dict[str, str]:
    combined = COMBINED_OUTPUT_TEMPLATE.format(
        user_goal=state["user_goal"],
        system_analyst_output=state["system_analyst_output"],
        lld_sections=state["lld_sections"],
        lld_architecture_analysis=state["lld_architecture_analysis"],
        lld_final_report=state["lld_final_report"],
    )

    return {"final_output": combined.strip()}


def build_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("system_analyst", run_system_analyst)
    graph.add_node("low_level_design", run_lld_agent)
    graph.add_node("combine", combine_output)

    graph.add_edge(START, "system_analyst")
    graph.add_edge("system_analyst", "low_level_design")
    graph.add_edge("low_level_design", "combine")
    graph.add_edge("combine", END)

    return graph.compile()


def main() -> None:
    _load_environment()
    app = build_graph()

    user_goal = (
        " ".join(sys.argv[1:]).strip()
        if len(sys.argv) > 1
        else "Design an AI-powered customer support assistant platform."
    )

    initial_state = {
        "user_goal": user_goal,
        "system_analyst_output": "",
        "lld_sections": "",
        "lld_architecture_analysis": "",
        "lld_final_report": "",
        "final_output": "",
    }

    result = app.invoke(initial_state)
    print(result.get("final_output", "No output generated."))


if __name__ == "__main__":
    main()
