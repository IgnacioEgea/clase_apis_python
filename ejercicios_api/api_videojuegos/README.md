# Calendario de videojuegos PS5

API Flask independiente para consultar un catálogo de juegos de PS5 y PS VR2.
Los datos están archivados por año en CSV (comprimidos cuando corresponde) y la
API genera JSON bajo demanda. Al iniciar el servidor, el catálogo se carga una
vez en memoria para evitar releer los CSV en cada petición. Reinicia el proceso
para que recoja cambios posteriores en los archivos de datos.

## Ejecutar

Requiere Python 3.10 o posterior.

```bash
python -m pip install -r requirements.txt
python app.py
```

Abre <http://127.0.0.1:5000/> para el diseño original o
<http://127.0.0.1:5000/modo-oscuro> para la alternativa en modo oscuro. Ambas
pantallas usan el mismo catálogo y los mismos endpoints de la API.
La instalación solo incluye dependencias necesarias para servir esta API.

El análisis de clientes está en `/clientes` y requiere contraseña. Define el
mismo valor privado para `CLIENTES_PASSWORD` tanto en el servidor de videojuegos
como en el servicio `api-clientes`, y configura `FLASK_SECRET_KEY` con un secreto aleatorio en el
servidor web. El blueprint raíz de Render marca estas variables como manuales
para que no queden guardadas en el repositorio. En local, inicia la API de
clientes desde la raíz del repositorio con
`PORT=5001 python ejercicios_api/06_filtros/app.py` con la variable
`CLIENTES_PASSWORD` configurada; inicia el servidor web con esa misma variable,
`API_CLIENTES_HOST=127.0.0.1:5001` y una `FLASK_SECRET_KEY` aleatoria.

## Desplegar en Render

La configuración raíz `render.yaml` establece `ejercicios_api/api_videojuegos`
como `rootDir`, instala solo las dependencias de esta API y comprueba el servicio
en `/api/anios`. Si configuras el servicio manualmente en Render:

- **Root Directory:** `ejercicios_api/api_videojuegos`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:**

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

Gunicorn sirve la aplicación Flask `app` definida en `app.py`. El proceso usa
el puerto que Render proporciona por la variable `PORT`.

## Consultas

- `GET /api/anios`: años disponibles.
- `GET /api/videojuegos?anio=2026`: catálogo de un año.
- `GET /api/videojuegos?anio=2026&q=stray&categoria=Accion&mes=07`: búsqueda y filtros.
- `GET /api/videojuegos/<id>`: ficha JSON.
- `GET /imagenes/<id>`: imagen de alta resolución o una ilustración identificada
  cuando no se dispone de arte original.
- `GET /videojuegos.csv?anio=2026`: descargar el archivo anual.

Las imágenes originales se obtienen de páginas oficiales o fichas públicas. Las
miniaturas de Metacritic se resuelven a la imagen original en vez de usar la
versión de 96 × 144 píxeles. La ilustración de sustitución no pretende ser una
portada real. Las puntuaciones solo se muestran cuando hay una fuente guardada.
La media normaliza las notas disponibles a una escala común de 0 a 10; se
presenta como orientativa porque las fuentes pueden usar criterios diferentes.

## Actualizar el catálogo

```bash
python importar_catalogo.py
```

El importador consulta las listas públicas de PS5 y PS VR2. Las fuentes de datos
son [Wikipedia: PS5](https://en.wikipedia.org/wiki/List_of_PlayStation_5_games)
y [Wikipedia: PS VR2](https://en.wikipedia.org/wiki/List_of_PlayStation_VR2_games).
Respeta la licencia CC BY-SA al redistribuir los datos.

## Pruebas

```bash
python -m unittest discover -s tests -v
```
