from flask import Flask, jsonify


app = Flask(__name__)
CLIENTES = [
    {
        "id_cliente": "CLI-2026-894021",
        "informacion_personal": {
            "nombre": "Ana",
            "apellido": "Gómez",
            "pais_residencia": "ES",
        },
    },
    {
        "id_cliente": "CLI-2026-123456",
        "informacion_personal": {
            "nombre": "Carlos",
            "apellido": "Ruiz",
            "pais_residencia": "MX",
        },
    },
]


@app.route("/clientes", methods=["GET"])
def obtener_clientes():
    return jsonify(CLIENTES)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
