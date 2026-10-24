import os
from typing import Any

import pandas as pd
import requests


API_URL = os.environ.get("API_URL", "http://127.0.0.1:5000/clientes")
REQUEST_TIMEOUT_SECONDS = 15


def obtener_clientes(url: str = API_URL) -> list[dict[str, Any]]:
    api_key = os.environ.get("CLIENTES_PASSWORD")
    if not api_key:
        raise ValueError("Define CLIENTES_PASSWORD para consultar la API protegida.")
    response = requests.get(
        url,
        headers={"X-API-Key": api_key},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    raw_data = response.json()
    if not isinstance(raw_data, list) or not all(
        isinstance(cliente, dict) for cliente in raw_data
    ):
        raise ValueError("La API debe devolver una lista JSON de clientes.")
    return raw_data


def procesar_clientes(raw_data: list[dict[str, Any]]) -> pd.DataFrame:
    clientes = pd.json_normalize(raw_data)
    columnas_requeridas = {
        "informacion_personal.nombre",
        "informacion_personal.apellido",
        "productos_activos.prestamos_vigentes",
        "segmentacion.nivel_ingresos_anual",
        "segmentacion.score_crediticio_interno",
        "segmentacion.tipo_cliente",
    }
    faltantes = columnas_requeridas.difference(clientes.columns)
    if faltantes:
        raise ValueError(
            "La respuesta de la API no contiene los campos necesarios: "
            + ", ".join(sorted(faltantes))
        )
    if clientes.empty:
        raise ValueError("La API no ha devuelto clientes para analizar.")

    ingresos = pd.to_numeric(
        clientes["segmentacion.nivel_ingresos_anual"], errors="coerce"
    )
    prestamos = pd.to_numeric(
        clientes["productos_activos.prestamos_vigentes"], errors="coerce"
    )
    puntuacion = pd.to_numeric(
        clientes["segmentacion.score_crediticio_interno"], errors="coerce"
    )
    if ingresos.isna().any() or (ingresos <= 0).any():
        raise ValueError("Los ingresos anuales deben ser números mayores que cero.")
    if prestamos.isna().any() or (prestamos < 0).any():
        raise ValueError("Los préstamos vigentes deben ser números no negativos.")
    if puntuacion.isna().any() or (~puntuacion.between(0, 1000)).any():
        raise ValueError("El score crediticio interno debe estar entre 0 y 1000.")

    clientes["nombre_completo"] = (
        clientes["informacion_personal.nombre"].astype(str)
        + " "
        + clientes["informacion_personal.apellido"].astype(str)
    )
    clientes["ratio_endeudamiento"] = prestamos / ingresos
    clientes["indice_salud_crediticia"] = puntuacion / 1000 * 100
    clientes["ingresos_anuales"] = ingresos
    clientes["prestamos_vigentes"] = prestamos
    clientes["tipo_cliente"] = clientes["segmentacion.tipo_cliente"]
    return clientes


def main() -> None:
    try:
        clientes = procesar_clientes(obtener_clientes())
    except (requests.exceptions.RequestException, ValueError) as error:
        raise SystemExit(f"Error al consultar la API de clientes: {error}") from error

    columnas = [
        "id_cliente",
        "nombre_completo",
        "tipo_cliente",
        "ingresos_anuales",
        "prestamos_vigentes",
        "ratio_endeudamiento",
        "indice_salud_crediticia",
    ]
    print(clientes[columnas].to_string(index=False))


if __name__ == "__main__":
    main()
