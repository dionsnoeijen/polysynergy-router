import pytest
from unittest.mock import Mock, patch, MagicMock
from routing.cache import get_routes, routing_cache
from models.route import Route, Segment


class TestRoutingCache:
    
    def setup_method(self):
        routing_cache.clear()
    
    def teardown_method(self):
        routing_cache.clear()
    
    @patch('routing.cache.table')
    def test_get_routes_from_dynamodb_when_not_cached(self, mock_table):
        mock_response = {
            'Items': [
                {
                    'SK': 'route#route1',
                    'method': 'GET',
                    'require_api_key': False,
                    'segments': [{'type': 'static', 'name': 'api', 'variable_type': 'any'}],
                    'node_setup_version_id': 'v1',
                    'tenant_id': 'tenant1',
                    'active_stages': ['dev', 'prod']
                },
                {
                    'SK': 'route#route2',
                    'method': 'POST',
                    'require_api_key': True,
                    'segments': [
                        {'type': 'static', 'name': 'users', 'variable_type': 'any'},
                        {'type': 'variable', 'name': 'id', 'variable_type': 'number'}
                    ],
                    'node_setup_version_id': 'v2',
                    'tenant_id': 'tenant2',
                    'active_stages': ['dev']
                }
            ]
        }
        mock_table.query.return_value = mock_response
        
        result = get_routes("project1", "dev")
        
        assert len(result) == 2
        assert result[0].id == "route1"
        assert result[0].method == "GET"
        assert result[0].require_api_key is False
        assert result[0].node_setup_version_id == "v1"
        assert result[0].tenant_id == "tenant1"
        
        assert result[1].id == "route2"
        assert result[1].method == "POST"
        assert result[1].require_api_key is True
        assert result[1].node_setup_version_id == "v2"
        assert result[1].tenant_id == "tenant2"
        
        mock_table.query.assert_called_once()
    
    @patch('routing.cache.table')
    def test_get_routes_filters_by_active_stage(self, mock_table):
        mock_response = {
            'Items': [
                {
                    'SK': 'route#route1',
                    'method': 'GET',
                    'require_api_key': False,
                    'segments': [{'type': 'static', 'name': 'api', 'variable_type': 'any'}],
                    'node_setup_version_id': 'v1',
                    'tenant_id': 'tenant1',
                    'active_stages': ['dev']
                },
                {
                    'SK': 'route#route2',
                    'method': 'POST',
                    'require_api_key': True,
                    'segments': [{'type': 'static', 'name': 'users', 'variable_type': 'any'}],
                    'node_setup_version_id': 'v2',
                    'tenant_id': 'tenant2',
                    'active_stages': ['prod']
                }
            ]
        }
        mock_table.query.return_value = mock_response
        
        result = get_routes("project1", "dev")
        
        assert len(result) == 1
        assert result[0].id == "route1"
    
    @patch('routing.cache.table')
    def test_get_routes_returns_cached_data_on_subsequent_calls(self, mock_table):
        mock_response = {
            'Items': [
                {
                    'SK': 'route#route1',
                    'method': 'GET',
                    'require_api_key': False,
                    'segments': [{'type': 'static', 'name': 'api', 'variable_type': 'any'}],
                    'node_setup_version_id': 'v1',
                    'tenant_id': 'tenant1',
                    'active_stages': ['dev']
                }
            ]
        }
        mock_table.query.return_value = mock_response
        
        # First call should hit DynamoDB
        result1 = get_routes("project1", "dev")
        
        # Second call should use cache
        result2 = get_routes("project1", "dev")
        
        # Should only query DynamoDB once
        mock_table.query.assert_called_once()
        
        # Results should be identical
        assert len(result1) == len(result2) == 1
        assert result1[0].id == result2[0].id == "route1"
    
    @patch('routing.cache.table')
    def test_get_routes_handles_empty_response(self, mock_table):
        mock_response = {'Items': []}
        mock_table.query.return_value = mock_response
        
        result = get_routes("project1", "dev")
        
        assert result == []
        assert ("project1", "dev") in routing_cache
    
    @patch('routing.cache.table')
    def test_cache_key_separation_by_project_and_stage(self, mock_table):
        mock_response = {
            'Items': [
                {
                    'SK': 'route#route1',
                    'method': 'GET',
                    'require_api_key': False,
                    'segments': [{'type': 'static', 'name': 'api', 'variable_type': 'any'}],
                    'node_setup_version_id': 'v1',
                    'tenant_id': 'tenant1',
                    'active_stages': ['dev']
                }
            ]
        }
        mock_table.query.return_value = mock_response
        
        # Different project/stage combinations should be cached separately
        get_routes("project1", "dev")
        get_routes("project1", "prod")
        get_routes("project2", "dev")
        
        assert ("project1", "dev") in routing_cache
        assert ("project1", "prod") in routing_cache
        assert ("project2", "dev") in routing_cache
        
        # Should make 3 separate DynamoDB calls
        assert mock_table.query.call_count == 3
    
    @patch('routing.cache.table')
    def test_segment_parsing_from_dynamodb_item(self, mock_table):
        mock_response = {
            'Items': [
                {
                    'SK': 'route#route1',
                    'method': 'GET',
                    'require_api_key': False,
                    'segments': [
                        {'type': 'static', 'name': 'api', 'variable_type': 'any'},
                        {'type': 'variable', 'name': 'version', 'variable_type': 'string'},
                        {'type': 'variable', 'name': 'id', 'variable_type': 'number'}
                    ],
                    'node_setup_version_id': 'v1',
                    'tenant_id': 'tenant1',
                    'active_stages': ['dev']
                }
            ]
        }
        mock_table.query.return_value = mock_response
        
        result = get_routes("project1", "dev")
        
        assert len(result) == 1
        route = result[0]
        assert len(route.segments) == 3
        
        assert route.segments[0].type == "static"
        assert route.segments[0].name == "api"
        
        assert route.segments[1].type == "variable"
        assert route.segments[1].name == "version"
        assert route.segments[1].variable_type == "string"
        
        assert route.segments[2].type == "variable"
        assert route.segments[2].name == "id"
        assert route.segments[2].variable_type == "number"