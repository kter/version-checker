"""
Lambda Handler for FastAPI Backend
Uses Mangum to wrap FastAPI for AWS Lambda
"""

import sys
from pathlib import Path

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

sentry_sdk.init(
    dsn="https://fa0da4cd1831bfc50e8f60a79b32f2c9@o4511031892705280.ingest.us.sentry.io/4511173944934400",
    send_default_pii=True,
    integrations=[AwsLambdaIntegration(timeout_warning=True)],
)

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from mangum import Mangum
from app.main import app

# Run FastAPI lifespan hooks on Lambda cold start so DB initialization executes.
handler = Mangum(app, lifespan="auto")


def lambda_handler(event, context):
    """
    AWS Lambda handler function
    """
    return handler(event, context)
