"""
Lambda Handler for FastAPI Backend
Uses Mangum to wrap FastAPI for AWS Lambda
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from mangum import Mangum
from app.main import app

# Create ASGI handler
handler = Mangum(app, lifespan="off")


def lambda_handler(event, context):
    """
    AWS Lambda handler function
    """
    return handler(event, context)
