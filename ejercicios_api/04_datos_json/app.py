import json
from pathlib import Path

from flask import Flask, jsonify


app = Flask(__name__)
ARCHIVO_CLIENTES = Path(__file__).resolve().parent / "data" / "datos_clientes.json"


@app.route("/clientes", methods=["GET"])
def obtener_clientes():
    with ARCHIVO_CLIENTES.open(encoding="utf-8") as archivo:
        return jsonify(json.load(archivo))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
