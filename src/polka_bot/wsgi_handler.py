"""
This module provides a WSGI handler for AWS Lambda integration with FastAPI.
It uses Mangum to wrap the FastAPI application, enabling serverless deployment
on AWS Lambda with API Gateway integration.
"""

from mangum import Mangum
from polka_bot.app import fastapi_app

lambda_handler = Mangum(fastapi_app)
