import os
from pathlib import Path
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END


# ----------------------------
# 1. State Definition
# ----------------------------

class State(TypedDict):
    question: str
    supervisor_prompt: str
    research_data: str
    final_answer: str
    feedback: str
    iteration: int


# ----------------------------
# 2. Load Environment
# ----------------------------

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found")

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=groq_api_key)


# ----------------------------
# 3. ReAct Research Agent (NO TOOLS)
# ----------------------------

def research_node(state: State):
    print(f"\n🔍 Research Agent (ReAct) - Iteration {state.get('iteration', 0)}")

    question = state["question"]
    supervisor_prompt = state["supervisor_prompt"]

    max_steps = 3
    scratchpad = ""

    for step in range(max_steps):

        react_prompt = f"""
You are a ReAct-style research agent.

Follow STRICT format:

Thought: reasoning
Action: none
Observation: reasoning result
(repeat if needed)

When done:
Final Answer: bullet point research notes

IMPORTANT:
- No external tools available
- Use only your knowledge
- Keep it concise and relevant

Supervisor Instructions:
{supervisor_prompt}

Question:
{question}

Previous steps:
{scratchpad}
"""

        response = llm.invoke([
            SystemMessage(content="You are a reasoning agent."),
            HumanMessage(content=react_prompt)
        ])

        output = response.content.strip()
        print(f"\nStep {step+1} Output:\n{output}")

        scratchpad += "\n" + output

        # Stop if final answer found
        if "Final Answer:" in output:
            final = output.split("Final Answer:")[-1].strip()
            return {"research_data": final}

    return {"research_data": scratchpad}


# ----------------------------
# 4. Summarizer Agent
# ----------------------------

def summarize_node(state: State):
    print("\n📝 Summarizer Agent")

    prompt = (
        "Give a clear final answer.\n"
        "Start with a direct answer, then add Key Points.\n"
        "Mention uncertainty if any."
    )

    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"""
Question:
{state['question']}

Research:
{state['research_data']}
""")
    ])

    return {"final_answer": response.content}


# ----------------------------
# 5. Supervisor Agent
# ----------------------------

def supervisor_node(state: State):
    print("\n🧠 Supervisor Agent")

    return {
        "supervisor_prompt": (
            "Ensure accurate, concise answers. Avoid hallucination. "
            "Focus only on relevant information."
        )
    }


# ----------------------------
# 6. Feedback Agent
# ----------------------------

def feedback_node(state: State):
    print("\n🔍 Feedback Agent")

    iteration = state.get("iteration", 0)

    prompt = (
        "You are a strict evaluator.\n"
        "Return ONLY 'yes' or 'no'.\n"
        "Does the answer fully solve the question?"
    )

    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"""
Question:
{state['question']}

Answer:
{state['final_answer']}
""")
    ])

    feedback = response.content.strip().lower()
    decision = "yes" if "yes" in feedback else "no"

    print("Feedback:", decision)

    return {
        "feedback": decision,
        "iteration": iteration + 1
    }


# ----------------------------
# 7. Feedback Router
# ----------------------------

def feedback_router(state: State):

    if state["feedback"] == "yes":
        print("✅ Final Answer Accepted")
        return END

    if state["iteration"] >= 3:
        print("⚠️ Max iterations reached")
        return END

    print("🔁 Looping back to Research...\n")
    return "research_agent"


# ----------------------------
# 8. Build Graph
# ----------------------------

builder = StateGraph(State)

builder.add_node("supervisor", supervisor_node)
builder.add_node("research_agent", research_node)
builder.add_node("summary_agent", summarize_node)
builder.add_node("feedback_agent", feedback_node)

builder.add_edge(START, "supervisor")
builder.add_edge("supervisor", "research_agent")
builder.add_edge("research_agent", "summary_agent")
builder.add_edge("summary_agent", "feedback_agent")

builder.add_conditional_edges(
    "feedback_agent",
    feedback_router,
    {
        "research_agent": "research_agent",
        END: END
    }
)

graph = builder.compile()


# ----------------------------
# 9. Run the System
# ----------------------------

result = graph.invoke({
    "question": "what is the current date and weather in kochi",
    "supervisor_prompt": "",
    "research_data": "",
    "final_answer": "",
    "feedback": "",
    "iteration": 0
})

print("\n================ FINAL OUTPUT ================\n")
print(result.get("final_answer", "No answer generated"))