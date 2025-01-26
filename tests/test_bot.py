import pytest
import requests
from unittest.mock import patch, MagicMock, AsyncMock
from telegram import Update, Message
from telegram.ext import ContextTypes

from polka_bot.bot import BotConfig, BotHandlers, create_app


# -----------------------------------------------------------------------------
# 1. Test BotConfig
# -----------------------------------------------------------------------------
def test_bot_config_all_env(monkeypatch):
    """
    Test that BotConfig correctly loads environment variables
    when they are all set.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@testchannel")

    config = BotConfig()

    assert config.bot_token == "test_bot_token"
    assert config.channel_id == "@testchannel"
    # admin_chat_id is optional, so we won't test it explicitly here.


def test_bot_config_missing_token(monkeypatch):
    """
    Test that BotConfig raises an error when TELEGRAM_BOT_TOKEN is missing.
    """
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN is required"):
        BotConfig()


def test_bot_config_missing_channel(monkeypatch):
    """
    Test that BotConfig sets a default channel_id when TELEGRAM_CHANNEL_ID is missing.
    """
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    config = BotConfig()
    assert config.channel_id == "@your_public_channel"


# -----------------------------------------------------------------------------
# 2. Test BotHandlers.is_valid_url
# -----------------------------------------------------------------------------
@pytest.fixture
def bot_config_fixture(monkeypatch):
    """Provides a BotConfig with minimal valid environment variables."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@testchannel")
    return BotConfig()


@pytest.fixture
def bot_handlers_fixture(bot_config_fixture):
    """Provides an instance of BotHandlers initialized with the test BotConfig."""
    return BotHandlers(bot_config_fixture)


def test_is_valid_url(bot_handlers_fixture):
    """
    Check that is_valid_url correctly identifies valid/invalid URLs.
    """
    assert bot_handlers_fixture.is_valid_url("http://example.com") is True
    assert bot_handlers_fixture.is_valid_url("https://example.com") is True
    assert bot_handlers_fixture.is_valid_url(" ftp://example.com") is False
    assert bot_handlers_fixture.is_valid_url("example.com") is False
    assert bot_handlers_fixture.is_valid_url("http://") is False


# -----------------------------------------------------------------------------
# 3. Pytest-asyncio for Handler Methods
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_start_command(bot_handlers_fixture):
    """
    Test the /start command, ensuring it sends a welcome message.
    """
    mock_update = MagicMock(spec=Update)
    mock_message = MagicMock(spec=Message)
    mock_message.text = "/start"
    mock_update.message = mock_message

    # Mock the reply_text method
    mock_message.reply_text = AsyncMock()

    await bot_handlers_fixture.start_command(mock_update, MagicMock())

    mock_message.reply_text.assert_awaited_once()
    args, _ = mock_message.reply_text.call_args
    assert "Welcome to Polka Bot" in args[0]


@pytest.mark.asyncio
async def test_help_command(bot_handlers_fixture):
    """
    Test the /help command, ensuring it sends the help text.
    """
    mock_update = MagicMock(spec=Update)
    mock_message = MagicMock(spec=Message)
    mock_message.text = "/help"
    mock_update.message = mock_message

    # Mock the reply_text method
    mock_message.reply_text = AsyncMock()

    await bot_handlers_fixture.help_command(mock_update, MagicMock())

    mock_message.reply_text.assert_awaited_once()
    args, _ = mock_message.reply_text.call_args
    assert "Commands:" in args[0]
    assert "/start" in args[0]


