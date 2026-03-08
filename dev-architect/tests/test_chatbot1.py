from fastapi.testclient import TestClient
import pytest

from src.agent import chatbot1
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


@pytest.fixture(autouse=True)
def reset_history():
    # ensure conversation history is clean before each test
    chatbot1.conversation_history = [SystemMessage(content=chatbot1.SYSTEM_PROMPT)]
    yield


class DummyAgent:
    def __init__(self, response_text="ok"):
        self.response_text = response_text

    def invoke(self, state):
        # simulate AI reply by appending an AIMessage
        messages = state["messages"].copy()
        messages.append(AIMessage(content=self.response_text))
        return {"messages": messages}


def test_app_exists_and_callable():
    assert chatbot1.app is not None
    assert callable(chatbot1.app)


def test_chat_returns_expected(monkeypatch):
    # replace the compiled graph with a dummy that returns a predictable reply
    monkeypatch.setattr(chatbot1, "agent", DummyAgent("reply"))
    client = TestClient(chatbot1.app)
    resp = client.post("/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "reply"


def test_conversation_history_updates(monkeypatch):
    monkeypatch.setattr(chatbot1, "agent", DummyAgent("foo"))
    client = TestClient(chatbot1.app)
    client.post("/chat", json={"message": "world"})
    # last element in history should be AI reply
    assert isinstance(chatbot1.conversation_history[-1], AIMessage)
    assert chatbot1.conversation_history[-1].content == "foo"


def test_reset_endpoint():
    # push a message into history
    chatbot1.conversation_history.append(HumanMessage(content="boo"))
    client = TestClient(chatbot1.app)
    res = client.post("/reset")
    assert res.status_code == 200
    assert chatbot1.conversation_history == [SystemMessage(content=chatbot1.SYSTEM_PROMPT)]
