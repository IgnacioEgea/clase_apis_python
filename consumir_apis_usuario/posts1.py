import requests

# Práctica 4.1 - Consumir una API
url = "https://jsonplaceholder.typicode.com/posts"
response = requests.get(url)

# Práctica 4.3 - Mostrar el código de estado
print("Código de estado:", response.status_code)

# Validar el código de estado
if response.status_code == 200:
    print(response.json())
else:
    print("Error en la solicitud")

# Mostrar cabeceras
print(response.headers)
print("Content-Type: " + response.headers["Content-Type"])

# Práctica 4.4 - Parámetros de ruta y consulta
# Enviar un parámetro de ruta
url_post = "https://jsonplaceholder.typicode.com/posts/1"
response_post = requests.get(url_post)
print("Respuesta de /posts/1:")
print(response_post.json())

# Enviar un parámetro de consulta
querystring = {"id": "2"}
response_query = requests.get(url, params=querystring)
print("Respuesta con querystring id=2:")
print(response_query.json())

# Enviar dos parámetros de consulta
querystring.update({"title": "qui est esse"})
response_query2 = requests.get(url, params=querystring)
print("Respuesta con querystring id=2 y title=qui est esse:")
print(response_query2.json())

# Modificar el valor del campo title
querystring["title"] = "nuevo titulo"
response_query3 = requests.get(url, params=querystring)
print("Respuesta con title modificado:")
print(response_query3.json())
