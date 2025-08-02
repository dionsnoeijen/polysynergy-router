import boto3
import json
import os

from fastapi import Request, HTTPException
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse, Response
from botocore.config import Config

from routing.cache import get_routes
from routing.matcher import match_route

from core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

lambda_client = boto3.client(
    "lambda",
    region_name=os.getenv("AWS_REGION", "eu-central-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=Config(
        read_timeout=910,
        connect_timeout=5,
        retries={
            'max_attempts': 1,
            'mode': 'standard'
        }
    )
)


def parse_subdomain(host: str) -> tuple[str, str]:
    logger.debug(f"Parsing subdomain from host: '{host}'")
    try:
        base = host.split(".")[0]
        project_id, stage = base.rsplit("-", 1)
        logger.info(f"Parsed subdomain: project_id='{project_id}', stage='{stage}'")
        return project_id, stage
    except Exception as e:
        logger.error(f"Failed to parse subdomain from host '{host}': {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid subdomain format")


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all_router(request: Request, full_path: str):
    logger.info(f"Incoming request: {request.method} {full_path}")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    try:
        host = request.headers.get("host", "")
        if not host:
            logger.error("No host header provided in request")
            raise HTTPException(status_code=400, detail="Host header required")
            
        project_id, stage = parse_subdomain(host)

        logger.info(f"Fetching routes for project='{project_id}', stage='{stage}'")
        routes = get_routes(project_id, stage)
        logger.info(f"Found {len(routes)} routes for project='{project_id}', stage='{stage}'")
        
        matched = match_route(full_path, request.method, routes)

        if matched == "method_not_allowed":
            logger.warning(f"Method not allowed: {request.method} {full_path}")
            raise HTTPException(status_code=405, detail="Method Not Allowed")

        if not matched:
            logger.error(f"No route found for: {request.method} {full_path} (project='{project_id}', stage='{stage}')")
            # Log available routes for debugging
            if routes:
                logger.info("Available routes:")
                for r in routes:
                    segments_desc = "/".join([s.name if s.type == "static" else f"{{{s.name}}}" for s in r.segments])
                    logger.info(f"  - {r.method} /{segments_desc} (id: {r.id})")
            else:
                logger.info("No routes configured for this project/stage")
            raise HTTPException(status_code=404, detail="Not found")

        function_name = f"node_setup_{matched['node_setup_version_id']}_{stage}"
        logger.info(f"Route matched successfully. Invoking Lambda: {function_name}")
        logger.debug(f"Route details: id={matched['route_id']}, variables={matched['variables']}")

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
        
        logger.debug(f"Lambda payload size: {len(json.dumps(payload))} bytes")

        try:
            logger.info(f"Invoking Lambda function: {function_name}")
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )

            response_payload = json.loads(response["Payload"].read())
            logger.info(f"Lambda invocation successful, received response")

            body = response_payload.get("body", "")
            headers = response_payload.get("headers", {})
            status_code = response_payload.get("statusCode", 200)
            is_base64 = response_payload.get("isBase64Encoded", False)
            
            logger.info(f"Lambda response: status={status_code}, headers={headers}, is_base64={is_base64}")
            if status_code >= 400:
                logger.error(f"Lambda returned error status {status_code}, body: {body}")
            else:
                logger.debug(f"Lambda response body: {body[:200]}...")  # First 200 chars

            content_type = headers.get("Content-Type", "text/plain")

            if is_base64:
                import base64
                body = base64.b64decode(body)
                logger.debug("Decoded base64 response body")

            logger.info(f"Returning response: status={status_code}, content_type={content_type}")
            
            if content_type == "application/json":
                try:
                    return JSONResponse(content=json.loads(body), status_code=status_code, headers=headers)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in response body despite Content-Type: application/json")
                    return Response(content=body, status_code=status_code, headers=headers,
                                    media_type="application/json")
            else:
                return Response(content=body, status_code=status_code, headers=headers, media_type=content_type)
        except Exception as e:
            logger.error(f"Lambda invocation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Invocation failed: {str(e)}")


    except HTTPException as e:
        logger.warning(f"HTTP exception: {e.status_code} - {e.detail}")
        raise e

    except Exception as e:
        logger.error(f"Unexpected error in catch_all_router: {str(e)}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        if "cannot unpack non-iterable coroutine object" in str(e):
            logger.error("This error suggests an async/await issue - a coroutine is being unpacked without await")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
