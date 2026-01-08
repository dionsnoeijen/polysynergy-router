import pytest
from routing.matcher import convert_segments_to_regex, match_route
from models.route import Segment, Route


class TestConvertSegmentsToRegex:
    
    def test_static_segment_conversion(self):
        segments = [Segment(type="static", name="api")]
        result = convert_segments_to_regex(segments)
        assert result == "^api$"
    
    def test_multiple_static_segments(self):
        segments = [
            Segment(type="static", name="api"),
            Segment(type="static", name="v1"),
            Segment(type="static", name="users")
        ]
        result = convert_segments_to_regex(segments)
        assert result == "^api/v1/users$"
    
    def test_string_variable_segment(self):
        segments = [Segment(type="variable", name="user_id", variable_type="string")]
        result = convert_segments_to_regex(segments)
        assert result == "^(?P<user_id>[^/]+)$"
    
    def test_number_variable_segment(self):
        segments = [Segment(type="variable", name="id", variable_type="number")]
        result = convert_segments_to_regex(segments)
        assert result == "^(?P<id>\\d+)$"
    
    def test_uuid_variable_segment(self):
        segments = [Segment(type="variable", name="uuid", variable_type="uuid")]
        result = convert_segments_to_regex(segments)
        assert result == "^(?P<uuid>[0-9a-fA-F-]{36})$"
    
    def test_any_variable_segment_default(self):
        segments = [Segment(type="variable", name="param")]
        result = convert_segments_to_regex(segments)
        assert result == "^(?P<param>[^/]+)$"
    
    def test_any_variable_segment(self):
        segments = [Segment(type="variable", name="param", variable_type="any")]
        result = convert_segments_to_regex(segments)
        assert result == "^(?P<param>[^/]+)$"
    
    def test_mixed_segments(self):
        segments = [
            Segment(type="static", name="api"),
            Segment(type="variable", name="version", variable_type="string"),
            Segment(type="static", name="users"),
            Segment(type="variable", name="user_id", variable_type="number")
        ]
        result = convert_segments_to_regex(segments)
        assert result == "^api/(?P<version>[^/]+)/users/(?P<user_id>\\d+)$"
    
    def test_special_characters_in_static_segment(self):
        segments = [Segment(type="static", name="api.v1")]
        result = convert_segments_to_regex(segments)
        assert result == "^api\\.v1$"
    
    def test_unsupported_variable_type_raises_error(self):
        # This test won't work because Pydantic validates the literal types
        # Instead, test that invalid types are caught by Pydantic
        with pytest.raises(Exception):  # Pydantic ValidationError
            Segment(type="variable", name="param", variable_type="unknown")


