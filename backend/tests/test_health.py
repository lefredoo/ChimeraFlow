"""
Test suite for health check endpoint
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    """Test /health endpoint returns 200 OK"""
    response = client.get("/health")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "chimeraflow-api"
    assert "version" in data


def test_root_endpoint():
    """Test / endpoint returns API info"""
    response = client.get("/")
    
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


def test_sources_endpoint(api_client):
    """Test /api/v1/sources endpoint (authenticated)"""
    response = api_client.get("/api/v1/sources")
    
    assert response.status_code == 200
    
    data = response.json()
    assert "sources" in data
    assert isinstance(data["sources"], list)
