import unittest

import numpy as np
import pandas as pd

from pipeline_meteorologico import (
    añadir_estimaciones_temperatura,
    enriquecer_datos,
    generar_resumenes,
    limpiar_datos_meteorologicos,
)


class PipelineTests(unittest.TestCase):
    def test_cleaning_converts_units_and_keeps_best_duplicate(self):
        dataframe = pd.DataFrame(
            [
                {
                    "city_name": "Madrid",
                    "year": "2024",
                    "month": "1",
                    "metrics.temperature.max": "68,0",
                    "metrics.temperature.avg": "59,0",
                    "metrics.temperature.min": "50,0",
                    "metrics.temperature.unit": "F",
                    "metrics.precipitation.avg": "1.0",
                    "metrics.precipitation.unit": "inches",
                },
                {
                    "city_name": "Madrid",
                    "year": "2024",
                    "month": "1",
                    "metrics.temperature.max": "-999.0",
                    "metrics.temperature.avg": "59,0",
                    "metrics.temperature.min": "50,0",
                    "metrics.temperature.unit": "F",
                    "metrics.precipitation.avg": "1.0",
                    "metrics.precipitation.unit": "inches",
                },
                {
                    "city_name": "Madrid",
                    "year": "2024",
                    "month": "2",
                    "metrics.temperature.max": "-999.0",
                    "metrics.temperature.avg": "50,0",
                    "metrics.temperature.min": "32,0",
                    "metrics.temperature.unit": "F",
                    "metrics.precipitation.avg": "0.5",
                    "metrics.precipitation.unit": "inches",
                },
            ]
        )

        cleaned, initial_count = limpiar_datos_meteorologicos(dataframe)

        self.assertEqual(initial_count, 3)
        self.assertEqual(len(cleaned), 2)
        january = cleaned.loc[cleaned["month"].eq(1)].iloc[0]
        february = cleaned.loc[cleaned["month"].eq(2)].iloc[0]
        self.assertAlmostEqual(january["metrics.temperature.max"], 20)
        self.assertAlmostEqual(january["metrics.temperature.avg"], 15)
        self.assertAlmostEqual(january["metrics.temperature.min"], 10)
        self.assertEqual(january["metrics.temperature.unit"], "C")
        self.assertAlmostEqual(january["metrics.precipitation.avg"], 25.4)
        self.assertEqual(january["metrics.precipitation.unit"], "mm")
        self.assertTrue(pd.isna(february["metrics.temperature.max"]))

    def test_forecasts_are_unique_and_means_use_real_rows_only(self):
        index = pd.MultiIndex.from_product(
            [["Madrid", "Londres"], [2018, 2019, 2020], range(1, 13)],
            names=["city_name", "year", "month"],
        )
        dataframe = index.to_frame(index=False)
        dataframe["city"] = dataframe["city_name"]
        dataframe["metrics.temperature.unit"] = "C"
        dataframe["metrics.precipitation.unit"] = "mm"
        dataframe["metrics.temperature.max"] = (
            20
            + 2 * (dataframe["year"] - 2018)
            + dataframe["month"] / 10
            + np.where(dataframe["year"].eq(2019), 1, 0)
            + np.where(dataframe["city_name"].eq("Londres"), 3, 0)
        )
        dataframe["metrics.temperature.avg"] = dataframe["metrics.temperature.max"] - 5
        dataframe["metrics.temperature.min"] = dataframe["metrics.temperature.max"] - 10
        dataframe["metrics.precipitation.avg"] = 10.0

        enriched = enriquecer_datos(dataframe)
        real = enriched.loc[enriched["data_type"].eq("real")]
        estimated = enriched.loc[enriched["data_type"].eq("estimado")]

        self.assertEqual(len(real), 72)
        self.assertEqual(len(estimated), 240)
        self.assertEqual(estimated["year"].min(), 2021)
        self.assertEqual(estimated["year"].max(), 2030)
        self.assertTrue(estimated["metrics.temperature.max"].notna().all())
        self.assertFalse(
            enriched.duplicated(["city_name", "year", "month"]).any()
        )
        self.assertTrue(estimated["data_type"].eq("estimado").all())

        madrid_january = estimated.loc[
            estimated["city_name"].eq("Madrid")
            & estimated["month"].eq(1)
            & estimated["year"].eq(2021)
        ].iloc[0]
        self.assertAlmostEqual(madrid_january["media"], 22.433333333333334)
        self.assertAlmostEqual(
            madrid_january["metrics.temperature.max"], 26.433333333333334
        )
        self.assertAlmostEqual(
            madrid_january["diferencia_temperatura_maxima"], 4
        )

        city_summary, annual_summary = generar_resumenes(enriched)
        self.assertEqual(len(city_summary), 2)
        self.assertEqual(len(annual_summary), 6)

    def test_estimation_rejects_invalid_horizon(self):
        dataframe = pd.DataFrame(
            {"city_name": ["Madrid"], "year": [2020], "month": [1], "max": [20]}
        )
        with self.assertRaises(ValueError):
            añadir_estimaciones_temperatura(dataframe, horizon=0)


if __name__ == "__main__":
    unittest.main()
