import json
import sys
from typing import Any


def _load_backend_runner():
    try:
        from lld_backend_agent.lldback import run_backend_lld as backend_runner

        return backend_runner
    except Exception:
        from .lldback import run_backend_lld as backend_runner

        return backend_runner


def run_backend_lld(lld_input: str | None = None, context: Any | None = None) -> str:
    """Delegate backend generation to the real backend LLD runner."""
    backend_runner = _load_backend_runner()
    return backend_runner(lld_input=lld_input, context=context)


def main():
    # Backwards-compatible CLI entrypoint: read stdin and print JSON payload
    try:
        raw = sys.stdin.read()
        payload = {}
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            payload = {"lld_input": raw}

        lld_input = payload.get("lld_input", "")
        # Pass supporting docs through to the backend if provided
        requirement_doc = payload.get("requirement_doc")
        architecture_doc = payload.get("architecture_doc")
        backend_output = run_backend_lld(
            lld_input=lld_input,
            context={
                "requirement_doc": requirement_doc,
                "architecture_doc": architecture_doc,
            },
        )

        # Emit JSON so the supervisor subprocess wrapper can parse it
        print(json.dumps({"backend_lld_output": str(backend_output).strip(), "status": "placeholder"}))

    except Exception as e:
        print(json.dumps({"backend_lld_output": f"Backend LLD stub error: {e}", "status": "error"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
