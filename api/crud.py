from fastapi import HTTPException, APIRouter
import boto3
from boto3.dynamodb.conditions import Key

from core.config import AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, DYNAMODB_ROUTING_TABLE
from models.route import SingleRouteUpdate, DeactivateRouteRequest
from routing.cache import routing_cache

router = APIRouter()

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)
table = dynamodb.Table(DYNAMODB_ROUTING_TABLE)

@router.post("/update-route")
def update_route(data: SingleRouteUpdate):
    try:
        pk = f"routing#{data.project_id}"
        sk = f"route#{data.route.id}"

        existing = table.get_item(Key={"PK": pk, "SK": sk}).get("Item", {})
        active_stages = set(existing.get("active_stages", []))
        active_stages.add(data.stage)

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
        table.put_item(Item=item)

        routing_cache.pop((data.project_id, data.stage), None)

        return {"message": "Route updated successfully."}
    except Exception as e:
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
def delete_route(data: SingleRouteUpdate):
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