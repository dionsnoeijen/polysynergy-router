from pydantic import BaseModel
from typing import Literal, List, Optional


class Segment(BaseModel):
    type: Literal["static", "variable"]
    name: str
    variable_type: Literal["string", "number", "uuid", "any"] = "any"

class Route(BaseModel):
    id: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    require_api_key: bool
    segments: List[Segment]
    node_setup_version_id: str
    tenant_id: str
    active_stages: Optional[List[str]] = None

class SingleRouteUpdate(BaseModel):
    project_id: str
    tenant_id: str
    stage: str
    route: Route

class RouteRef(BaseModel):
    id: str

class DeleteRouteRequest(BaseModel):
    project_id: str
    route: RouteRef

class MinimalRoute(BaseModel):
    id: str

class DeactivateRouteRequest(BaseModel):
    project_id: str
    stage: str
    route: MinimalRoute