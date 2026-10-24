import json
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request


app = Flask(__name__)
ARCHIVO_CLIENTES = Path(__file__).resolve().parent / "data" / "datos_clientes.json"


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


def cargar_clientes() -> list[dict[str, Any]]:
    with ARCHIVO_CLIENTES.open(encoding="utf-8") as archivo:
        return json.load(archivo)


@app.route("/clientes", methods=["GET"])
def obtener_clientes():
    clientes = cargar_clientes()
    consulta = request.args.get("q")
    if consulta is None:
        return jsonify(clientes)

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
        for cliente in clientes
        if all(coincide_filtro(cliente, campo, valor) for campo, valor in filtros)
    ]
    return jsonify(resultados)


@app.route("/clientes/<id_cliente>", methods=["GET"])
def obtener_cliente_id(id_cliente: str):
    cliente = next(
        (c for c in cargar_clientes() if c["id_cliente"] == id_cliente), None
    )
    if cliente is None:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify(cliente)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
