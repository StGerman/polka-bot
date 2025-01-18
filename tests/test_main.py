# Run tests with: pytest tests/test_main.py
# Run tests with coverage: pytest --cov=src tests/test_main.py
# Run tests with coverage and generate HTML report: pytest --cov=src --cov-report html tests/test_main.py
#

"""
This file contains tests for the main.py file in the src directory.
"""

import pytest

from fastapi.testclient import TestClient
from polka_bot.main import fastapi_app, is_valid_url


#
# 1. Test the is_valid_url function
#
@pytest.mark.parametrize(
    "test_url, expected",
    [
        ("http://example.com", True),
        ("https://example.com", True),
        ("http://localhost:8000", True),
        ("https://sub.domain.com/path?query=abc", True),
        ("ftp://example.com", False),
        ("justastring", False),
        ("http://", False),
        ("", False),
    ],
)
def test_is_valid_url(test_url, expected):
    """
    Test the is_valid_url function with various URL inputs.
    """
    assert is_valid_url(test_url) == expected


#
# 2. Test the FastAPI health-check endpoint
#
def test_health_check():
    """
    Test the / endpoint of the FastAPI application.
    We expect a 200 status code and a JSON response with a 'status' key.
    """
    client = TestClient(fastapi_app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Polka Bot is running!" in data["status"]


#
# 3. Test the /webhook endpoint with minimal data
#
def test_webhook_empty_json():
    """
    Sends an empty JSON to /webhook.
    The code in main.py tries to parse it into a Telegram Update.
    We expect either a success 'ok' or an error message,
    but the response should have a 200 status code in either case.
    """
    client = TestClient(fastapi_app)
    response = client.post("/webhook", json={})
    assert response.status_code == 200
    json_response = response.json()
    # Could be {"status": "ok"} or {"status": "error", ...} depending on the logic
    # At minimum, verify that 'status' is present.
    assert "status" in json_response
