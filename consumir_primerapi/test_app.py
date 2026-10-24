import os
import unittest
from unittest.mock import MagicMock, patch

from app import obtener_clientes, procesar_clientes


class ProcesarClientesTests(unittest.TestCase):
    @patch.dict(os.environ, {"CLIENTES_PASSWORD": "test-password"})
    @patch("app.requests.get")
    def test_obtener_clientes_envia_clave_por_encabezado(self, mock_get):
        response = MagicMock()
        response.json.return_value = []
        mock_get.return_value = response

        self.assertEqual(obtener_clientes("https://api.example/clientes"), [])

        mock_get.assert_called_once_with(
            "https://api.example/clientes",
            headers={"X-API-Key": "test-password"},
            timeout=15,
        )
        response.raise_for_status.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_obtener_clientes_requiere_clave(self):
        with self.assertRaisesRegex(ValueError, "CLIENTES_PASSWORD"):
            obtener_clientes("https://api.example/clientes")

    def test_normalizes_and_calculates_indicators(self):
        raw_data = [
            {
                "id_cliente": "CLI-TEST-1",
                "informacion_personal": {"nombre": "Ada", "apellido": "Lovelace"},
                "productos_activos": {"prestamos_vigentes": 2},
                "segmentacion": {
                    "nivel_ingresos_anual": 40000,
                    "score_crediticio_interno": 750,
                    "tipo_cliente": "Particular",
                },
            }
        ]

        result = procesar_clientes(raw_data).iloc[0]

        self.assertEqual(result["nombre_completo"], "Ada Lovelace")
        self.assertAlmostEqual(result["ratio_endeudamiento"], 2 / 40000)
        self.assertEqual(result["indice_salud_crediticia"], 75)

    def test_rejects_zero_annual_income(self):
        raw_data = [
            {
                "informacion_personal": {"nombre": "Ada", "apellido": "Lovelace"},
                "productos_activos": {"prestamos_vigentes": 0},
                "segmentacion": {
                    "nivel_ingresos_anual": 0,
                    "score_crediticio_interno": 750,
                    "tipo_cliente": "Particular",
                },
            }
        ]

        with self.assertRaisesRegex(ValueError, "mayores que cero"):
            procesar_clientes(raw_data)

    def test_rejects_score_outside_expected_scale(self):
        raw_data = [
            {
                "informacion_personal": {"nombre": "Ada", "apellido": "Lovelace"},
                "productos_activos": {"prestamos_vigentes": 0},
                "segmentacion": {
                    "nivel_ingresos_anual": 40000,
                    "score_crediticio_interno": 1001,
                    "tipo_cliente": "Particular",
                },
            }
        ]

        with self.assertRaisesRegex(ValueError, "entre 0 y 1000"):
            procesar_clientes(raw_data)


if __name__ == "__main__":
    unittest.main()
