import json

import pytest

import app as app_module
import chatbot


@pytest.fixture
def client():
    app_module.app.testing = True
    with app_module.app.test_client() as client:
        yield client


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_get_response_for_known_message(client):
    response = client.get("/get?msg=hello")
    assert response.status_code == 200
    data = response.get_json()
    assert "response" in data
    assert isinstance(data["response"], str) and data["response"]


def test_empty_message_is_handled_gracefully(client):
    response = client.get("/get")
    assert response.status_code == 200
    data = response.get_json()
    assert "didn't receive any message" in data["response"]


def test_overlong_message_is_rejected(client):
    too_long = "a" * (app_module.MAX_MESSAGE_LENGTH + 1)
    response = client.get("/get", query_string={"msg": too_long})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_unknown_route_returns_json_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_internal_error_does_not_leak_stack_trace(client, monkeypatch):
    def boom(self, _user_input):
        raise RuntimeError("something exploded internally, sensitive detail")

    monkeypatch.setattr(chatbot.Chatbot, "get_response", boom)

    response = client.get("/get?msg=hello")
    assert response.status_code == 500
    data = response.get_json()
    assert "error" in data
    body_text = json.dumps(data)
    assert "exploded" not in body_text
    assert "Traceback" not in body_text


def test_reset_clears_conversation_state(client):
    client.get("/get?msg=hello")
    with client.session_transaction() as flask_session:
        session_id = flask_session["session_id"]
    bot = app_module._bot_sessions[session_id]
    assert bot.last_intent == "greeting"

    response = client.post("/reset")
    assert response.status_code == 200
    assert bot.last_intent is None
