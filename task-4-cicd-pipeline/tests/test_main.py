"""
Tests for the Task 4 Flask health-check application.
"""

import sys
import os

# Ensure the app package is importable when running from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.main import app


@pytest.fixture
def client():
    """Configure the Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_status_code(client):
    """GET /health must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_fields(client):
    """GET /health must return the expected JSON fields and values."""
    response = client.get("/health")
    data = response.get_json()

    assert data is not None, "Response body must be valid JSON"
    assert "status" in data, "Response must contain 'status' field"
    assert "service" in data, "Response must contain 'service' field"
    assert data["status"] == "ok"
    assert data["service"] == "task-4-cicd-pipeline"


def test_health_content_type(client):
    """GET /health must return application/json content type."""
    response = client.get("/health")
    assert response.content_type.startswith("application/json")
