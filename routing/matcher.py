from typing import List, Optional, Dict
import re

from models.route import Segment, Route


def convert_segments_to_regex(segments: List[Segment]) -> str:
    regex_parts = []
    for segment in segments:
        if segment.type == "static":
            regex_parts.append(re.escape(segment.name))
        elif segment.type == "variable":
            match segment.variable_type:
                case "number":
                    regex_parts.append(rf"(?P<{segment.name}>\d+)")
                case "uuid":
                    regex_parts.append(rf"(?P<{segment.name}>[0-9a-fA-F-]{36})")
                case "string" | "any":
                    regex_parts.append(rf"(?P<{segment.name}>[^/]+)")
                case _:
                    raise ValueError(f"Unsupported variable_type: {segment.variable_type}")
    return "^" + "/".join(regex_parts) + "$"


def match_route(path: str, method: str, routes: List[Route]) -> Optional[Dict]:
    for route in routes:
        if route.method.upper() != method.upper():
            continue
        pattern = convert_segments_to_regex(route.segments)
        match = re.match(pattern, path)
        if match:
            return {
                "route_id": route.id,
                "node_setup_version_id": route.node_setup_version_id,
                "variables": match.groupdict()
            }
    return None