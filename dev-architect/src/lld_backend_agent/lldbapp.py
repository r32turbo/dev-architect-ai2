import json
import sys
from typing import Any


def run_backend_lld(lld_input: str | None = None, context: Any | None = None) -> str:
    """
    Minimal runtime API expected by the supervisor.
    Returns a simple placeholder string describing that the backend LLD
    is not fully implemented. Includes the provided `lld_input` when available.
    """
    try:
        input_text = (str(lld_input) or "").strip()

        # Allow context to be either an AgentContext-like object or a plain dict
        requirement_doc = None
        architecture_doc = None
        try:
            if context is not None:
                # If it's a dict-like mapping
                if isinstance(context, dict):
                    requirement_doc = context.get("requirement_doc")
                    architecture_doc = context.get("architecture_doc")
                else:
                    # Fallback: try attribute access (AgentContext)
                    requirement_doc = getattr(context, "requirement_doc", None)
                    architecture_doc = getattr(context, "architecture_doc", None)
        except Exception:
            requirement_doc = None
            architecture_doc = None

        parts = []
        parts.append("Backend LLD placeholder: received input." if input_text else "Backend LLD placeholder: no input provided.")
        parts.append("This is a minimal stub implementation. Replace with real backend LLD.")

        if input_text:
            parts.append("Received input:")
            parts.append(input_text)

        if requirement_doc:
            parts.append("\nRequirement doc (provided to backend):")
            parts.append(str(requirement_doc))

        if architecture_doc:
            parts.append("\nArchitecture doc (provided to backend):")
            parts.append(str(architecture_doc))

        return "\n".join(parts)

    except Exception as e:
        return f"Backend LLD stub error: {e}"


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
        backend_output = run_backend_lld(lld_input=lld_input, context={
            "requirement_doc": requirement_doc,
            "architecture_doc": architecture_doc,
        })

        # Emit JSON so the supervisor subprocess wrapper can parse it
        print(json.dumps({"backend_lld_output": str(backend_output).strip(), "status": "placeholder"}))

    except Exception as e:
        print(json.dumps({"backend_lld_output": f"Backend LLD stub error: {e}", "status": "error"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
