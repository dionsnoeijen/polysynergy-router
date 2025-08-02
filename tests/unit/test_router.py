import pytest
from fastapi import HTTPException
from api.router import parse_subdomain


class TestParseSubdomain:
    
    def test_valid_subdomain_parsing(self):
        result = parse_subdomain("project123-dev.example.com")
        assert result == ("project123", "dev")
    
    def test_valid_subdomain_with_hyphens_in_project_id(self):
        result = parse_subdomain("my-project-123-prod.example.com")
        assert result == ("my-project-123", "prod")
    
    def test_valid_subdomain_staging_environment(self):
        result = parse_subdomain("ecommerce-staging.example.com")
        assert result == ("ecommerce", "staging")
    
    def test_valid_subdomain_test_environment(self):
        result = parse_subdomain("api-gateway-test.example.com")
        assert result == ("api-gateway", "test")
    
    def test_subdomain_without_stage_raises_exception(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_subdomain("justproject.example.com")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid subdomain format"
    
    def test_empty_subdomain_raises_exception(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_subdomain("example.com")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid subdomain format"
    
    def test_malformed_subdomain_raises_exception(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_subdomain("invalid")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid subdomain format"
    
    def test_subdomain_with_only_hyphen_allows_empty_components(self):
        # Current implementation allows empty project_id and stage
        result = parse_subdomain("-")
        assert result == ("", "")
    
    def test_subdomain_ending_with_hyphen_allows_empty_stage(self):
        # Current implementation allows empty stage
        result = parse_subdomain("project-.example.com")
        assert result == ("project", "")
    
    def test_subdomain_starting_with_hyphen_allows_empty_project_id(self):
        # Current implementation allows empty project_id
        result = parse_subdomain("-dev.example.com")
        assert result == ("", "dev")
    
    def test_complex_domain_parsing(self):
        result = parse_subdomain("my-complex-project-production.api.company.co.uk")
        assert result == ("my-complex-project", "production")
    
    def test_numeric_project_and_stage(self):
        result = parse_subdomain("123-456.example.com")
        assert result == ("123", "456")
    
    def test_single_character_components(self):
        result = parse_subdomain("a-b.example.com")
        assert result == ("a", "b")