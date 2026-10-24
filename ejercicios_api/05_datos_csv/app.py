from pathlib import Path

from flask import Flask, jsonify, send_file


app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent


@app.route("/clientes", methods=["GET"])
def obtener_clientes():
    return jsonify(
        [
            {"id_cliente": "CLI-2026-894021", "nombre": "Ana", "apellido": "Gómez"},
            {"id_cliente": "CLI-2026-123456", "nombre": "Carlos", "apellido": "Ruiz"},
        ]
    )


@app.route("/clientescsv", methods=["GET"])
def obtener_clientes_csv():
    return send_file(
        BASE_DIR / "data" / "datos_clientes.csv",
        mimetype="text/csv",
        as_attachment=True,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
