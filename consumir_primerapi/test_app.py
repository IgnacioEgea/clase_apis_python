import unittest

from app import procesar_clientes


class ProcesarClientesTests(unittest.TestCase):
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
