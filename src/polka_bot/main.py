import os
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# 1. Module-Level Variables Initially None
#    We won't fail if they're missing at import time.
# -----------------------------------------------------------------------------
BOT_TOKEN = None
WEBHOOK_URL = None
ADMIN_CHAT_ID = None
TELEGRAM_CHANNEL_ID = None


def ensure_env_loaded():
    """
    Load and validate environment variables, storing them in module-level globals.
    Raise an error if required vars are missing.
    """
    global BOT_TOKEN, WEBHOOK_URL, ADMIN_CHAT_ID, TELEGRAM_CHANNEL_ID

    if BOT_TOKEN is None:
        BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        if not BOT_TOKEN:
            raise ValueError("Environment variable TELEGRAM_BOT_TOKEN is required.")

    if WEBHOOK_URL is None:
        WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
        if not WEBHOOK_URL:
            raise ValueError("Environment variable TELEGRAM_WEBHOOK_URL is required.")

    if ADMIN_CHAT_ID is None:
        ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", None)

    if TELEGRAM_CHANNEL_ID is None:
        TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@your_public_channel")


# -----------------------------------------------------------------------------
# 2. Telegram Bot Application (created lazily after env load)
#    We'll create it once in 'ensure_env_loaded' or in lifespan as needed.
# -----------------------------------------------------------------------------
telegram_app = None


def create_telegram_app_if_needed():
    global telegram_app, BOT_TOKEN
    if telegram_app is None:
        logger.info("Creating the Telegram bot application...")
        telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()


# -----------------------------------------------------------------------------
# 3. Admin Notification Helper
# -----------------------------------------------------------------------------
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str):
    """
    Send an error or debug message to the admin, if ADMIN_CHAT_ID is set.
    """
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")


# -----------------------------------------------------------------------------
# 4. Command Handlers
# -----------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a welcome message when the /start command is used.
    """
    await update.message.reply_text(
        "Welcome to Polka Bot! Use /help to see available commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


# -----------------------------------------------------------------------------
# 5. URL Validation with urlparse + HEAD Check
# -----------------------------------------------------------------------------
def is_valid_url(url: str) -> bool:
    """
    Basic syntactic validation using urlparse.
    Returns True if scheme is http/https and netloc is non-empty.
    """
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle non-command text messages.
    1. Use urlparse to validate URL syntax.
    2. (Optional) Use HEAD request to check for <400 response.
    3. Post valid URL to the channel and inform user.
    """
    user_text = (update.message.text or "").strip()

    if is_valid_url(user_text):
        # HEAD request to check accessibility
        try:
            response = requests.head(user_text, allow_redirects=True, timeout=5)
            if response.status_code < 400:
                # Post to the channel
                await context.bot.send_message(
                    chat_id=TELEGRAM_CHANNEL_ID,
                    text=f"User submitted a valid URL: {user_text}",
                )
                # Acknowledge to user
                await update.message.reply_text("This link seems valid and was posted!")
            else:
                await update.message.reply_text(
                    f"That link returned status code {response.status_code}, so it might be invalid."
                )
        except Exception as e:
            logger.error(f"Error validating URL: {e}")
            await update.message.reply_text(
                "I couldn't open that link. Please try again later."
            )
            # Notify admin about the exception
            await notify_admin(context, f"Validation error: {e}")
    else:
        # Not a valid URL
        await update.message.reply_text(
            "Send me a valid link or type /help for commands."
        )


# -----------------------------------------------------------------------------
# 6. Lifespan (Startup/Shutdown)
# -----------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup logic:
      1. Ensure environment variables are loaded/validated
      2. Create the Telegram application if needed
      3. Set the Telegram webhook

    Shutdown logic:
      - Optionally remove the webhook
    """
    # 1. Load env
    ensure_env_loaded()

    # 2. Create the Telegram bot application if not yet created
    create_telegram_app_if_needed()

    # 3. Register handlers (just once)
    register_handlers(telegram_app)

    # 4. Set Telegram webhook
    try:
        logger.info("Setting Telegram webhook...")
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
    except Exception as e:
        logger.error(f"Failed to set webhook at startup: {e}")

    logger.info("Polka Bot is up and running!")
    yield

    # ----- Shutdown logic -----
    logger.info("Removing Telegram webhook and shutting down Polka Bot...")
    try:
        await telegram_app.bot.delete_webhook()
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")


# -----------------------------------------------------------------------------
# 7. Register Handlers
#    We only call this once, to avoid duplicates if lifespan is triggered multiple times.
# -----------------------------------------------------------------------------
def register_handlers(app):
    """
    Register command and message handlers for the Telegram app.
    """
    # Only register if no handlers are present (idempotent check)
    if not app.handlers:
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# -----------------------------------------------------------------------------
# 8. FastAPI Application
# -----------------------------------------------------------------------------
fastapi_app = FastAPI(lifespan=lifespan)


@fastapi_app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receives Telegram updates via JSON payload, passes them to the telegram_app queue.
    """
    # Ensure env & telegram_app loaded
    ensure_env_loaded()
    create_telegram_app_if_needed()

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.update_queue.put(update)
    except Exception as e:
        logger.error(f"Error in /webhook endpoint: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=200
        )

    return JSONResponse(content={"status": "ok"}, status_code=200)


@fastapi_app.get("/")
def health_check():
    """Simple health-check endpoint."""
    return {"status": "Polka Bot is running!"}
