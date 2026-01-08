import boto3
import json
import os
import httpx

from fastapi import Request, HTTPException
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse, Response
from botocore.config import Config

from routing.cache import get_routes
from routing.matcher import match_route
from routing.request_parser import parse_request
from core.config import ROUTER_LOCAL_MODE, LOCAL_API_ENDPOINT
from core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Initialize Lambda client (only used in cloud mode)
lambda_client = None
if not ROUTER_LOCAL_MODE:
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
    logger.info("Router initialized in CLOUD mode (using Lambda)")
else:
    logger.info(f"Router initialized in SELF-HOSTED mode (using local API at {LOCAL_API_ENDPOINT})")


async def proxy_to_api_local(request: Request, full_path: str) -> Response:
    """Proxy requests to api_local service (for public API endpoints like embedded chat)."""
    try:
        # Build the target URL
        url = f"{LOCAL_API_ENDPOINT}/{full_path}"

        # Get request body if present
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()

        # Forward headers (excluding hop-by-hop headers)
        headers = {
            key: value for key, value in request.headers.items()
            if key.lower() not in ["host", "content-length", "transfer-encoding"]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=dict(request.query_params),
            )

            logger.info(f"Proxied to api_local: {response.status_code}")

            # Return response preserving headers
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )

    except httpx.TimeoutException:
        logger.error("Proxy to api_local timed out")
        raise HTTPException(status_code=504, detail="API timeout")
    except httpx.RequestError as e:
        logger.error(f"Proxy to api_local failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"API error: {str(e)}")


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all_router(request: Request, full_path: str):
    # Skip subdomain parsing for internal routes
    if full_path.startswith("__internal/"):
        logger.info(f"Skipping internal route: {request.method} {full_path}")
        raise HTTPException(status_code=404, detail="Internal route not found")

    # Proxy /api/v1/public/* requests to api_local (for embedded chat, etc.)
    if full_path.startswith("api/v1/public/"):
        logger.info(f"Proxying public API request: {request.method} /{full_path}")
        return await proxy_to_api_local(request, full_path)

    logger.info(f"Incoming request: {request.method} /{full_path}")
    logger.debug(f"Headers: {dict(request.headers)}")

    try:
        host = request.headers.get("host", "")
        if not host:
            logger.error("No host header provided in request")
            raise HTTPException(status_code=400, detail="Host header required")

        # Parse request using new unified parser (supports both subdomain and path-based)
        parsed = parse_request(host, f"/{full_path}")

        if not parsed:
            logger.error(f"Could not parse project/stage from host='{host}', path='/{full_path}'")
            raise HTTPException(
                status_code=400,
                detail="Invalid routing format. Use subdomain (project-stage.domain.com) or path-based (/project/stage/path)"
            )

        project_id = parsed.project_id
        stage = parsed.stage
        actual_path = parsed.path

        logger.info(f"Parsed request via {parsed.routing_method}: project='{project_id}', stage='{stage}', path='{actual_path}'")

        logger.info(f"Fetching routes for project='{project_id}', stage='{stage}'")
        routes = get_routes(project_id, stage)
        logger.info(f"Found {len(routes)} routes for project='{project_id}', stage='{stage}'")

        matched = match_route(actual_path, request.method, routes)

        if matched == "method_not_allowed":
            logger.warning(f"Method not allowed: {request.method} {actual_path}")
            raise HTTPException(status_code=405, detail="Method Not Allowed")

        if not matched:
            logger.error(f"No route found for: {request.method} {actual_path} (project='{project_id}', stage='{stage}')")
            # Log available routes for debugging
            if routes:
                logger.info("Available routes:")
                for r in routes:
                    segments_desc = "/".join([s.name if s.type == "static" else f"{{{s.name}}}" for s in r.segments])
                    logger.info(f"  - {r.method} /{segments_desc} (id: {r.id})")
            else:
                logger.info("No routes configured for this project/stage")
            raise HTTPException(status_code=404, detail="Not found")

        logger.info(f"Route matched successfully: id={matched['route_id']}, variables={matched['variables']}")
        logger.debug(f"Route details: node_setup_version_id={matched['node_setup_version_id']}, tenant_id={matched['tenant_id']}")

        # Prepare execution payload
        headers_dict = {key: value for key, value in request.headers.items()}
        query_dict = {key: value for key, value in request.query_params.items()}

        logger.info(f"Query params: {query_dict}")

        payload = {
            "path": actual_path,
            "method": request.method,
            "headers": headers_dict,
            "query_params": query_dict,
            "variables": matched["variables"],
            "project_id": project_id,
            "stage": stage,
            "tenant_id": matched["tenant_id"],
            "node_setup_version_id": matched["node_setup_version_id"],
            "body": (await request.body()).decode("utf-8") if request.method in ["POST", "PUT", "PATCH"] else None,
        }

        try:
            payload_json = json.dumps(payload)
            logger.debug(f"Execution payload size: {len(payload_json)} bytes")
        except Exception as e:
            logger.error(f"Failed to serialize payload: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to serialize request payload: {str(e)}")

        # Execute via Lambda (cloud) or local API (self-hosted)
        if ROUTER_LOCAL_MODE:
            # Self-hosted mode: Call local API
            return await execute_local(payload, payload_json)
        else:
            # Cloud mode: Call AWS Lambda
            return await execute_lambda(payload, payload_json, matched["node_setup_version_id"], stage)


    except HTTPException as e:
        logger.warning(f"HTTP exception: {e.status_code} - {e.detail}")
        raise e

    except Exception as e:
        logger.error(f"Unexpected error in catch_all_router: {str(e)}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        if "cannot unpack non-iterable coroutine object" in str(e):
            logger.error("This error suggests an async/await issue - a coroutine is being unpacked without await")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


async def execute_local(payload: dict, payload_json: str) -> Response:
    """Execute route via local API (self-hosted mode)."""
    logger.info(f"Executing via local API at {LOCAL_API_ENDPOINT}")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.post(
                f"{LOCAL_API_ENDPOINT}/api/v1/execution/route/",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            logger.info(f"Local API response: status={response.status_code}")

            # Return response as-is
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "text/plain")
            )

    except httpx.TimeoutException:
        logger.error("Local API request timed out")
        raise HTTPException(status_code=504, detail="Local API timeout")
    except httpx.RequestError as e:
        logger.error(f"Local API request failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Local API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error calling local API: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Local execution failed: {str(e)}")


async def execute_lambda(payload: dict, payload_json: str, node_setup_version_id: str, stage: str) -> Response:
    """Execute route via AWS Lambda (cloud mode)."""
    function_name = f"node_setup_{node_setup_version_id}_{stage}"
    logger.info(f"Invoking Lambda function: {function_name}")

    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=payload_json.encode("utf-8"),
        )

        response_payload = json.loads(response["Payload"].read())
        logger.info(f"Lambda invocation successful")

        body = response_payload.get("body", "")
        headers = response_payload.get("headers", {})
        status_code = response_payload.get("statusCode", 200)
        is_base64 = response_payload.get("isBase64Encoded", False)

        logger.info(f"Lambda response: status={status_code}, is_base64={is_base64}")

        if status_code >= 400:
            logger.error(f"Lambda returned error status {status_code}, body: {body}")
        else:
            logger.debug(f"Lambda response body: {str(body)[:200]}...")

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
                logger.warning("Invalid JSON in response body")
                return Response(content=body, status_code=status_code, headers=headers,
                                media_type="application/json")
        else:
            return Response(content=body, status_code=status_code, headers=headers, media_type=content_type)

    except Exception as e:
        logger.error(f"Lambda invocation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lambda invocation failed: {str(e)}")
