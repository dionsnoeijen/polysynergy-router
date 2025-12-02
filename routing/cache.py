from typing import List
from boto3.dynamodb.conditions import Key
import boto3
import os

from models.route import Route
from core.config import (
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    DYNAMODB_ROUTING_TABLE,
    DYNAMODB_LOCAL_ENDPOINT
)
from core.logging_config import get_logger

logger = get_logger(__name__)

# Initialize DynamoDB client with optional local endpoint
dynamodb_config = {
    "region_name": AWS_REGION,
}

# Use local endpoint if configured (self-hosted mode)
if DYNAMODB_LOCAL_ENDPOINT:
    dynamodb_config["endpoint_url"] = DYNAMODB_LOCAL_ENDPOINT
    # DynamoDB Local doesn't validate credentials
    dynamodb_config["aws_access_key_id"] = "dummy"
    dynamodb_config["aws_secret_access_key"] = "dummy"
    logger.info(f"Using DynamoDB Local at {DYNAMODB_LOCAL_ENDPOINT}")
elif AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    dynamodb_config["aws_access_key_id"] = AWS_ACCESS_KEY_ID
    dynamodb_config["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

dynamodb = boto3.resource("dynamodb", **dynamodb_config)
table = dynamodb.Table(DYNAMODB_ROUTING_TABLE)

routing_cache: dict[tuple[str, str], List[Route]] = {}

def get_routes(project_id: str, stage: str) -> List[Route]:
    key = (project_id, stage)

    if key in routing_cache:
        logger.debug(f"Cache hit for project='{project_id}', stage='{stage}' - returning {len(routing_cache[key])} routes")
        return routing_cache[key]

    logger.info(f"Cache miss for project='{project_id}', stage='{stage}' - querying DynamoDB")
    pk = f"routing#{project_id}"

    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("route#")
        )
        items = response.get("Items", [])
        logger.debug(f"DynamoDB query returned {len(items)} items for project='{project_id}'")

        routes = []
        for item in items:
            active_stages = item.get("active_stages", [])
            if stage in active_stages:
                route_id = item["SK"].split("#", 1)[1]
                routes.append(Route(
                    id=route_id,
                    method=item["method"],
                    require_api_key=item["require_api_key"],
                    segments=item["segments"],
                    node_setup_version_id=item["node_setup_version_id"],
                    tenant_id=item["tenant_id"],
                    active_stages=active_stages,
                ))
                logger.debug(f"Added route '{route_id}' to results (active stages: {active_stages})")
            else:
                route_id = item["SK"].split("#", 1)[1]
                logger.debug(f"Skipped route '{route_id}' - stage '{stage}' not in active stages: {active_stages}")

        logger.info(f"Caching {len(routes)} routes for project='{project_id}', stage='{stage}'")
        routing_cache[key] = routes
        return routes
        
    except Exception as e:
        logger.error(f"Failed to query DynamoDB for routes: {str(e)}", exc_info=True)
        # Return empty list on error to prevent cascading failures
        return []