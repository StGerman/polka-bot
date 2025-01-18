# tests/conftest.py

"""
This file contains fixtures for the tests in the tests directory.
"""

import pytest


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    """
    Set environment variables for testing.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://fake-webhook")
    monkeypatch.setenv("ADMIN_CHAT_ID", "123456789")
