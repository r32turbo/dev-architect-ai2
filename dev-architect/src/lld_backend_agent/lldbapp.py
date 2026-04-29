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
        if input_text:
            output = (
                "Backend LLD placeholder: received input.\n"
                "This is a minimal stub implementation. Replace with real backend LLD.\n\n"
                f"Received input:\n{input_text}\n"
            )
        else:
            output = (
                "Backend LLD placeholder: no input provided.\n"
                "Replace this stub with the real lld_backend agent implementation."
            )

        return output

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
        backend_output = run_backend_lld(lld_input=lld_input)

        # Emit JSON so the supervisor subprocess wrapper can parse it
        print(json.dumps({"backend_lld_output": str(backend_output).strip(), "status": "placeholder"}))

    except Exception as e:
        print(json.dumps({"backend_lld_output": f"Backend LLD stub error: {e}", "status": "error"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
