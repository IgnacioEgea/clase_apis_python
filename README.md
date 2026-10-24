# Clase: consumo de APIs y datos meteorológicos

## Preparación

Usa Python 3.12 o posterior. Instala las dependencias del pipeline y del dashboard:

```bash
python -m pip install -r requirements.txt
```

## Pipeline meteorológico

Descarga los datos de Madrid y Londres, los limpia, calcula indicadores y estima las máximas de los diez años siguientes. Los datos Parquet y las gráficas se escriben dentro del repositorio, independientemente del directorio desde el que se ejecute.

```bash
python pipeline_meteorologico.py
```

Para abrir el dashboard:

```bash
streamlit run dashboard.py
```

Para generar una versión HTML independiente que se puede abrir localmente, sin Streamlit ni conexión a internet:

```bash
python exportar_dashboard_html.py
```

Abre `output/dashboard_climatico.html` en el navegador. Vuelve a ejecutar el comando para actualizarlo después de regenerar los datos.

Los resultados se guardan en `data/`, `output/` e `informe_limpieza.txt`. El comando antiguo `python app.py/app.py` se conserva como wrapper de compatibilidad.

## Pruebas

Las pruebas usan datos sintéticos y no realizan peticiones externas:

```bash
python -m unittest discover -s tests -v
```

## Estructura

- `pipeline_meteorologico.py`: limpieza, enriquecimiento, estimaciones y generación de resultados.
- `dashboard.py`: aplicación Streamlit.
- `exportar_dashboard_html.py`: genera una copia autónoma del dashboard para abrir en el navegador.
- `data/`: ficheros Parquet generados.
- `output/`: gráficas generadas.
- `tests/`: pruebas unitarias locales.
- `hello/`, `consumir_apis_usuario/` y `clasehelloword.py`: ejercicios introductorios independientes.

## Ejercicio de API REST con Flask

El ejercicio didáctico está separado del pipeline y organizado por etapas en
[`ejercicios_api/`](./ejercicios_api/README.md). La API final de lanzamientos
PS5 está en `ejercicios_api/api_videojuegos/`. Instala las
dependencias del proyecto con `python -m pip install -r requirements.txt` y
ejecuta desde la raíz:

```bash
python ejercicios_api/api_videojuegos/app.py
```

La web también incluye el análisis interactivo de clientes en
`/clientes`, con el botón «Datos para el desarrollador» que documenta y enlaza
el endpoint JSON `/api/clientes`. En Render, el servicio web enlaza
automáticamente la API de clientes definida en `render.yaml`. Para ejecutarlo
en local, inicia primero esa API con `PORT=5001 python
ejercicios_api/06_filtros/app.py` y después inicia el servidor web; ambos
servicios usan datos sintéticos.

Abre `http://127.0.0.1:5000/` para ver la portada. El catálogo importa la lista de juegos nativos de PS5 de Wikipedia y la lista
de PS VR2 (1.128 y 438 registros en la última actualización), incluye juegos
multiplataforma, deduplica títulos coincidentes y conserva las fichas
enriquecidas que ya tenía el proyecto. Los juegos se separan por año desde
2020; los que no tienen año confirmado quedan en un archivo aparte. Los
archivos hasta 2025 se conservan comprimidos como CSV por año y se leen
progresivamente.
La API genera JSON al solicitarlo (`/api/videojuegos?anio=2022`); los ficheros
anuales se pueden descargar en `/videojuegos.csv?anio=2022`. La portada muestra
los resultados en varias columnas con su fecha exacta; al seleccionar un juego,
la lista pasa a una columna vertical junto a la ficha y conserva la posición.
Un botón permite volver al inicio. La ficha mantiene proporciones uniformes
para carátulas, conserva el formato panorámico del arte y permite ampliar la
imagen al pulsarla. Se usan imágenes de fuentes oficiales o de fichas de juegos
cuando están disponibles; si no se encuentra una imagen original, la ficha
muestra un sustituto rotulado para que nunca quede el espacio vacío. En la
última carga, 514 juegos tienen imagen real enlazada y los 1.056 restantes
muestran un sustituto ilustrativo, no una carátula del videojuego. La búsqueda
tolera pequeñas erratas; los filtros de
categoría y mes se aplican al seleccionarlos.
El historial conserva únicamente los videojuegos seleccionados, queda en el
navegador y se puede borrar. Las imágenes se sirven a través de un endpoint de la API, evitando bloqueos de
carga del navegador. Pulsa la imagen para ampliarla. En los registros importados, el resumen puede
estar vacío si la fuente no lo proporciona.

La ficha incluye un gráfico compacto para 3DJuegos, Vandal, Metacritic y Hobby
Consolas. Solo se rellenan notas verificadas; las fuentes con escala distinta
se muestran como tales y los datos ausentes se marcan explícitamente, nunca
como cero. A 24/10/2026, el catálogo contiene 492 juegos con al menos una nota
verificada; 484 notas de crítica de Metacritic se incorporaron desde sus listas
públicas de PS5, asociadas solo cuando el título coincide exactamente. No todos
los juegos aparecen en las fuentes: entre 1.417 juegos con fecha de lanzamiento,
muchos siguen sin puntuación publicada o no tienen coincidencia verificable.
Por ejemplo, Monster Hunter Wilds muestra 8,8/10 en 3DJuegos (22 votos) y 88/100
de crítica y 7,1/10 de usuarios en Metacritic. Ghost of Yōtei conserva 8,7/10
en 3DJuegos (60 votos) y 86/100 y 8,0/10 en Metacritic.

Las listas se actualizan con `python ejercicios_api/api_videojuegos/importar_catalogo.py`.
Las fuentes son la [lista de juegos nativos de PS5](https://en.wikipedia.org/wiki/List_of_PlayStation_5_games)
y la [lista de juegos de PS VR2](https://en.wikipedia.org/wiki/List_of_PlayStation_VR2_games),
que incluye fechas regionales, desarrolladores y géneros, pero no resúmenes ni
portadas para todos los títulos. Se toma la fecha PAL/Europa; cuando falta, NA
y luego Japón. Wikipedia se distribuye bajo CC BY-SA: conserva la atribución y
las condiciones de compartir igual al redistribuir los datos. Las listas y
fechas pueden cambiar. Con el servidor activo, consulta la API desde
`http://127.0.0.1:5000/api/anios` o
`http://127.0.0.1:5000/api/videojuegos?anio=2026`.

Las pruebas de la API se ejecutan con:

```bash
python -m unittest discover -s ejercicios_api/api_videojuegos/tests -v
```

La API de clientes con filtros está en `ejercicios_api/06_filtros/`; su
configuración de Render está incluida como segundo servicio en `render.yaml`.
El cliente de ejemplo y el dashboard están en `consumir_primerapi/`. Consulta
[`consumir_primerapi/README.md`](./consumir_primerapi/README.md) para ejecutar
ambos y configurar `API_URL` con la URL pública del servicio.