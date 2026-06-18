from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tms-agent-phase0-day1",
    }


def test_openapi_docs_are_available() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_valid_runtime_input_is_accepted() -> None:
    response = client.post(
        "/api/v1/device-status",
        json={
            "device_id": "device-001",
            "region": "south_china",
            "android_version": "11",
            "firmware_version": "2.4.1",
            "online": True,
            "error_code": None,
            "failure_rate_7d": 0.05,
            "last_seen_at": "2026-06-08T08:00:00+00:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_invalid_runtime_input_is_rejected_before_route_execution() -> None:
    response = client.post(
        "/api/v1/ott-queries",
        json={
            "query_id": "query-001",
            "tenant_id": "",
            "query_text": "卡顿",
            "channel": "phone",
            "include_history": False,
            "max_results": 21,
        },
    )

    assert response.status_code == 422
    assert len(response.json()["detail"]) >= 3
