# config.py
import os
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# For tests, we allow a default value so tests can run without errors
AWS_DB_URL = os.getenv("AWS_DB_URL")  # e.g., "postgresql+psycopg2://user:password@host:5432/dbname"
if not AWS_DB_URL:
    # In production, we would raise an error
    # For testing, we'll use a dummy value
    if os.getenv("TESTING") or os.getenv("GITHUB_ACTIONS"):
        AWS_DB_URL = "postgresql://dummy:dummy@localhost:5432/dummy"
    else:
        raise ValueError("AWS_DB_URL environment variable not set")

TALLY_URL = os.getenv("TALLY_URL", "http://localhost:9000")

COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_REGION = os.getenv("COGNITO_REGION")
if not all([COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_REGION]):
    # For testing purposes, use dummy values if we're in a test environment
    if os.getenv("TESTING") or os.getenv("GITHUB_ACTIONS"):
        COGNITO_USER_POOL_ID = COGNITO_USER_POOL_ID or "us-east-1_dummy"
        COGNITO_CLIENT_ID = COGNITO_CLIENT_ID or "dummyclientid"
        COGNITO_REGION = COGNITO_REGION or "us-east-1"
    else:
        raise ValueError("Cognito configuration is incomplete.")

def get_company_table_name(username, company_name):
    """
    Build a unique identifier for the company using the username and the company name.
    """
    sanitized_company = re.sub(r'\W+', '_', company_name.lower())
    return sanitized_company
