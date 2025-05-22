from typing import List
from boto3.dynamodb.conditions import Key
import boto3
import os

from models.route import Route

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
        return routing_cache[key]

    pk = f"routing#{project_id}"

    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("route#")
    )
    items = response.get("Items", [])

    routes = []
    for item in items:
        if stage in item.get("active_stages", []):
            routes.append(Route(
                id=item["SK"].split("#", 1)[1],
                method=item["method"],
                require_api_key=item["require_api_key"],
                segments=item["segments"],
                node_setup_version_id=item["node_setup_version_id"],
                tenant_id=item["tenant_id"],
                active_stages=item["active_stages"],
            ))

    routing_cache[key] = routes
    return routes