@pytest.mark.asyncio
@patch("requests.head")
async def test_handle_message_valid_url(mock_head, bot_handlers_fixture):
    """
    Test handle_message with a valid URL that returns <400 status code.
    It should send a message to the channel and inform the user.
    """
    # Mock successful HEAD response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_head.return_value = mock_response

    # Build a mock update with text that is a valid URL
    mock_update = MagicMock(spec=Update)
    mock_message = MagicMock(spec=Message)
    mock_message.text = "https://example.com"
    mock_update.message = mock_message

    # We need a mock context with a bot that can send_message
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    mock_context.bot = mock_bot

    # Mock the reply_text method
    mock_message.reply_text = AsyncMock()

    await bot_handlers_fixture.handle_message(mock_update, mock_context)

    # Assert requests.head was called
    mock_head.assert_called_once_with(
        "https://example.com", allow_redirects=True, timeout=5
    )

    # Assert it posted to the channel
    mock_bot.send_message.assert_awaited_once()
    send_args, send_kwargs = mock_bot.send_message.call_args
    assert send_kwargs["chat_id"] == bot_handlers_fixture.config.channel_id
    assert "User submitted a valid URL" in send_kwargs["text"]

    # Assert it replied to the user
    mock_message.reply_text.assert_awaited_once()
    reply_args, _ = mock_message.reply_text.call_args
    assert "This link seems valid" in reply_args[0]


@pytest.mark.asyncio
@patch("requests.head")
async def test_handle_message_invalid_url(mock_head, bot_handlers_fixture):
    """
    Test handle_message with an invalid URL syntax (not even called requests.head).
    It should ask the user for a valid link.
    """
    mock_update = MagicMock(spec=Update)
    mock_message = MagicMock(spec=Message)
    mock_message.text = "not_a_valid_url"
    mock_update.message = mock_message

    mock_head.return_value = MagicMock(status_code=200)  # Should never be called

    mock_message.reply_text = AsyncMock()
    mock_context = MagicMock()

    await bot_handlers_fixture.handle_message(mock_update, mock_context)

    mock_head.assert_not_called()
    mock_message.reply_text.assert_awaited_once()
    reply_args, _ = mock_message.reply_text.call_args
    assert "Send me a valid link" in reply_args[0]


@pytest.mark.asyncio
@patch("requests.head")
async def test_handle_message_url_status_error(mock_head, bot_handlers_fixture):
    """
    Test handle_message with a valid URL but returning a 404.
    The bot should inform the user it's invalid.
    """
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_head.return_value = mock_response

    mock_update = MagicMock(spec=Update)
    mock_message = MagicMock(spec=Message)
    mock_message.text = "http://example.com/404"
    mock_update.message = mock_message

    mock_message.reply_text = AsyncMock()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    mock_context.bot = mock_bot

    await bot_handlers_fixture.handle_message(mock_update, mock_context)

    mock_head.assert_called_once()
    # No call to send_message on the bot if the URL is invalid
    mock_bot.send_message.assert_not_awaited()

    mock_message.reply_text.assert_awaited_once()
    reply_args, _ = mock_message.reply_text.call_args
    assert "returned status code 404" in reply_args[0]


@pytest.mark.asyncio
@patch("requests.head", side_effect=requests.RequestException("Network error"))
async def test_handle_message_url_exception(mock_head, bot_handlers_fixture):
    """
    Test handle_message with a requests exception (network error, etc.)
    Bot should reply with an error message.
    """
    mock_update = MagicMock(spec=Update)
    mock_message = MagicMock(spec=Message)
    mock_message.text = "https://example.com"
    mock_update.message = mock_message

    mock_message.reply_text = AsyncMock()
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await bot_handlers_fixture.handle_message(mock_update, mock_context)

    mock_head.assert_called_once()
    mock_message.reply_text.assert_awaited_once()
    reply_args, _ = mock_message.reply_text.call_args
    assert "I couldn't open that link" in reply_args[0]


# -----------------------------------------------------------------------------
# 4. Test create_app
# -----------------------------------------------------------------------------
def test_create_app(bot_config_fixture):
    """
    Test that create_app returns a valid Telegram Application instance
    with handlers registered.
    """
    from telegram.ext import Application

    app = create_app(bot_config_fixture)
    assert isinstance(app, Application)
    # Verify handlers (optional, depending on how you want to confirm).
    # For instance, check that there are the expected handlers:
    assert len(app.handlers) > 0
