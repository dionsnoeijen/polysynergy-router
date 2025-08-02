import pytest
import os
from moto import mock_aws
import boto3
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def mock_aws_credentials():
    """Mock AWS credentials for testing"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['AWS_REGION'] = 'us-east-1'


@pytest.fixture
def mock_dynamodb_table(mock_aws_credentials):
    """Create a mock DynamoDB table for testing"""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        table = dynamodb.create_table(
            TableName='poly_router_routing',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        
        yield table


@pytest.fixture
def sample_route_data():
    """Sample route data for testing"""
    return {
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "stage": "dev",
        "route": {
            "id": "test-route-1",
            "method": "GET",
            "require_api_key": False,
            "segments": [
                {"type": "static", "name": "api", "variable_type": "any"},
                {"type": "variable", "name": "version", "variable_type": "string"}
            ],
            "node_setup_version_id": "v1",
            "tenant_id": "test-tenant"
        }
    }


@pytest.fixture
def mock_lambda_client():
    """Mock AWS Lambda client for testing"""
    with patch('api.router.lambda_client') as mock_client:
        mock_response = {
            'Payload': type('MockPayload', (), {
                'read': lambda: b'{"statusCode": 200, "body": "{\\"message\\": \\"success\\"}", "headers": {"Content-Type": "application/json"}}'
            })()
        }
        mock_client.invoke.return_value = mock_response
        yield mock_client


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear routing cache before each test"""
    from routing.cache import routing_cache
    routing_cache.clear()
    yield
    routing_cache.clear()