class TestMatchRoute:
    
    def test_exact_static_match(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("api", "GET", routes)  # Path without leading slash
        assert result == {
            "route_id": "route1",
            "node_setup_version_id": "v1",
            "tenant_id": "tenant1",
            "variables": {}
        }
    
    def test_no_match_returns_none(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("different", "GET", routes)
        assert result is None
    
    def test_path_matches_but_method_doesnt_returns_method_not_allowed(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("api", "POST", routes)
        assert result == "method_not_allowed"
    
    def test_variable_extraction(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[
                    Segment(type="static", name="users"),
                    Segment(type="variable", name="user_id", variable_type="number")
                ],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("users/123", "GET", routes)
        assert result == {
            "route_id": "route1",
            "node_setup_version_id": "v1",
            "tenant_id": "tenant1",
            "variables": {"user_id": "123"}
        }
    
    def test_multiple_variables_extraction(self):
        routes = [
            Route(
                id="route1",
                method="POST",
                require_api_key=False,
                segments=[
                    Segment(type="static", name="projects"),
                    Segment(type="variable", name="project_id", variable_type="string"),
                    Segment(type="static", name="tasks"),
                    Segment(type="variable", name="task_id", variable_type="number")
                ],
                node_setup_version_id="v2",
                tenant_id="tenant2"
            )
        ]
        result = match_route("projects/abc/tasks/456", "POST", routes)
        assert result == {
            "route_id": "route1",
            "node_setup_version_id": "v2",
            "tenant_id": "tenant2",
            "variables": {"project_id": "abc", "task_id": "456"}
        }
    
    def test_case_insensitive_method_matching(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("api", "get", routes)
        assert result == {
            "route_id": "route1",
            "node_setup_version_id": "v1",
            "tenant_id": "tenant1",
            "variables": {}
        }
    
    def test_first_matching_route_wins(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            ),
            Route(
                id="route2",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v2",
                tenant_id="tenant2"
            )
        ]
        result = match_route("api", "GET", routes)
        assert result["route_id"] == "route1"
    
    def test_number_variable_type_validation(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[
                    Segment(type="static", name="users"),
                    Segment(type="variable", name="user_id", variable_type="number")
                ],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        # Should match numbers
        result = match_route("users/123", "GET", routes)
        assert result is not None
        
        # Should not match non-numbers
        result = match_route("users/abc", "GET", routes)
        assert result is None
    
    def test_uuid_variable_type_validation(self):
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[
                    Segment(type="static", name="users"),
                    Segment(type="variable", name="user_id", variable_type="uuid")
                ],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        # Should match UUID format
        result = match_route("users/550e8400-e29b-41d4-a716-446655440000", "GET", routes)
        assert result is not None

        # Should not match non-UUID
        result = match_route("users/123", "GET", routes)
        assert result is None


class TestMultipleMethodsSupport:
    """Tests for multiple HTTP methods per route (backwards compatible)."""

    def test_single_method_as_string(self):
        """Existing routes with method as string should still work."""
        routes = [
            Route(
                id="route1",
                method="GET",  # Single method as string
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("/api", "GET", routes)
        assert result is not None
        assert result["route_id"] == "route1"

    def test_single_method_as_string_no_match(self):
        """Single method as string should not match other methods."""
        routes = [
            Route(
                id="route1",
                method="GET",
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        result = match_route("/api", "POST", routes)
        assert result == "method_not_allowed"

    def test_multiple_methods_as_list(self):
        """Route with multiple methods should match all listed methods."""
        routes = [
            Route(
                id="route1",
                method=["GET", "POST"],  # Multiple methods as list
                require_api_key=False,
                segments=[Segment(type="static", name="webhooks")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        # GET should match
        result = match_route("/webhooks", "GET", routes)
        assert result is not None
        assert result["route_id"] == "route1"

        # POST should also match
        result = match_route("/webhooks", "POST", routes)
        assert result is not None
        assert result["route_id"] == "route1"

    def test_multiple_methods_no_match_unlisted_method(self):
        """Route with multiple methods should not match unlisted methods."""
        routes = [
            Route(
                id="route1",
                method=["GET", "POST"],
                require_api_key=False,
                segments=[Segment(type="static", name="webhooks")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        # DELETE is not in the list
        result = match_route("/webhooks", "DELETE", routes)
        assert result == "method_not_allowed"

    def test_multiple_methods_case_insensitive(self):
        """Method matching should be case insensitive."""
        routes = [
            Route(
                id="route1",
                method=["GET", "post"],  # Mixed case
                require_api_key=False,
                segments=[Segment(type="static", name="api")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        # Lowercase should match
        result = match_route("/api", "get", routes)
        assert result is not None

        # Uppercase should match
        result = match_route("/api", "POST", routes)
        assert result is not None

    def test_all_crud_methods(self):
        """Route can support all CRUD methods."""
        routes = [
            Route(
                id="route1",
                method=["GET", "POST", "PUT", "PATCH", "DELETE"],
                require_api_key=False,
                segments=[Segment(type="static", name="resources")],
                node_setup_version_id="v1",
                tenant_id="tenant1"
            )
        ]
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            result = match_route("/resources", method, routes)
            assert result is not None
            assert result["route_id"] == "route1"