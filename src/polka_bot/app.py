# app.py
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
from polka_bot.bot import BotConfig, create_app, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup logic:
      1. Load environment config (BotConfig)
      2. Create the Telegram Application via create_app
    """
    bot_config = BotConfig()
    telegram_app = create_app(bot_config)

    # Store references in FastAPI app state
    app.state.bot_config = bot_config
    app.state.telegram_app = telegram_app

    logger.info("Polka Bot is up and running!")
    yield  # run the application
    logger.info("Polka Bot is shutdown!")


# The FastAPI application
fastapi_app = FastAPI(lifespan=lifespan)


@fastapi_app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receives Telegram updates via JSON payload
    and places them into the telegram_app's update queue.
    """
    try:
        data = await request.json()
        logger.info("Received webhook data: %s", data)

        update = Update.de_json(data, fastapi_app.state.telegram_app.bot)
        logger.info("Received update: %s", update)

        # Basic check: if there's no message and no callback_query,
        # treat this as invalid.
        if update.message is None and update.callback_query is None:
            raise ValueError("No message or callback_query in update.")

        # Put the update in the queue
        await fastapi_app.state.telegram_app.update_queue.put(update)

    except Exception as e:
        logging.error(f"Error in /webhook endpoint: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=200
        )

    return JSONResponse(content={"status": "ok"}, status_code=200)


@fastapi_app.get("/alive")
def health_check():
    """Simple health-check endpoint."""
    logger.info("Health check endpoint accessed.")
    return {"status": "Polka Bot is running!"}
