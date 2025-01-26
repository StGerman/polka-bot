# tests/test_app.py

from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from polka_bot.app import fastapi_app


@pytest.fixture
def client():
    """
    Provides a synchronous TestClient for the FastAPI application.
    It will run the app's lifespan (startup/shutdown) around each test.
    """
    with TestClient(fastapi_app) as test_client:
        yield test_client


def test_health_check(client):
    """
    Basic integration test for the health-check endpoint.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "Polka Bot is running!"}


@pytest.mark.parametrize(
    "update_json",
    [
        # Minimal Telegram update structure
        {
            "update_id": 1234,
            "message": {
                "message_id": 1,
                "text": "Hello Bot",
                "chat": {"id": 5678, "type": "private"},
                "date": 1111111111,
            },
        },
        # Callback query with required chat_instance
        {
            "update_id": 5678,
            "callback_query": {
                "id": "12345",
                "from": {"id": 9876, "is_bot": False, "first_name": "Test"},
                "chat_instance": "some_chat_instance",
                "message": {
                    "message_id": 10,
                    "chat": {"id": 9876, "type": "private"},
                    "date": 2222222222,
                    "text": "A callback query message",
                },
                "data": "callback_data_example",
            },
        },
    ],
)
def test_webhook_endpoint(client, update_json):
    """
    Integration test for the /webhook endpoint.
    Sends a Telegram-like JSON payload and expects a 200 OK response.
    """
    response = client.post("/webhook", json=update_json)
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}  # The endpoint returns {'status': 'ok'} on success.


@pytest.mark.parametrize(
    "malformed_payload",
    [
        {},  # Empty
        {"not": "a valid telegram update"},  # Invalid keys
        "this is not even JSON",  # a string instead of an object
    ],
)
def test_webhook_endpoint_invalid_payload(client, malformed_payload):
    """
    Test sending invalid data to /webhook.
    The endpoint should return a 200 with {"status": "error"} but won't crash the server.
    """
    if isinstance(malformed_payload, dict):
        response = client.post("/webhook", json=malformed_payload)
    else:
        # string as non-JSON data
        response = client.post("/webhook", data=malformed_payload)

    assert response.status_code == 200
    data = response.json()
    # We expect 'error' for either empty, malformed, or non-json data
    assert data["status"] == "error"


@pytest.mark.parametrize(
    "update_json",
    [
        {
            "update_id": 1234,
            "message": {
                "message_id": 1,
                "text": "Hello Bot",
                "chat": {"id": 5678, "type": "private"},
                "date": 1111111111,
            },
        },
    ],
)
@patch(
    "polka_bot.app.fastapi_app.state.telegram_app.update_queue.put",
    new_callable=AsyncMock,
)
def test_webhook_endpoint_queue_interaction(mock_put, client, update_json):
    """
    Example of mocking the queue to verify that /webhook
    tries to put the parsed Update into the queue.
    """
    response = client.post("/webhook", json=update_json)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    # Ensure we tried to put an Update into the queue
    assert mock_put.await_count == 1
    (update_instance,), _ = mock_put.await_args
    # Optionally check fields on 'update_instance'
    assert update_instance.update_id == update_json["update_id"]
