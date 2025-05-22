import os

AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

DYNAMODB_ROUTING_TABLE = os.getenv("DYNAMODB_ROUTING_TABLE", "poly_router_routing")

ROUTER_PORT = int(os.getenv("ROUTER_PORT", 8080))