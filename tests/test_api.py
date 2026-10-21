from fastapi.testclient import TestClient

from backend.main import app


def test_health_and_report_endpoints():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["creation_count"] == 1

        reports = client.get("/api/reports")
        assert reports.status_code == 200
        report_ids = {report["id"] for report in reports.json()["reports"]}
        assert {
            "sample-semiconductor-2026",
            "sample-game-2026",
            "sample-battery-2026",
        } <= report_ids

        missing = client.get("/api/reports/missing")
        assert missing.status_code == 404


def test_short_question_is_rejected_before_model_call():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "a"})
        assert response.status_code == 422


def test_stream_endpoint_rejects_short_question():
    with TestClient(app) as client:
        response = client.post("/api/chat/stream", json={"message": "a"})
        assert response.status_code == 422
