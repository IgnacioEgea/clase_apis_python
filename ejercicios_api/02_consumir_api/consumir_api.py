import requests


url = "http://127.0.0.1:5000/"
response = requests.get(url, timeout=10)
response.raise_for_status()
print("Respuesta del API REST ->", response.text)
