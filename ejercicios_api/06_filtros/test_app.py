import os
import unittest
from unittest.mock import patch

from app import app


class ClientesApiTests(unittest.TestCase):
    def setUp(self):
        self.password_environment = patch.dict(
            os.environ, {"CLIENTES_PASSWORD": "test-password"}
        )
        self.password_environment.start()
        self.client = app.test_client()

    def tearDown(self):
        self.password_environment.stop()

    def test_customer_routes_require_api_key(self):
        response = self.client.get("/clientes")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "No autorizado."})

    def test_health_check(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_list_clients_and_nested_data(self):
        response = self.client.get(
            "/clientes", headers={"X-API-Key": "test-password"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 6)
        self.assertEqual(response.json[0]["informacion_personal"]["nombre"], "Ana")

    def test_filter_clients(self):
        response = self.client.get(
            "/clientes?q=tipo_cliente:empresa",
            headers={"X-API-Key": "test-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)
        self.assertTrue(
            all(
                cliente["segmentacion"]["tipo_cliente"] == "Empresa"
                for cliente in response.json
            )
        )

    def test_get_client_by_id(self):
        response = self.client.get(
            "/clientes/CLI-2026-123456",
            headers={"X-API-Key": "test-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["informacion_personal"]["nombre"], "Carlos")

    def test_unknown_client_returns_404(self):
        response = self.client.get(
            "/clientes/no-existe",
            headers={"X-API-Key": "test-password"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
