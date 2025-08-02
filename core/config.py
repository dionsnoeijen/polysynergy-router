import os

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# DynamoDB Configuration
DYNAMODB_ROUTING_TABLE = os.getenv("DYNAMODB_ROUTING_TABLE", "poly_router_routing")

# Application Configuration
ROUTER_PORT = int(os.getenv("ROUTER_PORT", 8080))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
JSON_LOGS = os.getenv("JSON_LOGS", "false").lower() == "true"

# Debug mode - enables more verbose logging
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
if DEBUG_MODE:
    LOG_LEVEL = "DEBUG"