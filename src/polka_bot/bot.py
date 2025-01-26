# bot.py
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BotConfig:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("Environment variable TELEGRAM_BOT_TOKEN is required.")

        self.webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Environment variable TELEGRAM_WEBHOOK_URL is required.")

        self.admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "@your_public_channel")


class BotHandlers:
    def __init__(self, config: BotConfig):
        self.config = config

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Welcome to Polka Bot! Use /help to see available commands."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "Commands:\n"
            "/start - Start the bot and see a welcome message\n"
            "/help - View this help message\n"
            "\n"
            "Send me a URL and I'll try to validate it!"
        )
        await update.message.reply_text(help_text)

    def is_valid_url(self, url: str) -> bool:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                await update.message.reply_text("I couldn't open that link. Please try again later.")
        else:
            await update.message.reply_text(
                "Send me a valid link or type /help for commands."
            )


def create_app(config: BotConfig):
    """
    Create a new Telegram bot application.
    """
    logger.info("Creating Telegram bot application...")
    app = ApplicationBuilder().token(config.bot_token).build()

    handlers = BotHandlers(config)

    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    return app
