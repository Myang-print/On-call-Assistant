import logging

from fastapi.testclient import TestClient

from app.main import app


logger = logging.getLogger(__name__)


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    logger.info("health_status=%s body=%s", response.status_code, response.json())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
