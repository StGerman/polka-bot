"""
HTTP server logic for the Polka Bot.

This module:
- Defines a FastAPI application
- Manages the startup/shutdown (lifespan) to set/unset Telegram webhook
- Exposes webhook and health-check endpoints
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update

# Import the refactored bot logic
# (Assuming bot.py contains BotConfig, create_app, and a logger instance)
from bot import BotConfig, create_app, logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup logic:
      1. Load environment config (BotConfig)
      2. Create the Telegram Application via create_app
      3. Set the Telegram webhook

    Shutdown logic:
      - Delete the webhook
    """
    # 1. Load environment config
    bot_config = BotConfig()

    # 2. Create the Telegram bot application
    telegram_app = create_app(bot_config)

    # 3. Set Telegram webhook
    try:
        logger.info("Setting Telegram webhook ...")
        await telegram_app.bot.set_webhook(bot_config.webhook_url)
    except Exception as e:
        logger.error("Failed to set webhook at startup: %s", e)

    # Store references in FastAPI app state
    app.state.bot_config = bot_config
    app.state.telegram_app = telegram_app

    logger.info("Polka Bot is up and running!")
    yield

    # ----- Shutdown logic -----
    logger.info("Removing Telegram webhook and shutting down Polka Bot...")
    try:
        await telegram_app.bot.delete_webhook()
    except Exception as e:
        logger.error("Failed to delete webhook: %s", e)


# Create the FastAPI application, using the lifespan to manage webhook setup/teardown
fastapi_app = FastAPI(lifespan=lifespan)


@fastapi_app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receives Telegram updates via JSON payload and places them into the
    telegram_app's update queue for processing.
    """
    # Ensure env & telegram_app loaded
    try:
        data = await request.json()
        update = Update.de_json(data, fastapi_app.state.telegram_app.bot)
        await fastapi_app.state.telegram_app.update_queue.put(update)
    except Exception as e:
        logging.error(f"Error in /webhook endpoint: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=200
        )

    return JSONResponse(content={"status": "ok"}, status_code=200)


@fastapi_app.get("/")
def health_check():
    """Simple health-check endpoint."""
    return {"status": "Polka Bot is running!"}
