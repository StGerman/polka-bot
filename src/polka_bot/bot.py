"""
Bot logic module for the Polka Bot application.

Responsible for:
- Validating environment variables and loading them at runtime
- Creating and managing the Telegram application instance
- Defining command and message handlers for URL validation
- Streamlining content distribution to designated channels
- Providing administrative oversight and monitoring

Key Business Benefits:
- Reduces manual moderation effort
- Maintains content quality standards
- Improves user engagement through quick feedback
- Enables efficient content curation at scale
"""

import os
import logging
from urllib.parse import urlparse

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# -----------------------------------------------------------------------------
# 0. Setup Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# -----------------------------------------------------------------------------
# 1. Configuration & Initialization
# -----------------------------------------------------------------------------
class BotConfig:
    """
    Encapsulates all environment variables and provides validation.
    """
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("Environment variable TELEGRAM_BOT_TOKEN is required.")

        self.webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Environment variable TELEGRAM_WEBHOOK_URL is required.")

        self.admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "@your_public_channel")


# -----------------------------------------------------------------------------
# 2. Bot Handlers
# -----------------------------------------------------------------------------
class BotHandlers:
    """
    Defines all command and message handlers. Relies on a BotConfig instance
    for references to tokens, channel IDs, etc.
    """

    def __init__(self, config: BotConfig):
        self.config = config

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Send a welcome message when the /start command is used.
        """
        await update.message.reply_text(
            "Welcome to Polka Bot! Use /help to see available commands."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Send a help message listing available commands.
        """
        help_text = (
            "Commands:\n"
            "/start - Start the bot and see a welcome message\n"
            "/help - View this help message\n"
            "\n"
            "Send me a URL and I'll try to validate it!"
        )
        await update.message.reply_text(help_text)

    def is_valid_url(self, url: str) -> bool:
        """
        Basic syntactic validation using urlparse.
        Returns True if scheme is http/https and netloc is non-empty.
        """
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle non-command text messages.
        1. Use urlparse to validate URL syntax.
        2. HEAD request to check for <400 response.
        3. Post valid URL to the channel and inform user.
        """
        user_text = (update.message.text or "").strip()

        if self.is_valid_url(user_text):
            try:
                response = requests.head(user_text, allow_redirects=True, timeout=5)
                if response.status_code < 400:
                    await context.bot.send_message(
                        chat_id=self.config.channel_id,
                        text=f"User submitted a valid URL: {user_text}",
                    )
                    await update.message.reply_text("This link seems valid and was posted!")
                else:
                    await update.message.reply_text(
                        f"That link returned status code {response.status_code}, so it might be invalid."
                    )
            except Exception as e:
                logger.error("Error validating URL: %s", e)
                await update.message.reply_text(
                    "I couldn't open that link. Please try again later."
                )
        else:
            await update.message.reply_text(
                "Send me a valid link or type /help for commands."
            )


# -----------------------------------------------------------------------------
# 3. Application Factory
# -----------------------------------------------------------------------------
def create_app(config: BotConfig):
    """
    Creates and returns a fully configured Telegram Application instance.
    """
    logger.info("Creating the Telegram bot application...")
    app = ApplicationBuilder().token(config.bot_token).build()

    # Instantiate handlers with the given config
    handlers = BotHandlers(config)

    # Register command and message handlers
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    return app
