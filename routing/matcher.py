from typing import List, Optional, Dict
import re

from models.route import Segment, Route
from core.logging_config import get_logger

logger = get_logger(__name__)


def convert_segments_to_regex(segments: List[Segment]) -> str:
    regex_parts = []
    segment_descriptions = []
    
    for segment in segments:
        if segment.type == "static":
            # Skip empty segments (which can occur from leading slashes)
            if segment.name:
                regex_parts.append(re.escape(segment.name))
                segment_descriptions.append(f"static:'{segment.name}'")
        elif segment.type == "variable":
            segment_descriptions.append(f"var:{segment.name}({segment.variable_type})")
            match segment.variable_type:
                case "number":
                    regex_parts.append(rf"(?P<{segment.name}>\d+)")
                case "uuid":
                    regex_parts.append(rf"(?P<{segment.name}>[0-9a-fA-F-]{{36}})")
                case "string" | "any":
                    regex_parts.append(rf"(?P<{segment.name}>[^/]+)")
                case _:
                    raise ValueError(f"Unsupported variable_type: {segment.variable_type}")
    
    # Handle empty regex_parts (would happen if all segments were empty)
    if not regex_parts:
        pattern = "^$"
    else:
        pattern = "^" + "/".join(regex_parts) + "$"
    
    logger.debug(f"Converted segments [{', '.join(segment_descriptions)}] to regex: {pattern}")
    return pattern


def match_route(path: str, method: str, routes: List[Route]) -> Optional[Dict] | str:
    method = method.upper()
    path_matched = False
    
    logger.info(f"Attempting to match path '{path}' with method '{method}'")
    logger.debug(f"Available routes: {len(routes)}")

    for route in routes:
        pattern = convert_segments_to_regex(route.segments)
        match = re.match(pattern, path)
        
        if match:
            logger.debug(f"Path '{path}' matched route '{route.id}' pattern '{pattern}'")
            path_matched = True
            
            if route.method.upper() == method:
                variables = match.groupdict()
                logger.info(f"✓ Route matched: '{route.id}' with variables: {variables}")
                return {
                    "route_id": route.id,
                    "node_setup_version_id": route.node_setup_version_id,
                    "tenant_id": route.tenant_id,
                    "variables": variables
                }
            else:
                logger.debug(f"Method mismatch: route expects '{route.method}', got '{method}'")
        else:
            logger.debug(f"Path '{path}' did not match pattern '{pattern}' for route '{route.id}'")

    if path_matched:
        logger.warning(f"Path '{path}' matched a route but method '{method}' not allowed")
        return "method_not_allowed"
    
    logger.warning(f"No route found for path '{path}' with method '{method}'")
    return None