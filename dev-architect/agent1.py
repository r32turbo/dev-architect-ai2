import os
from typing import TypedDict, List, Union
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from pathlib import Path

# Load .env from the script's directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get API key and validate
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError(f"GROQ_API_KEY not found. Checked .env at: {env_path}")

# Initialize Groq model
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=api_key
)


# Agent State
class AgentState(TypedDict):
    messages: List[Union[HumanMessage, AIMessage]]
    persona: str
    context: str
    task: str
    input_data: str
    constraints: str


def build_prompt(state: AgentState) -> str:
    """Create structured prompt"""

    prompt = f"""
Persona:
{state['persona']}

Context:
{state['context']}

Task:
{state['task']}

Input Data:
{state['input_data']}

Constraints:
{state['constraints']}

User Query:
{state['messages'][-1].content}
"""

    return prompt


def process(state: AgentState) -> AgentState:
    """LangGraph node"""

    prompt = build_prompt(state)

    response = llm.invoke(prompt)

    state["messages"].append(AIMessage(content=response.content))

    return state


# Create graph
graph = StateGraph(AgentState)

graph.add_node("process", process)

graph.add_edge(START, "process")
graph.add_edge("process", END)

agent = graph.compile()


# CLI runner
if __name__ == "__main__":

    conversation_history = []

    user_input = input("Enter your message: ")

    while user_input.lower() != "exit":

        conversation_history.append(HumanMessage(content=user_input))

        result = agent.invoke({
            "messages": conversation_history,
            "persona": "You are an AI assistant specialized in prompt engineering.",
            "context": "The user is learning prompt structures.",
            "task": "Analyze the user query and provide a structured explanation.",
            "input_data": user_input,
            "constraints": "Respond clearly and professionally."
        })

        conversation_history = result["messages"]

        print("AI:", conversation_history[-1].content)

        user_input = input("Enter your message: ")