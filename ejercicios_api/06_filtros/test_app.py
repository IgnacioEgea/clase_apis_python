import unittest

from app import app


class ClientesApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_check(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_list_clients_and_nested_data(self):
        response = self.client.get("/clientes")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 6)
        self.assertEqual(response.json[0]["informacion_personal"]["nombre"], "Ana")

    def test_filter_clients(self):
        response = self.client.get("/clientes?q=tipo_cliente:empresa")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)
        self.assertTrue(
            all(
                cliente["segmentacion"]["tipo_cliente"] == "Empresa"
                for cliente in response.json
            )
        )

    def test_get_client_by_id(self):
        response = self.client.get("/clientes/CLI-2026-123456")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["informacion_personal"]["nombre"], "Carlos")

    def test_unknown_client_returns_404(self):
        response = self.client.get("/clientes/no-existe")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
