import pytest
from routing.request_parser import parse_request, ParsedRequest


class TestParseRequest:
    """Tests for the request parser that extracts project_id, stage, and path."""

    def test_valid_subdomain_parsing(self):
        result = parse_request("project123-dev.example.com", "/api/users")
        assert result is not None
        assert result.project_id == "project123"
        assert result.stage == "dev"
        assert result.path == "/api/users"
        assert result.routing_method == "subdomain"

    def test_valid_subdomain_with_hyphens_in_project_id(self):
        result = parse_request("my-project-123-prod.example.com", "/api")
        assert result is not None
        assert result.project_id == "my-project-123"
        assert result.stage == "prod"

    def test_valid_subdomain_staging_environment(self):
        result = parse_request("ecommerce-staging.example.com", "/")
        assert result is not None
        assert result.project_id == "ecommerce"
        assert result.stage == "staging"

    def test_valid_subdomain_test_environment(self):
        result = parse_request("api-gateway-test.example.com", "/health")
        assert result is not None
        assert result.project_id == "api-gateway"
        assert result.stage == "test"

    def test_subdomain_without_stage_returns_none(self):
        # Single component subdomain doesn't match pattern
        result = parse_request("justproject.example.com", "/api")
        # This should fall back to path-based, but /api isn't valid path-based either
        assert result is None

    def test_empty_subdomain_returns_none(self):
        result = parse_request("example.com", "/api/users")
        assert result is None

    def test_path_based_routing(self):
        result = parse_request("example.com", "/myproject/dev/api/users")
        assert result is not None
        assert result.project_id == "myproject"
        assert result.stage == "dev"
        assert result.path == "/api/users"
        assert result.routing_method == "path"

    def test_path_based_root_path(self):
        result = parse_request("example.com", "/project/prod/")
        assert result is not None
        assert result.project_id == "project"
        assert result.stage == "prod"
        assert result.path == "/"

    def test_complex_domain_parsing(self):
        result = parse_request("my-complex-project-production.api.company.co.uk", "/api")
        assert result is not None
        assert result.project_id == "my-complex-project"
        assert result.stage == "production"

    def test_localhost_with_port(self):
        result = parse_request("project-dev.localhost:8080", "/api/test")
        assert result is not None
        assert result.project_id == "project"
        assert result.stage == "dev"
        assert result.path == "/api/test"

    def test_numeric_project_and_stage(self):
        result = parse_request("123-456.example.com", "/test")
        assert result is not None
        assert result.project_id == "123"
        assert result.stage == "456"

    def test_single_character_components(self):
        result = parse_request("a-b.example.com", "/")
        assert result is not None
        assert result.project_id == "a"
        assert result.stage == "b"
