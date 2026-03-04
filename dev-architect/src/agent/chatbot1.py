import os

# when executing the script directly from the workspace root the `src` folder
# may not be on sys.path, causing imports like `import agent` to fail.  insert
# it automatically so the module can be run with `python src/agent/chatbot1.py`.
import sys
from pathlib import Path
project_root = Path(__file__).parents[2]
src_folder = project_root / "src"
if str(src_folder) not in sys.path:
    sys.path.insert(0, str(src_folder))

from typing import TypedDict, List, Union

# helper for imports that can auto-install missing packages
import importlib, subprocess

def ensure_import(module_name: str, package: str | None = None):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pkg = package or module_name
        print(f"Package '{pkg}' not found; attempting to install...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        return importlib.import_module(module_name)

# FastAPI is required for the HTTP API; uvicorn is used when running as script
FastAPI = ensure_import("fastapi").FastAPI
from pydantic import BaseModel
from threading import Lock
from typing import Optional

try:
    uvicorn = ensure_import("uvicorn")
except Exception:  # pragma: no cover
    uvicorn = None  # okay if we can't auto-install

# external libraries used by the agent; attempt to auto-install them if
# they're missing, then retry the import.  This makes the script easier to
# kick off from a clean environment.
def _install_agent_deps():
    deps = [
        "langchain-core",
        "langgraph",
        "langchain-groq",
        "python-dotenv",
    ]
    print("Agent dependencies missing; installing:", deps)
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + deps)

try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langgraph.graph import StateGraph, START, END
    from langchain_groq import ChatGroq
    from dotenv import load_dotenv
except ImportError as e:  # pragma: no cover
    _install_agent_deps()
    # retry imports after installation
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langgraph.graph import StateGraph, START, END
    from langchain_groq import ChatGroq
    from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# -----------------------------
# Initialize Groq LLM
# -----------------------------
llm = ChatGroq(
    model="llama3-8b-8192",
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# -----------------------------
# Define Agent State
# -----------------------------
class AgentState(TypedDict):
    messages: List[Union[HumanMessage, AIMessage, SystemMessage]]

# -----------------------------
# System Prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a helpful AI assistant.
- Answer clearly.
- Keep responses structured.
- If coding, explain step-by-step.
"""

# -----------------------------
# Processing Node
# -----------------------------
def process(state: AgentState) -> AgentState:
    response = llm.invoke(state["messages"])
    state["messages"].append(AIMessage(content=response.content))
    return state

# -----------------------------
# Build LangGraph
# -----------------------------
graph = StateGraph(AgentState)
graph.add_node("process", process)
graph.add_edge(START, "process")
graph.add_edge("process", END)

agent = graph.compile()

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI(title="Groq AI Agent")

# Store conversation history (in-memory)
# shared state (in-memory)
conversation_history: List[Union[HumanMessage, AIMessage, SystemMessage]] = [
    SystemMessage(content=SYSTEM_PROMPT)
]
# lock to protect conversation_history during concurrent requests
_history_lock = Lock()

# Request Model
class ChatRequest(BaseModel):
    message: str

# -----------------------------
# Chat Endpoint
# -----------------------------
@app.post("/chat")
async def chat(request: ChatRequest):
    global conversation_history

    # perform update under lock so concurrent hits work
    with _history_lock:
        # Add user message
        conversation_history.append(HumanMessage(content=request.message))

        # Invoke agent and update state
        result = agent.invoke({"messages": conversation_history})
        conversation_history = result["messages"]
        ai_response = conversation_history[-1].content

        # Append to log instead of overwriting
        with open("logging.txt", "a", encoding="utf-8") as file:
            file.write("Conversation Log\n")
            for msg in conversation_history:
                if isinstance(msg, HumanMessage):
                    file.write(f"You: {msg.content}\n")
                elif isinstance(msg, AIMessage):
                    file.write(f"AI: {msg.content}\n")
            file.write("End of Log\n\n")

    return {"response": ai_response}


# utility endpoints ----------------------------------------------------------
@app.post("/reset")
def reset_conversation():
    """Reset the in-memory conversation history back to just the system prompt."""
    global conversation_history
    with _history_lock:
        conversation_history = [SystemMessage(content=SYSTEM_PROMPT)]
    return {"status": "reset"}


if __name__ == "__main__":
    # start the app with uvicorn for local testing
    uvicorn.run("agent.chatbot1:app", host="0.0.0.0", port=8000, reload=True)
