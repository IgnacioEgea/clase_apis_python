# Calendario de videojuegos PS5 y PS VR2

API REST desarrollada con Flask para explorar lanzamientos de PlayStation 5 y
PlayStation VR2. Incluye una interfaz web responsive, búsqueda y filtros,
fichas de videojuegos, consulta JSON y descarga del catálogo CSV.

## Funcionalidades

- Consulta del catálogo por año, título, categoría y mes.
- Fichas por videojuego con fechas, desarrollador, fuentes e información de notas.
- Respuestas JSON y descarga de los datos en CSV.
- Imágenes de catálogo con ilustración alternativa cuando no hay portada disponible.
- Historial y favoritos guardados localmente en el navegador.
- Catálogo incluido en CSV, leído al arrancar el servicio.

## Requisitos

- Python 3.10 o posterior.
- Las dependencias de `requirements.txt`.

## Ejecutar en local

Desde esta carpeta:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

En Windows, activa el entorno con:

```powershell
.venv\Scripts\Activate.ps1
```

Abre <http://127.0.0.1:5000/>.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/anios` | Años de catálogo disponibles |
| `GET` | `/api/videojuegos?anio=2026` | Juegos de un año |
| `GET` | `/api/videojuegos?anio=2026&q=stray&categoria=Accion&mes=07` | Búsqueda y filtros |
| `GET` | `/api/videojuegos/<id>` | Ficha JSON de un videojuego |
| `GET` | `/imagenes/<id>` | Imagen o ilustración alternativa |
| `GET` | `/videojuegos.csv?anio=2026` | Descargar catálogo anual en CSV |

Ejemplo para consultar el catálogo:

```bash
curl "http://127.0.0.1:5000/api/videojuegos?anio=2026"
```

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Despliegue en Render

El archivo `render.yaml` configura el servicio para desplegar esta carpeta como
raíz independiente. También puedes crear el servicio manualmente:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- **Health Check Path:** `/api/anios`

Configura `FLASK_SECRET_KEY` como variable privada de entorno en producción.
No publiques claves ni contraseñas en el repositorio.

## Integración opcional: análisis de clientes

La sección `/clientes` es una integración opcional con un servicio externo de
clientes; el catálogo de videojuegos y sus endpoints funcionan sin ese servicio.
Para habilitarla, configura `CLIENTES_PASSWORD` y `API_CLIENTES_URL`, o bien
`API_CLIENTES_HOST`. Usa HTTPS en producción y protege las variables como
secretos del proveedor de despliegue.

## Fuentes y atribución

Los datos del catálogo se basan en las listas públicas de
[juegos de PS5](https://en.wikipedia.org/wiki/List_of_PlayStation_5_games) y
[juegos de PS VR2](https://en.wikipedia.org/wiki/List_of_PlayStation_VR2_games).
Si redistribuyes los datos, respeta la licencia CC BY-SA y atribuye las fuentes.
Las fechas de lanzamiento pueden cambiar y las puntuaciones solo se muestran
cuando hay una fuente registrada.
