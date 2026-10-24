import requests


url = "http://127.0.0.1:5000/api/videojuegos"
response = requests.get(url, params={"anio": 2026}, timeout=10)
response.raise_for_status()
for videojuego in response.json():
    print(
        f"{videojuego['fecha_salida']} · {videojuego['titulo']} "
        f"({videojuego['desarrollador']})"
    )
