"""
This module provides a WSGI handler for AWS Lambda integration with FastAPI.
It uses Mangum to wrap the FastAPI application, enabling serverless deployment
on AWS Lambda with API Gateway integration.
"""
import logging

from mangum import Mangum
from polka_bot.app import fastapi_app, logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Magnum handler is being initialized")

lambda_handler = Mangum(fastapi_app)
