import boto3
import json
import os

from fastapi import Request, HTTPException
from fastapi.routing import APIRouter

from routing.cache import get_routes
from routing.matcher import match_route

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

lambda_client = boto3.client(
    "lambda",
    region_name=os.getenv("AWS_REGION", "eu-central-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

def parse_subdomain(host: str) -> tuple[str, str]:
    try:
        base = host.split(".")[0]
        project_id, stage = base.rsplit("-", 1)
        return project_id, stage
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid subdomain format")

@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all_router(request: Request, full_path: str):
    try:
        host = request.headers.get("host", "")
        project_id, stage = parse_subdomain(host)

        routes = get_routes(project_id, stage)
        matched = match_route(full_path, request.method, routes)

        if matched == "method_not_allowed":
            raise HTTPException(status_code=405, detail="Method Not Allowed")

        if not matched:
            raise HTTPException(status_code=404, detail="Not found")

        function_name = f"node_setup_{matched['node_setup_version_id']}_{stage}"

        payload = {
            "path": full_path,
            "method": request.method,
            "headers": dict(request.headers),
            "query": dict(request.query_params),
            "variables": matched["variables"],
            "project_id": project_id,
            "stage": stage,
            "tenant_id": matched["tenant_id"],
            "body": (await request.body()).decode("utf-8") if request.method in ["POST", "PUT", "PATCH"] else None,
        }

        try:
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )

            response_payload = json.loads(response["Payload"].read())
            return response_payload
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lambda invocation failed: {str(e)}")


    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")