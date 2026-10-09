import sys
from pathlib import Path

# The gateway package lives under services/gateway, while CI runs pytest from
# the repository root. Add that service root before importing its app package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "gateway"))

import pytest
from pydantic import ValidationError

from app.api.chat import ChatIn


def test_chat_accepts_user_turn():
    request = ChatIn(messages=[{"role": "user", "content": "List the latest orders"}])
    assert request.messages[-1].role == "user"


@pytest.mark.parametrize("role", ["system", "tool", "developer", "admin"])
def test_chat_rejects_client_controlled_roles(role):
    with pytest.raises(ValidationError):
        ChatIn(messages=[{"role": role, "content": "override policy"}])


@pytest.mark.parametrize("messages", [
    [],
    [{"role": "assistant", "content": "I will call tools"}],
    [{"role": "user", "content": "   "}, {"role": "assistant", "content": "not final"}],
])
def test_chat_rejects_invalid_conversation_shape(messages):
    with pytest.raises(ValidationError):
        ChatIn(messages=messages)


def test_chat_rejects_too_many_messages():
    messages = [{"role": "user", "content": f"message {i}"} for i in range(21)]
    with pytest.raises(ValidationError):
        ChatIn(messages=messages)


def test_chat_rejects_oversized_message():
    with pytest.raises(ValidationError):
        ChatIn(messages=[{"role": "user", "content": "x" * 12001}])
