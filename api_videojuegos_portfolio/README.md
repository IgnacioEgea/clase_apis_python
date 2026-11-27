# Calendario de videojuegos PS5

API REST desarrollada con Flask para explorar lanzamientos de PlayStation 5,
desde grandes producciones hasta indies. Incluye una interfaz web responsive, búsqueda y filtros,
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
| `GET` | `/api/categorias?anio=2026` | Categorías disponibles de un año |
| `GET` | `/api/videojuegos/<id>` | Ficha JSON de un videojuego |
| `GET` | `/imagenes/<id>` | Imagen o ilustración alternativa |
| `GET` | `/videojuegos.csv?anio=2026` | Descargar catálogo anual en CSV |
| `GET` | `/api/descubrir` | Colecciones para descubrir juegos |
| `GET` | `/api/descubrir/<coleccion>?genero=rol&anio=2024&limite=20` | Juegos de una colección, ya ordenados |
| `GET` | `/api/generos` | Géneros unificados y número de juegos de cada uno |
| `GET` | `/api/videojuegos?anio=todos&q=resident` | Buscar en todos los años |
| `GET` | `/api/videojuegos/<id>/similares` | Juegos parecidos a uno dado |

Ejemplo para consultar el catálogo:

```bash
curl "http://127.0.0.1:5000/api/videojuegos?anio=2026"
```

## Descubrir juegos

Además de buscar por título, la web ofrece colecciones para encontrar juegos:

| Colección | Criterio |
|---|---|
| `mejor-valorados` | Nota de críticos de Metacritic |
| `mas-descargados` | Top 20 anual de la PlayStation Store en Europa (PlayStation Blog, 2023-2025) |
| `goty` | Ganadores de Juego del año en The Game Awards (2020-2025) |
| `mas-esperados` | Seguidores en releases.com de los próximos juegos de PS5 |
| `proximos` | Fecha de salida posterior a hoy |
| `recientes` | Publicados en los últimos 90 días |
| `expansiones-dlc` | Expansiones y DLC destacados, enlazados a su juego base |
| `resenas-usuarios` | Nota de usuarios de Metacritic (aún con pocos datos) |

Todas admiten `genero` (ver `/api/generos`), `anio` y `limite` (1-200). Las
categorías de Wikipedia se agrupan en 16 géneros en español (Acción, Rol,
Shooter, Terror...). Las listas curadas están en `data/colecciones/` como CSV
con la fuente de cada dato; los juegos que citan y no están en el catálogo
reciben una ficha mínima para poder abrirlos igualmente.

## Rendimiento

- Los CSV se leen una sola vez al arrancar: se preparan el índice de búsqueda,
  las categorías de cada año y el JSON de cada catálogo anual.
- Las respuestas JSON llevan `ETag` (el navegador recibe `304` si no cambiaron)
  y se comprimen con gzip cuando el navegador lo acepta.
- Las portadas externas se guardan en una caché en memoria limitada a 48 MB,
  así cada imagen se descarga de la fuente una sola vez por proceso.
- El CSS y el JavaScript están en `static/` con una versión en la URL, para que
  el navegador los guarde en caché y solo los vuelva a pedir cuando cambian.

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

## Portadas

Cada juego guarda en el CSV la URL de su portada oficial. Se eligió la mejor
versión disponible de cada una, comprobando que el nombre coincide con el juego:

1. Arte vertical 2:3 de **Steam** (600×900) o de la **PlayStation Store**
   (portada vertical o, si no existe, el arte cuadrado oficial).
2. Las imágenes que ya tenía el catálogo (3DJuegos, PlayStation, Metacritic)
   cuando tienen buena resolución.
3. La portada del artículo de **Wikipedia** como último recurso.

En la ficha todas se muestran en el mismo marco vertical 2:3: las verticales
lo llenan y las cuadradas o apaisadas se ven enteras sobre un fondo
desenfocado de la propia imagen. Los pocos juegos sin arte oficial localizable
muestran una portada ilustrativa generada (colores propios, título, género y
año) marcada como tal. Las portadas siguen siendo propiedad de sus editores: se
muestran solo para identificar cada juego en un proyecto universitario sin
fines lucrativos, enlazando siempre a la fuente.

## Fuentes y atribución

Los datos del catálogo combinan la
[lista de juegos de PS5 de Wikipedia](https://en.wikipedia.org/wiki/List_of_PlayStation_5_games),
los juegos de la [categoría de PS5 de Wikipedia](https://en.wikipedia.org/wiki/Category:PlayStation_5_games)
que faltaban (con fecha de PS5, desarrollador y género de Wikidata) y fichas
revisadas a mano. Los juegos exclusivos de realidad virtual (PS VR2) no se
incluyen; los juegos normales con modo VR opcional, como Gran Turismo 7, se
mantienen como PS5. Si redistribuyes los datos, respeta la licencia CC BY-SA
de Wikipedia y atribuye las fuentes.
Las fechas de lanzamiento pueden cambiar y las puntuaciones solo se muestran
cuando hay una fuente registrada.
