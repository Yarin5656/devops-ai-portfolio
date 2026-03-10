"""
Tests for the Incident Response API.

Uses FastAPI's TestClient (backed by httpx) so no running server is required.
All tests run in rule-based mode by design — AI enrichment is not activated
unless ANTHROPIC_API_KEY is present in the environment, so tests remain
deterministic and free of external dependencies.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import Category, Severity, AnalysisMode

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_body_contains_ok(self):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /analyze-incident — happy path
# ---------------------------------------------------------------------------

class TestAnalyzeIncident:

    def _post(self, payload: dict):
        return client.post("/analyze-incident", json=payload)

    def test_network_incident_classified_correctly(self):
        response = self._post({
            "source": "nginx",
            "environment": "staging",
            "log": "connection refused to upstream service",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.NETWORK.value
        assert body["severity"] in [s.value for s in Severity]
        assert body["analysis_mode"] == AnalysisMode.RULE_BASED.value

    def test_permissions_incident(self):
        response = self._post({
            "source": "app-server",
            "environment": "production",
            "log": "permission denied reading /etc/ssl/private/server.key",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.PERMISSIONS.value
        assert body["severity"] == Severity.HIGH.value

    def test_timeout_incident(self):
        response = self._post({
            "source": "payment-service",
            "environment": "production",
            "log": "upstream read timeout after 30s waiting for response",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.TIMEOUT.value

    def test_dependency_incident(self):
        response = self._post({
            "source": "worker",
            "environment": "dev",
            "log": "ModuleNotFoundError: No module named 'boto3'",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.DEPENDENCY.value

    def test_resource_incident(self):
        response = self._post({
            "source": "api-gateway",
            "environment": "production",
            "log": "OOM killer invoked: out of memory, process killed",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.RESOURCE.value
        assert body["severity"] == Severity.CRITICAL.value

    def test_unknown_incident_falls_back(self):
        response = self._post({
            "source": "cron",
            "environment": "staging",
            "log": "job finished with unexpected exit code 42",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.UNKNOWN.value

    def test_response_contains_all_required_fields(self):
        response = self._post({
            "source": "nginx",
            "environment": "staging",
            "log": "connection refused to upstream service",
        })
        body = response.json()
        required_fields = {
            "category", "severity", "root_cause",
            "recommended_fix", "runbook_steps", "analysis_mode",
            "source", "environment",
        }
        assert required_fields.issubset(body.keys())

    def test_runbook_steps_are_non_empty_list(self):
        response = self._post({
            "source": "nginx",
            "environment": "staging",
            "log": "connection refused to upstream service",
        })
        body = response.json()
        assert isinstance(body["runbook_steps"], list)
        assert len(body["runbook_steps"]) > 0

    def test_source_and_environment_echoed_in_response(self):
        response = self._post({
            "source": "my-service",
            "environment": "prod",
            "log": "disk full: no space left on device",
        })
        body = response.json()
        assert body["source"] == "my-service"
        assert body["environment"] == "prod"

    def test_optional_metadata_accepted(self):
        response = self._post({
            "source": "nginx",
            "environment": "staging",
            "log": "connection refused",
            "metadata": {"host": "web-01", "pod": "nginx-abc123"},
        })
        assert response.status_code == 200

    def test_missing_required_field_returns_422(self):
        response = self._post({
            "source": "nginx",
            "environment": "staging",
            # log is missing
        })
        assert response.status_code == 422

    def test_database_source_escalates_dependency_severity(self):
        """Dependency incidents on database sources should be escalated to HIGH."""
        response = self._post({
            "source": "postgres",
            "environment": "production",
            "log": "dependency resolution failed: missing shared library libssl.so.1.1",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == Category.DEPENDENCY.value
        assert body["severity"] == Severity.HIGH.value
