from fastapi import HTTPException, APIRouter
import boto3
from boto3.dynamodb.conditions import Key

from core.config import (
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    DYNAMODB_ROUTING_TABLE,
    DYNAMODB_LOCAL_ENDPOINT,
    ROUTER_LOCAL_MODE
)
from models.route import SingleRouteUpdate, DeactivateRouteRequest, DeleteRouteRequest
from routing.cache import routing_cache

router = APIRouter()

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
elif AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    dynamodb_config["aws_access_key_id"] = AWS_ACCESS_KEY_ID
    dynamodb_config["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

dynamodb = boto3.resource("dynamodb", **dynamodb_config)
table = dynamodb.Table(DYNAMODB_ROUTING_TABLE)

@router.post("/update-route")
def update_route(data: SingleRouteUpdate):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Received update-route request: project_id={data.project_id}, stage={data.stage}")
        logger.info(f"Route data: id={data.route.id}, method={data.route.method}")
        logger.info(f"Route active_stages: {getattr(data.route, 'active_stages', None)}")
        
        pk = f"routing#{data.project_id}"
        sk = f"route#{data.route.id}"

        existing = table.get_item(Key={"PK": pk, "SK": sk}).get("Item", {})
        logger.info(f"Existing DynamoDB item: {existing}")
        
        active_stages = set(existing.get("active_stages", []))
        logger.info(f"Current active_stages from DB: {active_stages}")
        
        if data.stage:
            active_stages.add(data.stage)
            logger.info(f"Added stage '{data.stage}', new active_stages: {active_stages}")
        elif hasattr(data.route, 'active_stages') and data.route.active_stages:
            active_stages.update(data.route.active_stages)
            logger.info(f"Updated with route active_stages: {data.route.active_stages}, new active_stages: {active_stages}")

        item = {
            "PK": pk,
            "SK": sk,
            "method": data.route.method,
            "require_api_key": data.route.require_api_key,
            "segments": [s.model_dump() for s in data.route.segments],
            "node_setup_version_id": data.route.node_setup_version_id,
            "tenant_id": data.tenant_id,
            "active_stages": list(active_stages),
        }
        logger.info(f"Writing item to DynamoDB: {item}")
        table.put_item(Item=item)

        routing_cache.pop((data.project_id, data.stage), None)

        return {"message": "Route updated successfully."}
    except Exception as e:
        logger.error(f"Error in update_route: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update route: {str(e)}")

@router.post("/deactivate-route")
def deactivate_route(data: DeactivateRouteRequest):
    try:
        pk = f"routing#{data.project_id}"
        sk = f"route#{data.route.id}"

        # haal huidige item op
        response = table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item")

        if not item:
            raise HTTPException(status_code=404, detail="Route not found.")

        stages = set(item.get("active_stages", []))
        if data.stage in stages:
            stages.remove(data.stage)
            if stages:
                table.update_item(
                    Key={"PK": pk, "SK": sk},
                    UpdateExpression="SET active_stages = :stages",
                    ExpressionAttributeValues={":stages": list(stages)}
                )
            else:
                table.delete_item(Key={"PK": pk, "SK": sk})

        routing_cache.pop((data.project_id, data.stage), None)

        return {"message": f"Stage '{data.stage}' deactivated for route '{data.route.id}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate route: {str(e)}")

@router.delete("/delete-route")
def delete_route(data: DeleteRouteRequest):
    try:
        pk = f"routing#{data.project_id}"
        sk = f"route#{data.route.id}"

        # eerst ophalen om te zien welke stages actief waren
        response = table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item")

        if item:
            for stage in item.get("active_stages", []):
                routing_cache.pop((data.project_id, stage), None)

        table.delete_item(Key={"PK": pk, "SK": sk})

        return {"message": "Route deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete route: {str(e)}")

@router.get("/routes/{project_id}")
def get_routes(project_id: str):
    try:
        response = table.query(KeyConditionExpression=Key("PK").eq(f"routing#{project_id}"))
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch routes: {str(e)}")