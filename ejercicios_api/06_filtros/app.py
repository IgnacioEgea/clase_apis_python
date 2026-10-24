import json
import hmac
import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request


app = Flask(__name__)
ARCHIVO_CLIENTES = Path(__file__).resolve().parent / "data" / "datos_clientes.json"


def cargar_clientes() -> list[dict[str, Any]]:
    with ARCHIVO_CLIENTES.open(encoding="utf-8") as archivo:
        clientes = json.load(archivo)
    if not isinstance(clientes, list) or not all(
        isinstance(cliente, dict) for cliente in clientes
    ):
        raise ValueError(
            f"El archivo {ARCHIVO_CLIENTES} debe contener una lista de clientes"
        )
    return clientes


CLIENTES = cargar_clientes()


def coincide_filtro(datos: Any, campo_buscado: str, valor_buscado: str) -> bool:
    if isinstance(datos, dict):
        for campo, valor in datos.items():
            if (
                campo.casefold() == campo_buscado
                and not isinstance(valor, (dict, list))
                and valor_buscado in str(valor).casefold()
            ):
                return True
            if isinstance(valor, (dict, list)) and coincide_filtro(
                valor, campo_buscado, valor_buscado
            ):
                return True
    elif isinstance(datos, list):
        return any(
            coincide_filtro(elemento, campo_buscado, valor_buscado)
            for elemento in datos
        )
    return False


def verificar_api_key():
    configured_password = os.environ.get("CLIENTES_PASSWORD")
    if not configured_password:
        return jsonify({"error": "El acceso a la API no está configurado."}), 503
    if not hmac.compare_digest(
        request.headers.get("X-API-Key", ""), configured_password
    ):
        return jsonify({"error": "No autorizado."}), 401
    return None


@app.route("/clientes", methods=["GET"])
def obtener_clientes():
    error = verificar_api_key()
    if error:
        return error
    consulta = request.args.get("q")
    if consulta is None:
        return jsonify(CLIENTES)

    filtros = []
    for filtro in consulta.split():
        campo, separador, valor = filtro.partition(":")
        if not separador or not campo or not valor:
            return jsonify({"error": "Usa el formato campo:valor"}), 400
        filtros.append((campo.casefold(), valor.casefold()))
    if not filtros:
        return jsonify({"error": "El parámetro q debe contener filtros"}), 400

    resultados = [
        cliente
        for cliente in CLIENTES
        if all(coincide_filtro(cliente, campo, valor) for campo, valor in filtros)
    ]
    return jsonify(resultados)


@app.route("/clientes/<id_cliente>", methods=["GET"])
def obtener_cliente_id(id_cliente: str):
    error = verificar_api_key()
    if error:
        return error
    cliente = next((c for c in CLIENTES if c["id_cliente"] == id_cliente), None)
    if cliente is None:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify(cliente)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", "5000")))
