# Ejercicio de API REST

Cada carpeta representa una etapa independiente del ejercicio. Las etapas 1–6
son los ejemplos didácticos originales; la API personal final está en
`api_videojuegos/`.

## Etapas

1. `01_primer_api/`: endpoint raíz que responde `Hello world!`.
2. `02_consumir_api/`: cliente `requests` que consume el servidor de la etapa 1.
3. `03_clientes_json/`: endpoint `/clientes` con respuesta JSON.
4. `04_datos_json/`: lectura de clientes desde un fichero JSON.
5. `05_datos_csv/`: descarga del fichero de clientes CSV.
6. `06_filtros/`: API con datos de clientes sintéticos, búsqueda por ID y filtros
   insensibles a mayúsculas. Se puede desplegar con el servicio `api-clientes`
   definido en `render.yaml`; requiere publicar primero el repositorio en GitHub
   y vincularlo a Render.
7. `api_videojuegos/`: catálogo PS5 desde 2020 con filtros, fichas visuales,
   búsqueda aproximada, JSON bajo demanda e historial de juegos seleccionados.

Para ejecutar los servidores desde la raíz del repositorio, usa, por ejemplo:

```bash
python ejercicios_api/01_primer_api/app.py
python ejercicios_api/03_clientes_json/app.py
python ejercicios_api/04_datos_json/app.py
python ejercicios_api/05_datos_csv/app.py
python ejercicios_api/06_filtros/app.py
python ejercicios_api/api_videojuegos/app.py
```

Ejecuta un solo servidor a la vez: las etapas usan el puerto 5000. Para probar
el cliente de la etapa 2, deja activo el servidor de `01_primer_api` y, desde
otra terminal, ejecuta:

```bash
python ejercicios_api/02_consumir_api/consumir_api.py
```

La API de clientes carga sus datos JSON al iniciar y expone `/clientes`,
`/clientes/<id_cliente>` y `/health`. Sus pruebas se ejecutan desde la raíz con:

```bash
python -m unittest discover -s ejercicios_api/06_filtros -p 'test_*.py' -v
```

El cliente que normaliza/enriquece esos datos y el dashboard Streamlit están
documentados en [`consumir_primerapi/README.md`](../consumir_primerapi/README.md).
Para desplegar, publica el repositorio en GitHub y crea los servicios definidos
en el `render.yaml` de la raíz. Render mostrará la URL pública al terminar;
configura esa URL en `API_URL` incluyendo `/clientes` antes de ejecutar el cliente.
La web principal también ofrece la vista interactiva en `/clientes` y reenvía
sus peticiones a este servicio. En Render, el host se configura automáticamente
desde el blueprint; localmente inicia esta API en el puerto 5001 antes del
servidor de videojuegos. El acceso al dashboard y a sus datos requiere iniciar
sesión; configura `CLIENTES_PASSWORD` con `Nacho` en ambos servicios de Render
(el servidor web y la API de clientes). Configura además `FLASK_SECRET_KEY` con
un secreto aleatorio solo en el servidor web. Los registros son sintéticos.

La API final usa las rutas `/api/anios`, `/api/videojuegos?anio=2022`,
`/api/videojuegos/<id>` y `/videojuegos.csv?anio=2022`. La lista acepta los
parámetros opcionales `q`, `categoria` y `mes`; la búsqueda tolera errores
pequeños de escritura. Desde la raíz, ejecuta
sus pruebas con:

```bash
python -m unittest discover -s ejercicios_api/api_videojuegos/tests -v
```

El catálogo combina las listas de juegos nativos de PS5 y PS VR2 de Wikipedia
(1.128 y 438 registros en la última importación, con títulos coincidentes
deduplicados), incluyendo multiplataforma, desde 2020. Los datos de 2020–2025 están guardados como
`videojuegos_<año>.csv.gz`; los años recientes se mantienen en CSV sin
comprimir. Los anuncios sin fecha confirmada se guardan en
`videojuegos_sin_fecha.csv`, sin asignarles una fecha estimada. Cada fila
conserva un enlace de fuente, desarrollador y género cuando están disponibles.
Todas las fichas muestran una imagen: se usa arte o carátula real cuando está
disponible y, en los demás casos, una imagen sustitutiva que indica claramente
que no se ha encontrado el original. Las imágenes se sirven desde la API para
evitar bloqueos del navegador.
La ficha puede mostrar puntuaciones verificadas de 3DJuegos, Vandal, Metacritic
y Hobby Consolas; los valores ausentes no se rellenan como cero. Al 24/10/2026,
492 juegos tienen al menos una puntuación verificada y 484 notas de crítica se
incorporaron desde las listas públicas de PS5 de Metacritic, solo con coincidencia
exacta de título. Muchas fichas no tienen notas publicadas o no coinciden con
esas fuentes, y se mantienen sin rellenar antes que inventar valores. El CSV es la
fuente de datos y el JSON se genera bajo demanda leyendo únicamente el año
solicitado. Actualiza la lista con:

```bash
python ejercicios_api/api_videojuegos/importar_catalogo.py
```

Las fuentes son la [lista de juegos de PS5](https://en.wikipedia.org/wiki/List_of_PlayStation_5_games)
y la [lista de PS VR2](https://en.wikipedia.org/wiki/List_of_PlayStation_VR2_games);
al redistribuir sus datos hay que respetar CC BY-SA y atribuir las fuentes.
