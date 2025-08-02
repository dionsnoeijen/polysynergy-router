from typing import List
from boto3.dynamodb.conditions import Key
import boto3
import os

from models.route import Route
from core.logging_config import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION", "eu-central-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
table = dynamodb.Table("poly_router_routing")

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