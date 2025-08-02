import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestMainRouting:
    
    def setup_routes_in_db(self, mock_table):
        """Helper to set up test routes in mock DynamoDB"""
        mock_table.put_item(Item={
            "PK": "routing#test-project",
            "SK": "route#api-route",
            "method": "GET",
            "require_api_key": False,
            "segments": [
                {"type": "static", "name": "api", "variable_type": "any"},
                {"type": "variable", "name": "version", "variable_type": "string"}
            ],
            "node_setup_version_id": "v1",
            "tenant_id": "test-tenant",
            "active_stages": ["dev"]
        })
        
        mock_table.put_item(Item={
            "PK": "routing#test-project",
            "SK": "route#users-route",
            "method": "POST",
            "require_api_key": True,
            "segments": [
                {"type": "static", "name": "users", "variable_type": "any"},
                {"type": "variable", "name": "user_id", "variable_type": "number"}
            ],
            "node_setup_version_id": "v2",
            "tenant_id": "test-tenant",
            "active_stages": ["dev"]
        })
    
    def test_successful_route_matching_and_lambda_invocation(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            # Configure mock Lambda response
            lambda_response = {
                "statusCode": 200,
                "body": json.dumps({"message": "Hello from Lambda", "version": "v1.0"}),
                "headers": {"Content-Type": "application/json"}
            }
            mock_lambda_client.invoke.return_value = {
                'Payload': type('MockPayload', (), {
                    'read': lambda: json.dumps(lambda_response).encode('utf-8')
                })()
            }
            
            # Make request with proper subdomain
            response = test_client.get(
                "/api/v1",
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 200
            assert response.json() == {"message": "Hello from Lambda", "version": "v1.0"}
            
            # Verify Lambda was called with correct parameters
            mock_lambda_client.invoke.assert_called_once()
            call_args = mock_lambda_client.invoke.call_args
            
            assert call_args[1]["FunctionName"] == "node_setup_v1_dev"
            assert call_args[1]["InvocationType"] == "RequestResponse"
            
            # Verify payload structure
            payload = json.loads(call_args[1]["Payload"])
            assert payload["path"] == "/api/v1"
            assert payload["method"] == "GET"
            assert payload["project_id"] == "test-project"
            assert payload["stage"] == "dev"
            assert payload["tenant_id"] == "test-tenant"
            assert payload["variables"] == {"version": "v1"}
    
    def test_post_request_with_body(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            lambda_response = {
                "statusCode": 201,
                "body": json.dumps({"id": 123, "created": True}),
                "headers": {"Content-Type": "application/json"}
            }
            mock_lambda_client.invoke.return_value = {
                'Payload': type('MockPayload', (), {
                    'read': lambda: json.dumps(lambda_response).encode('utf-8')
                })()
            }
            
            request_body = {"name": "John Doe", "email": "john@example.com"}
            response = test_client.post(
                "/users/123",
                json=request_body,
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 201
            assert response.json() == {"id": 123, "created": True}
            
            # Verify Lambda payload includes body
            call_args = mock_lambda_client.invoke.call_args
            payload = json.loads(call_args[1]["Payload"])
            assert json.loads(payload["body"]) == request_body
    
    def test_route_not_found_returns_404(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            response = test_client.get(
                "/nonexistent/path",
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 404
            assert "Not found" in response.json()["detail"]
            
            # Lambda should not be called
            mock_lambda_client.invoke.assert_not_called()
    
    def test_method_not_allowed_returns_405(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            # Try DELETE on a GET-only route
            response = test_client.delete(
                "/api/v1",
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 405
            assert "Method Not Allowed" in response.json()["detail"]
            
            # Lambda should not be called
            mock_lambda_client.invoke.assert_not_called()
    
    def test_invalid_subdomain_returns_400(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            response = test_client.get(
                "/api/v1",
                headers={"host": "invalid-subdomain.example.com"}
            )
            
            assert response.status_code == 400
            assert "Invalid subdomain format" in response.json()["detail"]
    
    def test_lambda_invocation_failure_returns_500(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            # Configure Lambda to raise an exception
            mock_lambda_client.invoke.side_effect = Exception("Lambda service unavailable")
            
            response = test_client.get(
                "/api/v1",
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 500
            assert "Invocation failed" in response.json()["detail"]
    
    def test_lambda_returns_non_json_response(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            lambda_response = {
                "statusCode": 200,
                "body": "Plain text response",
                "headers": {"Content-Type": "text/plain"}
            }
            mock_lambda_client.invoke.return_value = {
                'Payload': type('MockPayload', (), {
                    'read': lambda: json.dumps(lambda_response).encode('utf-8')
                })()
            }
            
            response = test_client.get(
                "/api/v1",
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 200
            assert response.text == "Plain text response"
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    def test_lambda_returns_base64_encoded_response(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            import base64
            binary_data = b"Binary file content"
            encoded_data = base64.b64encode(binary_data).decode('utf-8')
            
            lambda_response = {
                "statusCode": 200,
                "body": encoded_data,
                "headers": {"Content-Type": "application/octet-stream"},
                "isBase64Encoded": True
            }
            mock_lambda_client.invoke.return_value = {
                'Payload': type('MockPayload', (), {
                    'read': lambda: json.dumps(lambda_response).encode('utf-8')
                })()
            }
            
            response = test_client.get(
                "/api/v1",
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 200
            assert response.content == binary_data
    
    def test_variable_extraction_with_numbers(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            lambda_response = {
                "statusCode": 200,
                "body": json.dumps({"user_id": 123}),
                "headers": {"Content-Type": "application/json"}
            }
            mock_lambda_client.invoke.return_value = {
                'Payload': type('MockPayload', (), {
                    'read': lambda: json.dumps(lambda_response).encode('utf-8')
                })()
            }
            
            response = test_client.post(
                "/users/123",
                json={"name": "Test User"},
                headers={"host": "test-project-dev.example.com"}
            )
            
            assert response.status_code == 200
            
            # Verify user_id variable was extracted correctly
            call_args = mock_lambda_client.invoke.call_args
            payload = json.loads(call_args[1]["Payload"])
            assert payload["variables"] == {"user_id": "123"}
    
    def test_health_endpoint_works_without_subdomain_parsing(self, test_client):
        response = test_client.get("/__internal/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    
    def test_malformed_lambda_response_handled_gracefully(self, test_client, mock_dynamodb_table, mock_lambda_client):
        with patch('routing.cache.table', mock_dynamodb_table):
            self.setup_routes_in_db(mock_dynamodb_table)
            
            # Lambda returns malformed JSON
            lambda_response = {
                "statusCode": 200,
                "body": '{"invalid": json content}',
                "headers": {"Content-Type": "application/json"}
            }
            mock_lambda_client.invoke.return_value = {
                'Payload': type('MockPayload', (), {
                    'read': lambda: json.dumps(lambda_response).encode('utf-8')
                })()
            }
            
            response = test_client.get(
                "/api/v1",
                headers={"host": "test-project-dev.example.com"}
            )
            
            # Should still return response even with malformed JSON
            assert response.status_code == 200
            assert response.text == '{"invalid": json content}'