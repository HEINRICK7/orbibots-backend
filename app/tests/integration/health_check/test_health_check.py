import unittest

from fastapi.testclient import TestClient

from app.src.infra.entrypoints.app import create_app
from app.src.infra.setup.settings import Settings


class HealthCheckIntegrationTests(unittest.TestCase):
    def test_health_endpoint_is_public_and_returns_existing_contract(self) -> None:
        with TestClient(create_app(Settings(app_env="test"))) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
