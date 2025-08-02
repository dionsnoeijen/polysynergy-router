import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import json


@pytest.mark.integration
class TestCrudOperations:
    
    def test_update_route_creates_new_route(self, test_client, mock_dynamodb_table, sample_route_data):
        with patch('api.crud.table', mock_dynamodb_table):
            response = test_client.post("/__internal/update-route", json=sample_route_data)
            
            assert response.status_code == 200
            assert response.json() == {"message": "Route updated successfully."}
            
            # Verify the route was stored in DynamoDB
            item = mock_dynamodb_table.get_item(
                Key={
                    "PK": "routing#test-project",
                    "SK": "route#test-route-1"
                }
            )
            
            assert "Item" in item
            stored_item = item["Item"]
            assert stored_item["method"] == "GET"
            assert stored_item["require_api_key"] is False
            assert stored_item["node_setup_version_id"] == "v1"
            assert stored_item["tenant_id"] == "test-tenant"
            assert "dev" in stored_item["active_stages"]
    
    def test_update_route_adds_stage_to_existing_route(self, test_client, mock_dynamodb_table, sample_route_data):
        with patch('api.crud.table', mock_dynamodb_table):
            # First create the route
            response1 = test_client.post("/__internal/update-route", json=sample_route_data)
            assert response1.status_code == 200
            
            # Update the same route for a different stage
            sample_route_data["stage"] = "prod"
            response2 = test_client.post("/__internal/update-route", json=sample_route_data)
            assert response2.status_code == 200
            
            # Verify both stages are active
            item = mock_dynamodb_table.get_item(
                Key={
                    "PK": "routing#test-project",
                    "SK": "route#test-route-1"
                }
            )
            
            stored_item = item["Item"]
            assert set(stored_item["active_stages"]) == {"dev", "prod"}
    
    def test_deactivate_route_removes_stage(self, test_client, mock_dynamodb_table, sample_route_data):
        with patch('api.crud.table', mock_dynamodb_table):
            # Create route with multiple stages
            test_client.post("/__internal/update-route", json=sample_route_data)
            sample_route_data["stage"] = "prod"
            test_client.post("/__internal/update-route", json=sample_route_data)
            
            # Deactivate one stage
            deactivate_data = {
                "project_id": "test-project",
                "stage": "dev",
                "route": {"id": "test-route-1"}
            }
            
            response = test_client.post("/__internal/deactivate-route", json=deactivate_data)
            assert response.status_code == 200
            assert "dev" in response.json()["message"]
            
            # Verify only prod stage remains
            item = mock_dynamodb_table.get_item(
                Key={
                    "PK": "routing#test-project",
                    "SK": "route#test-route-1"
                }
            )
            
            stored_item = item["Item"]
            assert stored_item["active_stages"] == ["prod"]
    
    def test_deactivate_route_deletes_when_no_stages_remain(self, test_client, mock_dynamodb_table, sample_route_data):
        with patch('api.crud.table', mock_dynamodb_table):
            # Create route with single stage
            test_client.post("/__internal/update-route", json=sample_route_data)
            
            # Deactivate the only stage
            deactivate_data = {
                "project_id": "test-project",
                "stage": "dev",
                "route": {"id": "test-route-1"}
            }
            
            response = test_client.post("/__internal/deactivate-route", json=deactivate_data)
            assert response.status_code == 200
            
            # Verify route is deleted
            item = mock_dynamodb_table.get_item(
                Key={
                    "PK": "routing#test-project",
                    "SK": "route#test-route-1"
                }
            )
            
            assert "Item" not in item
    
    def test_deactivate_nonexistent_route_returns_404(self, test_client, mock_dynamodb_table):
        with patch('api.crud.table', mock_dynamodb_table):
            deactivate_data = {
                "project_id": "test-project",
                "stage": "dev",
                "route": {"id": "nonexistent-route"}
            }
            
            response = test_client.post("/__internal/deactivate-route", json=deactivate_data)
            assert response.status_code == 404
            assert "Route not found" in response.json()["detail"]
    
    def test_delete_route_removes_entire_route(self, test_client, mock_dynamodb_table, sample_route_data):
        with patch('api.crud.table', mock_dynamodb_table):
            # Create route with multiple stages
            test_client.post("/__internal/update-route", json=sample_route_data)
            sample_route_data["stage"] = "prod"
            test_client.post("/__internal/update-route", json=sample_route_data)
            
            # Delete entire route
            delete_data = {
                "project_id": "test-project",
                "route": {"id": "test-route-1"}
            }
            
            response = test_client.delete("/__internal/delete-route", json=delete_data)
            assert response.status_code == 200
            assert response.json() == {"message": "Route deleted successfully."}
            
            # Verify route is completely deleted
            item = mock_dynamodb_table.get_item(
                Key={
                    "PK": "routing#test-project",
                    "SK": "route#test-route-1"
                }
            )
            
            assert "Item" not in item
    
    def test_get_routes_returns_project_routes(self, test_client, mock_dynamodb_table, sample_route_data):
        with patch('api.crud.table', mock_dynamodb_table):
            # Create multiple routes
            test_client.post("/__internal/update-route", json=sample_route_data)
            
            sample_route_data["route"]["id"] = "test-route-2"
            sample_route_data["route"]["method"] = "POST"
            test_client.post("/__internal/update-route", json=sample_route_data)
            
            response = test_client.get("/__internal/routes/test-project")
            assert response.status_code == 200
            
            routes = response.json()
            assert len(routes) == 2
            
            route_ids = [route["SK"].split("#")[1] for route in routes]
            assert "test-route-1" in route_ids
            assert "test-route-2" in route_ids
    
    def test_get_routes_empty_project_returns_empty_list(self, test_client, mock_dynamodb_table):
        with patch('api.crud.table', mock_dynamodb_table):
            response = test_client.get("/__internal/routes/empty-project")
            assert response.status_code == 200
            assert response.json() == []
    
    def test_invalid_route_data_returns_422(self, test_client, mock_dynamodb_table):
        with patch('api.crud.table', mock_dynamodb_table):
            invalid_data = {
                "project_id": "test-project",
                "tenant_id": "test-tenant",
                "stage": "dev",
                "route": {
                    "id": "test-route-1",
                    "method": "INVALID_METHOD",  # Invalid HTTP method
                    "require_api_key": False,
                    "segments": [],
                    "node_setup_version_id": "v1",
                    "tenant_id": "test-tenant"
                }
            }
            
            response = test_client.post("/__internal/update-route", json=invalid_data)
            assert response.status_code == 422