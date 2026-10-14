import pytest
from fastapi.testclient import TestClient
from src.api.main import app, get_producer
from src.api.queue import MockQueueProducer

# Use MockQueueProducer for lightning-fast, isolated unit testing
mock_producer = MockQueueProducer()


def override_get_producer():
    return mock_producer


app.dependency_overrides[get_producer] = override_get_producer

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_queue():
    """Ensure queue is clean before each test execution."""
    mock_producer.clear()
    yield


def test_liveness_probe():
    """Verify /healthz returns 200 and accurate health schema."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert response.headers.get("X-Request-ID") is not None
    assert response.headers.get("X-Process-Time") is not None


def test_readiness_probe():
    """Verify /readyz returns 200 when dependencies are reachable."""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["dependencies"]["queue"] == "connected"


def test_ingest_single_event_success():
    """Verify valid event is accepted and queued."""
    payload = {
        "tenant_id": "tenant_enterprise_01",
        "event_type": "user.signup",
        "user_id": "usr_abc123",
        "properties": {
            "plan": "growth",
            "source": "google_ads",
            "mrr": 299.0
        }
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["events_queued"] == 1
    assert "request_id" in data
    assert len(mock_producer.messages) == 1
    assert mock_producer.messages[0]["tenant_id"] == "tenant_enterprise_01"


def test_ingest_single_event_validation_failure():
    """Verify malformed payloads are rejected with 422 before reaching the queue."""
    # Invalid tenant_id (spaces and symbols not allowed)
    payload = {
        "tenant_id": "invalid tenant id with spaces!!",
        "event_type": "user.signup",
        "properties": {}
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 422
    assert len(mock_producer.messages) == 0  # Nothing buffered into queue


def test_ingest_batch_events_success():
    """Verify batch of valid events is enqueued efficiently."""
    payload = {
        "events": [
            {
                "tenant_id": "tenant_123",
                "event_type": "page.view",
                "properties": {"path": "/dashboard"}
            },
            {
                "tenant_id": "tenant_123",
                "event_type": "button.click",
                "properties": {"button_id": "export_csv"}
            }
        ]
    }
    response = client.post("/api/v1/events/batch", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["events_queued"] == 2
    assert len(mock_producer.messages) == 2


def test_ingest_batch_empty_failure():
    """Verify empty batch is rejected (must have at least 1 event)."""
    payload = {"events": []}
    response = client.post("/api/v1/events/batch", json=payload)
    assert response.status_code == 422
