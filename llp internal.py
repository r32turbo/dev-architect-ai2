import os
from pathlib import Path
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

# State Definition

class State(TypedDict):
    question: str
    supervisor_prompt: str
    draft_answer: str
    final_answer: str
    feedback: str
    status: str
    iteration: int


# 2. Load Environment


env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=groq_api_key
)



# 3. Supervisor Node


def supervisor_node(state: State):
    print("\n Supervisor")

    feedback = state.get("feedback", "")

    return {
        "supervisor_prompt": (
            "Answer accurately, concisely, and avoid hallucination. "
            "Fix issues based on feedback:\n" + feedback
        )
    }


# ----------------------------
# 4. ReAct Agent Node
# ----------------------------

def react_agent_node(state: State):
    print("\n ReAct Agent")

    question = state["question"]
    supervisor_prompt = state.get("supervisor_prompt", "")
    prev_answer = state.get("draft_answer", "")

    prompt = f"""
You are a ReAct AI agent.

Follow:
Thought → Answer

Rules:
- Improve previous answer
- Use supervisor instructions
- Be concise and correct

Supervisor Instructions:
{supervisor_prompt}

Question:
{question}

Previous Answer:
{prev_answer}
"""

    response = llm.invoke([
        SystemMessage(content="You are a reasoning AI."),
        HumanMessage(content=prompt)
    ])

    return {"draft_answer": response.content.strip()}


# ----------------------------
# 5. Evaluator Node
# ----------------------------

def evaluator_node(state: State):
    print("\n Evaluator")

    question = state["question"]
    answer = state["draft_answer"]
    iteration = state.get("iteration", 0) + 1

    prompt = f"""
Evaluate the answer.

Return STRICT format:

Status: done OR improve
Feedback: reason

Criteria:
- Correctness
- Completeness
- Clarity
- No hallucination

Question:
{question}

Answer:
{answer}
"""

    response = llm.invoke([
        SystemMessage(content="You are a strict evaluator."),
        HumanMessage(content=prompt)
    ])

    output = response.content.strip()
    print(output)

    status = "improve"

    if "status: done" in output.lower():
        status = "done"

    return {
        "status": status,
        "feedback": output,
        "iteration": iteration
    }


# ----------------------------
# 6. Summarizer Node
# ----------------------------

def summarizer_node(state: State):
    print("\n moving to  Summarizer")

    question = state["question"]
    draft = state["draft_answer"]

    prompt = """
Create final structured answer:

- Direct Answer
- Key Points
- Notes (if any)
"""

    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"Question: {question}\nAnswer: {draft}")
    ])

    return {"final_answer": response.content}



# 7. Router (Loop Control)


MAX_ITERATIONS = 3

def route_decision(state: State):
    iteration = state.get("iteration", 0)

    #  HARD STOP
    if iteration >= MAX_ITERATIONS:
        print(f"\n Max iterations reached ({iteration}). Stopping loop.")
        return "summarizer"

    if state["status"] == "done":
        print("\nAnswer is good. Moving to summarizer.")
        return "summarizer"
    else:
        print("\n Answer needs improvement. Looping back.")
        return "supervisor"


# ----------------------------
# 8. Build Graph
# ----------------------------

builder = StateGraph(State)

builder.add_node("supervisor", supervisor_node)
builder.add_node("agent", react_agent_node)
builder.add_node("evaluator", evaluator_node)
builder.add_node("summarizer", summarizer_node)

builder.add_edge(START, "supervisor")
builder.add_edge("supervisor", "agent")
builder.add_edge("agent", "evaluator")

builder.add_conditional_edges(
    "evaluator",
    route_decision,
    {
        "summarizer": "summarizer",
        "supervisor": "supervisor"
    }
)

builder.add_edge("summarizer", END)

graph = builder.compile()



# 9. Run

result = graph.invoke({
    "question": "AI ",
    "supervisor_prompt": "",
    "draft_answer": "",
    "final_answer": "",
    "feedback": "",
    "status": "",
    "iteration": 0
})

print("\n================ FINAL OUTPUT ================\n")
print(result.get("final_answer", "No answer generated"))