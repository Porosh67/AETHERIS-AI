"""
AETHERIS AI — FastAPI Integration Tests
Tests API endpoints: health, incidents CRUD, evidence verify, taxonomy.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Use in-memory SQLite for tests
from backend.app.models.db_models import (
    IncidentRecord, BobActivityLog, PatchRecord, EvidenceRecord, StateTransitionLog
)


def make_test_app():
    """Create a test FastAPI app with in-memory database."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    # Patch the database module to use test engine
    import backend.app.db.database as db_module
    original_engine = db_module.engine
    db_module.engine = test_engine

    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=True)

    def cleanup():
        db_module.engine = original_engine

    return client, cleanup


@pytest.fixture
def client():
    c, cleanup = make_test_app()
    yield c
    cleanup()


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "inference_mode" in data

    def test_health_has_watsonx_flag(self, client):
        resp = client.get("/health")
        assert "watsonx_configured" in resp.json()


class TestTaxonomy:
    def test_taxonomy_returns_categories(self, client):
        resp = client.get("/api/taxonomy")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "NULL_ERROR" in data["categories"]

    def test_taxonomy_returns_services(self, client):
        resp = client.get("/api/taxonomy")
        data = resp.json()
        assert "services" in data
        assert "orders-service" in data["services"]


class TestIncidentCRUD:
    def _create_payload(self):
        return {
            "incident_id": "INC-API-001",
            "title": "Test incident",
            "category": "NULL_ERROR",
            "severity": "HIGH",
            "service": "orders-service",
            "error_trace": "NullPointerException at line 87",
        }

    def test_create_incident_returns_201(self, client):
        resp = client.post("/api/incidents", json=self._create_payload())
        assert resp.status_code == 201

    def test_create_incident_returns_fields(self, client):
        resp = client.post("/api/incidents", json=self._create_payload())
        data = resp.json()
        assert data["incident_id"] == "INC-API-001"
        assert data["state"] == "IDLE"
        assert data["attempt_count"] == 0

    def test_create_incident_invalid_category_rejects(self, client):
        payload = self._create_payload()
        payload["category"] = "UNKNOWN_CATEGORY"
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_incident_invalid_service_rejects(self, client):
        payload = self._create_payload()
        payload["service"] = "secret-admin-service"
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_get_incident(self, client):
        created = client.post("/api/incidents", json=self._create_payload()).json()
        pk = created["id"]
        resp = client.get(f"/api/incidents/{pk}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pk

    def test_get_nonexistent_incident_404(self, client):
        resp = client.get("/api/incidents/does-not-exist")
        assert resp.status_code == 404

    def test_list_incidents(self, client):
        client.post("/api/incidents", json=self._create_payload())
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_reset_incident(self, client):
        created = client.post("/api/incidents", json=self._create_payload()).json()
        pk = created["id"]
        resp = client.delete(f"/api/incidents/{pk}/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"


class TestScenarios:
    def test_scenarios_endpoint_returns_list(self, client):
        resp = client.get("/api/scenarios")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestDataEndpoints:
    def test_data_incidents_returns_list(self, client):
        resp = client.get("/api/data/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_data_telemetry_returns_list(self, client):
        resp = client.get("/api/data/telemetry")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
