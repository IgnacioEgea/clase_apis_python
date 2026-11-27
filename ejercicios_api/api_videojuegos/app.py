import csv
import gzip
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import threading
import time
import unicodedata
from collections import Counter, OrderedDict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from flask import (
    Flask,
    Response,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)


app = Flask(__name__)
# Recargar plantillas en cada petición solo tiene sentido al desarrollar.
app.config["TEMPLATES_AUTO_RELOAD"] = os.environ.get("FLASK_DEBUG") == "1"
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "false"
).casefold() in {"1", "true", "yes"}
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "videojuegos"
STATIC_DIR = BASE_DIR / "static"
IMAGE_HOSTS = frozenset({
    "i.3djuegos.com",
    "image.api.playstation.com",
    "gmedia.playstation.com",
    "www.metacritic.com",
    "upload.wikimedia.org",
    "images.igdb.com",
    "shared.akamai.steamstatic.com",
    "cdn.akamai.steamstatic.com",
    "shared.fastly.steamstatic.com",
    "cdn.fastly.steamstatic.com",
    "shared.cloudflare.steamstatic.com",
    "cdn.cloudflare.steamstatic.com",
})
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_APP_ASSETS = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps"
HTTP_HEADERS = {
    # Wikimedia pide un User-Agent identificable con una forma de contacto.
    "User-Agent": (
        "CalendarioPS5/1.1 (proyecto universitario sin fines lucrativos; "
        "https://github.com/IgnacioEgea/clase_apis_python)"
    ),
}
LOOKUP_TIMEOUT_SECONDS = 6
MAX_LOOKUP_BYTES = 1024 * 1024
COVER_RETRY_SECONDS = 3600
IMAGE_TYPES = frozenset({"image/avif", "image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_CACHE_MAX_BYTES = 48 * 1024 * 1024
IMAGE_CACHE_SECONDS = 86400
MAX_CLIENT_DATA_BYTES = 2 * 1024 * 1024
CLIENT_API_TIMEOUT_SECONDS = 10
API_CACHE_SECONDS = 300
COMPRESSIBLE_TYPES = frozenset({
    "application/json",
    "image/svg+xml",
    "text/css",
    "text/csv",
    "text/html",
    "text/javascript",
})
MIN_COMPRESS_BYTES = 1024
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FichaBusqueda:
    """Texto ya normalizado de un juego para no recalcularlo en cada búsqueda."""

    texto: str
    palabras: tuple[str, ...]
    categoria: str


ARCHIVOS: dict[str, Path] = {}
VIDEOJUEGOS_POR_ANIO: dict[str, tuple[dict[str, str], ...]] = {}
VIDEOJUEGOS_POR_ID: dict[str, dict[str, str]] = {}
FICHAS_BUSQUEDA: dict[int, FichaBusqueda] = {}
CATEGORIAS_POR_ANIO: dict[str, tuple[str, ...]] = {}
JSON_POR_ANIO: dict[str, bytes] = {}
# Clave especial para buscar en el catálogo completo, sin elegir año.
TODOS_LOS_ANIOS = "todos"


def archivos_disponibles() -> dict[str, Path]:
    archivos = {}
    for path in DATA_DIR.glob("videojuegos_*"):
        if path.suffix not in {".csv", ".gz"}:
            continue
        nombre = path.name.removeprefix("videojuegos_")
        clave = nombre.removesuffix(".csv.gz").removesuffix(".csv")
        if clave == "sin_fecha" or (clave.isdecimal() and len(clave) == 4):
            archivos[clave] = path
    return archivos


def archivo_para_anio(anio: str) -> Path | None:
    if anio == "sin-fecha":
        anio = "sin_fecha"
    return ARCHIVOS.get(anio)


def leer_videojuegos(path: Path) -> Iterator[dict[str, str]]:
    abrir = gzip.open if path.suffix == ".gz" else open
    with abrir(path, mode="rt", encoding="utf-8-sig", newline="") as archivo:
        yield from csv.DictReader(archivo)


def serializar_json(videojuegos: Iterable[dict[str, str]]) -> bytes:
    return json.dumps(
        list(videojuegos), ensure_ascii=False, separators=(",", ":")
    ).encode()


def crear_ficha_busqueda(videojuego: dict[str, str]) -> FichaBusqueda:
    texto = normalizar_texto(
        f"{videojuego.get('titulo', '')} {videojuego.get('id', '')}"
    )
    return FichaBusqueda(
        texto=" ".join(texto.split()),
        palabras=tuple(texto.split()),
        categoria=normalizar_categoria(videojuego.get("categoria", "")),
    )


def categorias_unicas(videojuegos: Iterable[dict[str, str]]) -> tuple[str, ...]:
    """Agrupa variantes como "Action-Adventure" y "Action-adventure".

    El filtro ya ignora mayúsculas y tildes, así que en el desplegable se
    muestra una sola opción por categoría: la forma escrita más frecuente.
    """
    variantes: dict[str, Counter[str]] = {}
    for videojuego in videojuegos:
        categoria = videojuego.get("categoria", "").strip()
        if categoria:
            variantes.setdefault(normalizar_categoria(categoria), Counter())[
                categoria
            ] += 1
    return tuple(
        contador.most_common(1)[0][0]
        for _, contador in sorted(variantes.items())
    )


RESUMENES_PATH = BASE_DIR / "data" / "resumenes.csv"


def leer_resumenes() -> dict[str, str]:
    """Resúmenes redactados a mano, guardados aparte de los CSV importados.

    Así una nueva importación del catálogo no los borra.
    """
    if not RESUMENES_PATH.exists():
        return {}
    with RESUMENES_PATH.open(encoding="utf-8-sig", newline="") as archivo:
        return {
            fila["id"]: fila["resumen"].strip()
            for fila in csv.DictReader(archivo)
            if fila.get("id") and fila.get("resumen", "").strip()
        }


def con_resumen(videojuego: dict[str, str], resumenes: dict[str, str]) -> dict[str, str]:
    # El resumen del CSV del año tiene prioridad; el manual solo rellena huecos.
    if not videojuego.get("resumen") and videojuego.get("id") in resumenes:
        videojuego["resumen"] = resumenes[videojuego["id"]]
    return videojuego


def cargar_catalogo() -> None:
    """Lee los CSV una sola vez y prepara índices, categorías y JSON."""
    global ARCHIVOS, VIDEOJUEGOS_POR_ANIO, VIDEOJUEGOS_POR_ID
    global FICHAS_BUSQUEDA, CATEGORIAS_POR_ANIO, JSON_POR_ANIO
    ARCHIVOS = archivos_disponibles()
    resumenes = leer_resumenes()
    VIDEOJUEGOS_POR_ANIO = {
        anio: tuple(con_resumen(videojuego, resumenes) for videojuego in leer_videojuegos(path))
        for anio, path in ARCHIVOS.items()
    }
    VIDEOJUEGOS_POR_ID = {
        videojuego["id"]: videojuego
        for videojuegos in VIDEOJUEGOS_POR_ANIO.values()
        for videojuego in videojuegos
        if videojuego.get("id")
    }
    FICHAS_BUSQUEDA = {
        id(videojuego): crear_ficha_busqueda(videojuego)
        for videojuegos in VIDEOJUEGOS_POR_ANIO.values()
        for videojuego in videojuegos
    }
    CATEGORIAS_POR_ANIO = {
        anio: categorias_unicas(videojuegos)
        for anio, videojuegos in VIDEOJUEGOS_POR_ANIO.items()
    }
    JSON_POR_ANIO = {
        anio: serializar_json(videojuegos)
        for anio, videojuegos in VIDEOJUEGOS_POR_ANIO.items()
    }
    # "todos" junta los años en orden y deja al final los juegos sin fecha.
    todos = tuple(
        videojuego
        for anio in sorted(VIDEOJUEGOS_POR_ANIO, key=lambda clave: (clave == "sin_fecha", clave))
        for videojuego in VIDEOJUEGOS_POR_ANIO[anio]
    )
    VIDEOJUEGOS_POR_ANIO[TODOS_LOS_ANIOS] = todos
    CATEGORIAS_POR_ANIO[TODOS_LOS_ANIOS] = categorias_unicas(todos)
    JSON_POR_ANIO[TODOS_LOS_ANIOS] = serializar_json(todos)


def buscar_videojuego(videojuego_id: str) -> dict[str, str] | None:
    # Las expansiones y los juegos citados en colecciones también tienen ficha.
    return VIDEOJUEGOS_POR_ID.get(videojuego_id) or EXTRAS_POR_ID.get(videojuego_id)


def normalizar_texto(texto: str) -> str:
    texto_sin_tildes = unicodedata.normalize("NFD", texto.casefold())
    return "".join(
        caracter
        for caracter in texto_sin_tildes
        if unicodedata.category(caracter) != "Mn"
    )


def ficha_busqueda(videojuego: dict[str, str]) -> FichaBusqueda:
    ficha = FICHAS_BUSQUEDA.get(id(videojuego))
    return ficha if ficha is not None else crear_ficha_busqueda(videojuego)


def termino_coincide(termino: str, palabra: str) -> bool:
    if termino in palabra:
        return True
    if len(termino) < 3 or (len(termino) < 5 and termino[:3] != palabra[:3]):
        return False
    # Descarta rápido las palabras con longitudes muy distintas antes de usar
    # SequenceMatcher, que es la parte más costosa de la búsqueda aproximada.
    if 2 * min(len(termino), len(palabra)) / (len(termino) + len(palabra)) < 0.82:
        return False
    matcher = SequenceMatcher(None, termino, palabra)
    return (
        matcher.real_quick_ratio() >= 0.82
        and matcher.quick_ratio() >= 0.82
        and matcher.ratio() >= 0.82
    )


def coincide_busqueda(
    videojuego: dict[str, str], consulta: str | list[str]
) -> bool:
    terminos = (
        normalizar_texto(consulta).split()
        if isinstance(consulta, str)
        else consulta
    )
    if not terminos:
        return False
    ficha = ficha_busqueda(videojuego)
    if " ".join(terminos) in ficha.texto:
        return True
    return all(
        any(termino_coincide(termino, palabra) for palabra in ficha.palabras)
        for termino in terminos
    )


def normalizar_categoria(categoria: str) -> str:
    return normalizar_texto(categoria).strip()


def filtrar_videojuegos(
    videojuegos: tuple[dict[str, str], ...],
    consulta: str,
    categoria: str,
    mes: str,
) -> Iterator[dict[str, str]]:
    # La consulta y la categoría se normalizan una vez por petición, no por juego.
    terminos = normalizar_texto(consulta).split() if consulta else []
    categoria_normalizada = normalizar_categoria(categoria) if categoria else ""
    for videojuego in videojuegos:
        if categoria and ficha_busqueda(videojuego).categoria != categoria_normalizada:
            continue
        if mes and not videojuego.get("fecha_salida", "").startswith(
            f"{videojuego.get('anio_salida', '')}-{mes}-"
        ):
            continue
        if consulta and not coincide_busqueda(videojuego, terminos):
            continue
        yield videojuego


def partir_titulo(titulo: str, ancho: int = 15, max_lineas: int = 4) -> list[str]:
    lineas: list[str] = []
    for palabra in titulo.split():
        if lineas and len(lineas[-1]) + 1 + len(palabra) <= ancho:
            lineas[-1] += " " + palabra
        else:
            lineas.append(palabra)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1][: ancho - 1].rstrip() + "…"
    return lineas


def renderizar_imagen_sustitutiva(videojuego: dict[str, str] | str) -> str:
    """Portada ilustrativa 2:3 para los juegos sin arte oficial localizable.

    Los colores salen del título, así que cada juego tiene siempre la misma
    portada y dos juegos distintos casi nunca coinciden.
    """
    if isinstance(videojuego, str):
        videojuego = {"titulo": videojuego}
    titulo = videojuego.get("titulo", "") or "Videojuego"
    semilla = int(hashlib.sha256(titulo.encode()).hexdigest()[:8], 16)
    tono = semilla % 360
    tono2 = (tono + 35 + semilla % 50) % 360
    lineas = partir_titulo(titulo)
    tam = 92 if max(map(len, lineas)) <= 10 else 76
    inicio = 760 - (len(lineas) - 1) * tam * 0.55
    texto_titulo = "".join(
        f'<text x="80" y="{inicio + i * tam * 1.1:.0f}" fill="#fff" '
        f'font-family="Arial Black,Arial,sans-serif" font-size="{tam}" '
        f'font-weight="900">{html.escape(linea)}</text>'
        for i, linea in enumerate(lineas)
    )
    categoria = (videojuego.get("categoria", "") or "").split("·")[0].strip()
    anio = videojuego.get("anio_salida", "") or ""
    pie = " · ".join(dato for dato in (categoria.upper(), anio) if dato)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 1350" '
        f'role="img" aria-label="Portada ilustrativa de {html.escape(titulo, quote=True)}">'
        f'<defs><linearGradient id="f" x1="0" y1="0" x2="1" y2="1">'
        f'<stop stop-color="hsl({tono},62%,30%)"/>'
        f'<stop offset="1" stop-color="hsl({tono2},70%,9%)"/></linearGradient>'
        '<radialGradient id="l" cx=".75" cy=".2" r=".7">'
        '<stop stop-color="#fff" stop-opacity=".28"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
        '<rect width="900" height="1350" fill="url(#f)"/>'
        '<rect width="900" height="1350" fill="url(#l)"/>'
        f'<circle cx="{620 + semilla % 160}" cy="{300 + semilla % 140}" r="230" '
        'fill="none" stroke="#fff" stroke-opacity=".18" stroke-width="28"/>'
        f'<path d="M0 {1010 + semilla % 90} L900 {880 + semilla % 120} L900 1350 L0 1350Z" '
        'fill="#000" fill-opacity=".28"/>'
        '<rect x="80" y="80" width="150" height="64" rx="10" fill="#fff"/>'
        '<text x="155" y="125" text-anchor="middle" fill="#0b1b2b" '
        'font-family="Arial,sans-serif" font-size="34" font-weight="700">PS5</text>'
        f'{texto_titulo}'
        f'<text x="80" y="1180" fill="#fff" fill-opacity=".85" '
        f'font-family="Arial,sans-serif" font-size="34" letter-spacing="3">{html.escape(pie)}</text>'
        '<text x="80" y="1260" fill="#fff" fill-opacity=".55" '
        'font-family="Arial,sans-serif" font-size="24" letter-spacing="4">'
        'PORTADA ILUSTRATIVA</text></svg>'
    )


def imagen_sustitutiva_response(videojuego: dict[str, str] | str) -> Response:
    return Response(
        renderizar_imagen_sustitutiva(videojuego),
        mimetype="image/svg+xml",
        headers={
            # Corto para que el navegador vuelva a intentarlo si la fuente
            # de la portada estaba caída.
            "Cache-Control": "public, max-age=3600",
            "X-Image-Fallback": "true",
        },
    )


class CacheImagenes:
    """Caché LRU en memoria, limitada por bytes y segura entre hilos."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self._datos: OrderedDict[str, tuple[bytes, str]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, clave: str) -> tuple[bytes, str] | None:
        with self._lock:
            valor = self._datos.get(clave)
            if valor is not None:
                self._datos.move_to_end(clave)
            return valor

    def set(self, clave: str, contenido: bytes, tipo: str) -> None:
        if len(contenido) > self.max_bytes:
            return
        with self._lock:
            anterior = self._datos.pop(clave, None)
            if anterior is not None:
                self._bytes -= len(anterior[0])
            self._datos[clave] = (contenido, tipo)
            self._bytes += len(contenido)
            while self._bytes > self.max_bytes:
                _, (eliminado, _) = self._datos.popitem(last=False)
                self._bytes -= len(eliminado)

    def clear(self) -> None:
        with self._lock:
            self._datos.clear()
            self._bytes = 0


CACHE_IMAGENES = CacheImagenes(IMAGE_CACHE_MAX_BYTES)


def calcular_version_estaticos() -> str:
    resumen = hashlib.sha256()
    for path in sorted(STATIC_DIR.rglob("*")):
        if path.is_file():
            resumen.update(path.read_bytes())
    return resumen.hexdigest()[:12]


STATIC_VERSION = calcular_version_estaticos()


@app.context_processor
def variables_plantillas() -> dict[str, str]:
    return {"static_version": STATIC_VERSION}


@app.after_request
def optimizar_respuesta(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.endpoint == "static" and request.args.get("v") == STATIC_VERSION:
        # La URL cambia cuando cambia el contenido, así que se puede cachear un año.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return comprimir_respuesta(response)


def comprimir_respuesta(response: Response) -> Response:
    if (
        response.direct_passthrough
        or response.is_streamed
        or response.status_code != 200
        or "Content-Encoding" in response.headers
        or response.mimetype not in COMPRESSIBLE_TYPES
        or "gzip" not in request.headers.get("Accept-Encoding", "").lower()
    ):
        return response
    contenido = response.get_data()
    if len(contenido) < MIN_COMPRESS_BYTES:
        return response
    response.set_data(gzip.compress(contenido, compresslevel=6, mtime=0))
    response.headers["Content-Encoding"] = "gzip"
    response.vary.add("Accept-Encoding")
    return response


def url_imagen_permitida(image_url: str) -> str | None:
    """Devuelve la URL a descargar si apunta a una fuente de imágenes permitida."""
    parsed_url = urlsplit(image_url)
    if (
        parsed_url.hostname == "www.metacritic.com"
        and parsed_url.path.startswith("/a/img/resize/")
    ):
        # Metacritic sirve miniaturas redimensionadas; se pide el original.
        resized_path = parsed_url.path.removeprefix("/a/img/resize/")
        _, separator, original_path = resized_path.partition("/")
        if separator and original_path.startswith("catalog/"):
            image_url = urlunsplit(
                ("https", "www.metacritic.com", f"/a/img/{original_path}", "", "")
            )
            parsed_url = urlsplit(image_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname not in IMAGE_HOSTS
        or parsed_url.username
        or parsed_url.password
    ):
        return None
    return image_url


def descargar_imagen(image_url: str) -> tuple[bytes, str]:
    upstream_request = Request(image_url, headers=HTTP_HEADERS)
    with urlopen(upstream_request, timeout=10) as upstream:
        content_type = upstream.headers.get_content_type()
        final_url = urlsplit(upstream.geturl())
        if final_url.scheme != "https" or final_url.hostname not in IMAGE_HOSTS:
            raise URLError("La fuente redirigió a un destino no permitido.")
        if content_type not in IMAGE_TYPES:
            raise URLError("La fuente no devolvió una imagen.")
        content = upstream.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise URLError("La imagen supera el tamaño permitido.")
    return content, content_type


def leer_json_externo(url: str) -> object:
    with urlopen(
        Request(url, headers={**HTTP_HEADERS, "Accept": "application/json"}),
        timeout=LOOKUP_TIMEOUT_SECONDS,
    ) as respuesta:
        datos = respuesta.read(MAX_LOOKUP_BYTES + 1)
    if len(datos) > MAX_LOOKUP_BYTES:
        raise URLError("La respuesta de búsqueda es demasiado grande.")
    return json.loads(datos)


def articulo_wikipedia(videojuego: dict[str, str]) -> str | None:
    """Título del artículo de Wikipedia del juego, si su fuente apunta a uno."""
    fuente = urlsplit(videojuego.get("fuente", ""))
    if fuente.hostname != "en.wikipedia.org" or not fuente.path.startswith("/wiki/"):
        return None
    titulo = unquote(fuente.path.removeprefix("/wiki/")).replace("_", " ")
    if not titulo or titulo.startswith("List of"):
        return None
    return titulo


def portada_wikipedia(titulo_articulo: str) -> str | None:
    parametros = urlencode({
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "pageimages",
        "piprop": "thumbnail|original",
        "pithumbsize": "600",
        # Las portadas comerciales no tienen licencia libre; sin este
        # parámetro la API solo devuelve imágenes libres.
        "pilicense": "any",
        "redirects": "1",
        "titles": titulo_articulo,
    })
    datos = leer_json_externo(f"{WIKIPEDIA_API_URL}?{parametros}")
    paginas = datos.get("query", {}).get("pages", []) if isinstance(datos, dict) else []
    for pagina in paginas:
        imagen = pagina.get("thumbnail") or pagina.get("original") or {}
        fuente = imagen.get("source", "")
        if fuente:
            return fuente.split("?", 1)[0]
    return None


def clave_titulo(titulo: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", normalizar_texto(titulo)))


def portadas_steam(titulo: str) -> list[str]:
    """Portada vertical de Steam si hay un juego con el mismo nombre exacto."""
    parametros = urlencode({"term": titulo, "l": "english", "cc": "US"})
    datos = leer_json_externo(f"{STEAM_SEARCH_URL}?{parametros}")
    elementos = datos.get("items", []) if isinstance(datos, dict) else []
    buscado = clave_titulo(titulo)
    for elemento in elementos:
        if clave_titulo(str(elemento.get("name", ""))) != buscado:
            continue
        app_id = str(elemento.get("id", ""))
        if not app_id.isdecimal():
            continue
        miniatura = str(elemento.get("tiny_image", "")).split("?", 1)[0]
        carpeta = miniatura.rsplit("/", 1)[0] if "/" in miniatura else ""
        candidatas = [
            f"{carpeta}/library_600x900.jpg" if carpeta else "",
            f"{STEAM_APP_ASSETS}/{app_id}/library_600x900.jpg",
            f"{carpeta}/header.jpg" if carpeta else "",
            f"{STEAM_APP_ASSETS}/{app_id}/header.jpg",
        ]
        return list(dict.fromkeys(url for url in candidatas if url))
    return []


class CachePortadas:
    """Recuerda qué URL funcionó para cada juego y cuándo falló la búsqueda."""

    def __init__(self) -> None:
        self._url: dict[str, str] = {}
        self._fallos: dict[str, float] = {}
        self._lock = threading.Lock()

    def url(self, videojuego_id: str) -> str | None:
        with self._lock:
            return self._url.get(videojuego_id)

    def guardar(self, videojuego_id: str, url: str) -> None:
        with self._lock:
            self._url[videojuego_id] = url
            self._fallos.pop(videojuego_id, None)

    def fallo_reciente(self, videojuego_id: str) -> bool:
        with self._lock:
            momento = self._fallos.get(videojuego_id)
            return momento is not None and time.monotonic() - momento < COVER_RETRY_SECONDS

    def marcar_fallo(self, videojuego_id: str) -> None:
        with self._lock:
            self._fallos[videojuego_id] = time.monotonic()

    def clear(self) -> None:
        with self._lock:
            self._url.clear()
            self._fallos.clear()


CACHE_PORTADAS = CachePortadas()


def candidatas_portada(videojuego: dict[str, str]) -> Iterator[str]:
    """URLs de portada en orden de preferencia, buscándolas solo si hace falta.

    1. La imagen guardada en el CSV (3DJuegos, PlayStation, Metacritic…).
    2. La portada del artículo de Wikipedia del juego.
    3. La portada de Steam si el juego tiene el mismo nombre allí.
    """
    guardada = videojuego.get("imagen_url", "")
    if guardada and not guardada.startswith("/imagenes/"):
        permitida = url_imagen_permitida(guardada)
        if permitida:
            yield permitida
    busquedas = []
    articulo = articulo_wikipedia(videojuego)
    if articulo:
        busquedas.append(lambda: [portada_wikipedia(articulo)])
    busquedas.append(lambda: portadas_steam(videojuego.get("titulo", "")))
    for buscar in busquedas:
        try:
            urls = buscar()
        except (URLError, TimeoutError, OSError, ValueError) as error:
            logger.warning(
                "No se pudo buscar la portada de %s: %s", videojuego.get("id"), error
            )
            continue
        for url in urls:
            permitida = url_imagen_permitida(url) if url else None
            if permitida:
                yield permitida


def obtener_portada(videojuego: dict[str, str]) -> tuple[bytes, str] | None:
    videojuego_id = videojuego.get("id", "")
    conocida = CACHE_PORTADAS.url(videojuego_id)
    if conocida:
        cached = CACHE_IMAGENES.get(conocida)
        if cached is not None:
            return cached
        candidatas: Iterator[str] = iter([conocida])
    elif CACHE_PORTADAS.fallo_reciente(videojuego_id):
        return None
    else:
        candidatas = candidatas_portada(videojuego)

    for url in candidatas:
        cached = CACHE_IMAGENES.get(url)
        if cached is None:
            try:
                cached = descargar_imagen(url)
            except (URLError, TimeoutError, OSError) as error:
                logger.warning(
                    "No se pudo cargar la imagen de %s: %s", videojuego_id, error
                )
                continue
            CACHE_IMAGENES.set(url, *cached)
        CACHE_PORTADAS.guardar(videojuego_id, url)
        return cached
    CACHE_PORTADAS.marcar_fallo(videojuego_id)
    return None


@app.route("/", methods=["GET"])
def home():
    return render_home(gamer_mode=False)


@app.route("/gamers", methods=["GET"])
def home_gamers():
    return render_home(gamer_mode=True)


@app.route("/modo-oscuro", methods=["GET"])
def home_modo_oscuro():
    return render_home(gamer_mode=True)


@app.route("/clientes", methods=["GET"])
def pagina_clientes():
    csrf_token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    if not session.get("clientes_authenticated"):
        response = make_response(
            render_template("clientes_login.html", csrf_token=csrf_token)
        )
    else:
        response = make_response(
            render_template("clientes.html", csrf_token=csrf_token)
        )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/clientes/login", methods=["POST"])
def iniciar_sesion_clientes():
    csrf_token = session.get("csrf_token", "")
    submitted_token = request.form.get("csrf_token", "")
    if not csrf_token or not hmac.compare_digest(csrf_token, submitted_token):
        csrf_token = secrets.token_urlsafe(32)
        session["csrf_token"] = csrf_token
        return (
            render_template(
                "clientes_login.html",
                csrf_token=csrf_token,
                error="La sesión del formulario caducó. Recarga la página e inténtalo de nuevo.",
            ),
            400,
        )

    configured_password = os.environ.get("CLIENTES_PASSWORD")
    if not configured_password:
        return (
            render_template(
                "clientes_login.html",
                csrf_token=csrf_token,
                error="El acceso todavía no está configurado en el servidor.",
            ),
            503,
        )
    if not hmac.compare_digest(
        request.form.get("password", ""), configured_password
    ):
        return (
            render_template(
                "clientes_login.html",
                csrf_token=csrf_token,
                error="Contraseña incorrecta. Inténtalo de nuevo.",
            ),
            401,
        )

    session.clear()
    session["clientes_authenticated"] = True
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect(url_for("pagina_clientes"))


@app.route("/clientes/logout", methods=["POST"])
def cerrar_sesion_clientes():
    csrf_token = session.get("csrf_token", "")
    submitted_token = request.form.get("csrf_token", "")
    if (
        not session.get("clientes_authenticated")
        or not csrf_token
        or not hmac.compare_digest(csrf_token, submitted_token)
    ):
        return jsonify({"error": "No autorizado."}), 401
    session.clear()
    return redirect(url_for("pagina_clientes"))


@app.route("/api/clientes", methods=["GET"])
def api_clientes():
    if not session.get("clientes_authenticated"):
        return jsonify({"error": "Inicia sesión para consultar los clientes."}), 401

    url = os.environ.get("API_CLIENTES_URL")
    if not url:
        host = os.environ.get("API_CLIENTES_HOST", "127.0.0.1:5001")
        scheme = "https" if host != "127.0.0.1:5001" else "http"
        url = f"{scheme}://{host}/clientes"

    api_key = os.environ.get("CLIENTES_PASSWORD")
    if not api_key:
        return jsonify({"error": "El acceso a la API no está configurado."}), 503
    upstream_request = Request(
        url,
        headers={"Accept": "application/json", "X-API-Key": api_key},
    )
    try:
        with urlopen(
            upstream_request, timeout=CLIENT_API_TIMEOUT_SECONDS
        ) as upstream:
            content_type = upstream.headers.get_content_type()
            if content_type != "application/json":
                logger.warning("La API de clientes devolvió %s", content_type)
                return jsonify({"error": "La API de clientes no devolvió JSON."}), 502
            raw_data = upstream.read(MAX_CLIENT_DATA_BYTES + 1)
    except HTTPError as error:
        logger.warning("La API de clientes respondió HTTP %s", error.code)
        return jsonify({"error": "La API de clientes rechazó la petición."}), 502
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("No se pudo consultar la API de clientes: %s", error)
        return jsonify({"error": "La API de clientes no está disponible."}), 503

    if len(raw_data) > MAX_CLIENT_DATA_BYTES:
        return jsonify({"error": "La respuesta de clientes es demasiado grande."}), 502
    try:
        clientes = json.loads(raw_data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("La API de clientes devolvió JSON inválido: %s", error)
        return jsonify({"error": "La API de clientes devolvió JSON inválido."}), 502
    if not isinstance(clientes, list) or not all(
        isinstance(cliente, dict) for cliente in clientes
    ):
        return jsonify({"error": "La API de clientes devolvió un formato inválido."}), 502
    response = jsonify(clientes)
    response.headers["Cache-Control"] = "no-store"
    return response


def render_home(gamer_mode: bool):
    anios = sorted(
        (int(clave) for clave in ARCHIVOS if clave.isdecimal()),
    )
    # Se abre el año en curso; si no hay datos de ese año, el más reciente.
    anio_inicial = date.today().year if date.today().year in anios else (
        anios[-1] if anios else ""
    )
    response = make_response(
        render_template(
            "index.html",
            anios=anios,
            tiene_sin_fecha="sin_fecha" in ARCHIVOS,
            anio_inicial=anio_inicial,
            gamer_mode=gamer_mode,
            colecciones=COLECCIONES,
            generos=[(slug_genero, nombre) for slug_genero, nombre, _ in GENEROS],
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/anios", methods=["GET"])
def obtener_anios():
    return jsonify(
        {
            "anios": sorted(
                int(clave) for clave in ARCHIVOS if clave.isdecimal()
            ),
            "incluye_sin_fecha": "sin_fecha" in ARCHIVOS,
        }
    )


@app.route("/api/videojuegos", methods=["GET"])
def obtener_videojuegos():
    anio = request.args.get("anio", "").strip()
    if not anio and request.args.get("q", "").strip():
        # Buscar por nombre sin elegir año recorre todo el catálogo.
        anio = TODOS_LOS_ANIOS
    if not anio:
        return (
            jsonify(
                {
                    "error": (
                        "Indica un año, 'sin-fecha' o 'todos' en el parámetro anio."
                    )
                }
            ),
            400,
        )

    clave_anio = "sin_fecha" if anio == "sin-fecha" else anio
    videojuegos = VIDEOJUEGOS_POR_ANIO.get(clave_anio)
    if videojuegos is None:
        return jsonify({"error": "No existe un archivo para ese año."}), 404

    consulta = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", "").strip()
    mes = request.args.get("mes", "").strip()
    if mes and (not mes.isdecimal() or not 1 <= int(mes) <= 12):
        return jsonify({"error": "El mes debe ser un número entre 1 y 12."}), 400
    if mes:
        mes = f"{int(mes):02d}"
    if consulta or categoria or mes:
        cuerpo = serializar_json(
            filtrar_videojuegos(videojuegos, consulta, categoria, mes)
        )
    else:
        # El catálogo completo de cada año ya está serializado desde el arranque.
        cuerpo = JSON_POR_ANIO[clave_anio]
    return respuesta_json_cacheable(cuerpo)


def respuesta_json_cacheable(cuerpo: bytes) -> Response:
    response = Response(cuerpo, mimetype="application/json")
    response.headers["Cache-Control"] = f"public, max-age={API_CACHE_SECONDS}"
    response.add_etag()
    return response.make_conditional(request)


@app.route("/api/categorias", methods=["GET"])
def obtener_categorias():
    anio = request.args.get("anio", "").strip()
    clave_anio = "sin_fecha" if anio == "sin-fecha" else anio
    categorias = CATEGORIAS_POR_ANIO.get(clave_anio)
    if categorias is None:
        return jsonify({"error": "No existe un archivo para ese año."}), 404
    return respuesta_json_cacheable(
        json.dumps(
            {"anio": anio, "categorias": list(categorias)}, ensure_ascii=False
        ).encode()
    )


@app.route("/api/videojuegos/<videojuego_id>", methods=["GET"])
def obtener_videojuego(videojuego_id: str):
    videojuego = buscar_videojuego(videojuego_id)
    if videojuego is not None:
        return jsonify(videojuego)
    return jsonify({"error": "Videojuego no encontrado."}), 404


LIMITE_SIMILARES = 6
LIMITE_SIMILARES_MAX = 20


ARTICULOS_INICIALES = frozenset({"the", "a", "an", "el", "la", "los", "las"})
# Marcas que preceden a sagas distintas: "EA Sports FC" no es "EA Sports PGA Tour".
PREFIJOS_DE_MARCA = frozenset({"ea sports", "marvel s", "tom clancy", "sid meier", "disney pixar"})


def clave_saga(titulo: str) -> str:
    """Las dos primeras palabras del título: "Final Fantasy", "Elden Ring"...

    Basta para reconocer entregas de una misma saga sin una lista manual.
    """
    palabras = re.sub(r"[^a-z0-9 ]+", " ", normalizar_texto(titulo)).split()
    if palabras and palabras[0] in ARTICULOS_INICIALES:
        palabras = palabras[1:]
    if len(palabras) < 2:
        return ""
    longitud = 3 if " ".join(palabras[:2]) in PREFIJOS_DE_MARCA else 2
    return " ".join(palabras[:longitud]) if len(palabras) >= longitud else ""


def puntuar_similitud(
    base: dict[str, str], generos_base: set[str], candidato: dict[str, str]
) -> tuple[float, list[str]]:
    """Cuánto se parece un juego a otro y por qué, para explicarlo en la ficha."""
    generos = set(generos_de(candidato))
    comunes = generos_base & generos
    saga = clave_saga(base.get("titulo", ""))
    misma_saga = bool(saga) and saga == clave_saga(candidato.get("titulo", ""))
    if not comunes and not misma_saga:
        return 0.0, []
    # Jaccard: compartir 2 de 2 géneros pesa más que 1 de 4.
    puntos = 10 * len(comunes) / len(generos_base | generos) if generos else 0.0
    motivos = ["misma saga"] if misma_saga else []
    if misma_saga:
        puntos += 6
    motivos += [NOMBRES_GENERO[g] for g in GENEROS_POR_SLUG_ORDEN if g in comunes]
    estudio_base = normalizar_texto(base.get("desarrollador", "")).strip()
    if estudio_base and estudio_base == normalizar_texto(
        candidato.get("desarrollador", "")
    ).strip():
        puntos += 4
        motivos.append("mismo estudio")
    nota_candidato = nota(candidato, "puntuacion_metacritic_criticos")
    if nota_candidato is not None:
        # Entre dos juegos parecidos, se recomienda antes el mejor valorado.
        puntos += max(0.0, nota_candidato - 60) / 10
    if base.get("anio_salida", "").isdecimal() and candidato.get(
        "anio_salida", ""
    ).isdecimal():
        puntos -= abs(int(base["anio_salida"]) - int(candidato["anio_salida"])) * 0.3
    return puntos, motivos


def juegos_similares(videojuego: dict[str, str], limite: int) -> list[dict[str, object]]:
    base = videojuego
    resultado: list[dict[str, object]] = []
    # Para una expansión, lo primero que se recomienda es su juego base.
    juego_base = VIDEOJUEGOS_POR_ID.get(videojuego.get("juego_base_id", ""))
    if juego_base is not None:
        base = juego_base
        resultado.append(con_destacado(juego_base, "Juego base"))
    generos_base = set(generos_de(base))
    if not generos_base and not clave_saga(base.get("titulo", "")):
        return resultado[:limite]
    puntuados = []
    for candidato in VIDEOJUEGOS_POR_ID.values():
        if candidato["id"] in {videojuego["id"], base["id"]}:
            continue
        puntos, motivos = puntuar_similitud(base, generos_base, candidato)
        if puntos > 0:
            puntuados.append((puntos, candidato, motivos))
    puntuados.sort(key=lambda trio: (-trio[0], trio[1]["titulo"].casefold()))
    resultado.extend(
        con_destacado(candidato, " · ".join(motivos))
        for _, candidato, motivos in puntuados[: limite - len(resultado)]
    )
    return resultado


@app.route("/api/videojuegos/<videojuego_id>/similares", methods=["GET"])
def obtener_similares(videojuego_id: str):
    videojuego = buscar_videojuego(videojuego_id)
    if videojuego is None:
        return jsonify({"error": "Videojuego no encontrado."}), 404
    limite_texto = request.args.get("limite", str(LIMITE_SIMILARES)).strip()
    if not limite_texto.isdecimal() or not 1 <= int(limite_texto) <= LIMITE_SIMILARES_MAX:
        return jsonify({
            "error": f"El límite debe ser un número entre 1 y {LIMITE_SIMILARES_MAX}."
        }), 400
    cuerpo = {
        "id": videojuego["id"],
        "titulo": videojuego["titulo"],
        "generos": [NOMBRES_GENERO[g] for g in generos_de(videojuego)],
        "similares": juegos_similares(videojuego, int(limite_texto)),
    }
    return respuesta_json_cacheable(json.dumps(cuerpo, ensure_ascii=False).encode())


@app.route("/imagenes/<videojuego_id>", methods=["GET"])
def obtener_imagen_real(videojuego_id: str):
    videojuego = buscar_videojuego(videojuego_id)
    if videojuego is None:
        return jsonify({"error": "Videojuego no encontrado."}), 404
    portada = obtener_portada(videojuego)
    if portada is None:
        return imagen_sustitutiva_response(videojuego)
    content, content_type = portada
    return Response(
        content,
        mimetype=content_type,
        headers={"Cache-Control": f"public, max-age={IMAGE_CACHE_SECONDS}"},
    )


# ---------------------------------------------------------------------------
# Descubrir juegos: colecciones y géneros
# ---------------------------------------------------------------------------
# Las categorías del CSV vienen de Wikipedia, mezclan inglés y español y tienen
# cientos de variantes ("Action role-playing", "RPG", "Rol"...). Para que el
# usuario pueda explorar por género, cada categoría se asigna a una o varias
# familias buscando palabras clave en el texto ya normalizado.
GENEROS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("accion", "Acción", ("action", "accion", "hack and slash", "beat 'em up", "brawler", "parkour", "stealth", "mech", "combat", "arcade")),
    ("aventura", "Aventura", ("adventure", "aventura", "visual novel", "interactive drama", "interactive fiction", "interactive film", "walking simulator", "point-and-click", "exploration", "mystery", "detective", "thriller")),
    ("rol", "Rol (RPG)", ("role-playing", "role playing", "rpg", "soulslike", "dungeon crawl", "massively multiplayer")),
    ("shooter", "Shooter", ("shooter", "shoot 'em up", "run and gun", "bullet hell", "battle royale")),
    ("terror", "Terror", ("horror", "terror")),
    ("plataformas", "Plataformas", ("platform", "plataformas", "metroidvania")),
    ("deportes", "Deportes", ("sport", "football", "golf", "baseball", "basketball", "tennis", "rugby", "skateboarding", "snowboarding", "cycling")),
    ("conduccion", "Conducción", ("racing", "driving", "conduccion", "rally", "vehicular")),
    ("lucha", "Lucha", ("fighting", "fighter", "airdasher")),
    ("estrategia", "Estrategia", ("strategy", "tactic", "tower defense", "4x", "auto battler", "deck-building", "card", "board", "battle arena")),
    ("simulacion", "Simulación", ("simulation", "simulator", "sim ", "city-build", "management", "farm", "sandbox")),
    ("puzles", "Puzles", ("puzzle", "match-three", "brain", "metroidbrainia")),
    ("roguelike", "Roguelike", ("roguelike", "roguelite", "rougelike")),
    ("musical", "Musical y ritmo", ("rhythm", "music")),
    ("supervivencia", "Supervivencia", ("survival",)),
    ("casual", "Casual y familiar", ("casual", "party", "family", "social deduction", "incremental", "compilation")),
)
NOMBRES_GENERO = {slug: nombre for slug, nombre, _ in GENEROS}
GENEROS_POR_SLUG_ORDEN = tuple(slug for slug, _, _ in GENEROS)
COLECCIONES_DIR = BASE_DIR / "data" / "colecciones"
LIMITE_COLECCION = 50
LIMITE_COLECCION_MAX = 200
DIAS_RECIENTES = 90


@dataclass(frozen=True, slots=True)
class Coleccion:
    slug: str
    titulo: str
    descripcion: str
    criterio: str


COLECCIONES: tuple[Coleccion, ...] = (
    Coleccion("mejor-valorados", "Mejor valorados por la crítica",
              "Juegos ordenados por su nota de prensa en Metacritic.",
              "Nota de críticos de Metacritic (0-100), de mayor a menor."),
    Coleccion("mas-descargados", "Más descargados",
              "Top 20 anual de la PlayStation Store en Europa publicado por Sony.",
              "Ranking oficial anual de descargas de PS5 (región EU) del PlayStation Blog. Sin 'anio' se muestra el último año."),
    Coleccion("goty", "Juegos del año (GOTY)",
              "Ganadores del premio a Juego del año de The Game Awards.",
              "Ganador de Game of the Year en The Game Awards de cada año."),
    Coleccion("mas-esperados", "Lanzamientos más esperados",
              "Los próximos juegos de PS5 con más seguidores esperándolos.",
              "Seguidores aproximados en releases.com (lista de 2027, consultada el 20/11/2026)."),
    Coleccion("proximos", "Próximos lanzamientos",
              "Juegos con fecha de salida a partir de mañana, del más cercano al más lejano.",
              "Fecha de salida posterior a hoy; los que solo tienen año van al final."),
    Coleccion("recientes", "Novedades",
              f"Juegos publicados en los últimos {DIAS_RECIENTES} días.",
              "Fecha de salida entre hoy y los últimos 90 días, del más nuevo al más antiguo."),
    Coleccion("expansiones-dlc", "Expansiones y DLC",
              "Contenido adicional destacado de juegos de PS5, enlazado a su juego base.",
              "Selección curada de expansiones y DLC, del más reciente al más antiguo."),
    Coleccion("resenas-usuarios", "Mejores reseñas de usuarios",
              "Juegos ordenados por la nota de los usuarios de Metacritic.",
              "Nota de usuarios de Metacritic (0-10). Por ahora hay pocos juegos con este dato."),
)
COLECCIONES_POR_SLUG = {coleccion.slug: coleccion for coleccion in COLECCIONES}

GENEROS_POR_JUEGO: dict[str, tuple[str, ...]] = {}
EXTRAS_POR_ID: dict[str, dict[str, str]] = {}
GOTY: tuple[dict[str, str], ...] = ()
MAS_DESCARGADOS: tuple[dict[str, str], ...] = ()
MAS_ESPERADOS: tuple[dict[str, str], ...] = ()
EXPANSIONES: tuple[dict[str, str], ...] = ()


def hoy() -> date:
    """Separado para que los tests puedan fijar la fecha."""
    return date.today()


def generos_de_categoria(categoria: str) -> tuple[str, ...]:
    texto = normalizar_categoria(categoria)
    if not texto or "{" in texto:
        return ()
    texto = f"{texto} "
    return tuple(
        slug for slug, _, claves in GENEROS
        if any(clave in texto for clave in claves)
    )


def generos_de(videojuego: dict[str, str]) -> tuple[str, ...]:
    return GENEROS_POR_JUEGO.get(videojuego.get("id", "")) or generos_de_categoria(
        videojuego.get("categoria", "")
    )


def leer_coleccion(nombre: str) -> tuple[dict[str, str], ...]:
    path = COLECCIONES_DIR / nombre
    if not path.exists():
        logger.warning("No existe el archivo de colección %s", path)
        return ()
    with path.open(encoding="utf-8-sig", newline="") as archivo:
        return tuple(csv.DictReader(archivo))


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar_texto(texto)).strip("-")


def registro_extra(fila: dict[str, str], **campos: str) -> dict[str, str]:
    """Ficha mínima para juegos citados en una colección que no están en el catálogo."""
    registro = {
        "id": f"extra-{slug(fila['titulo'])}",
        "titulo": fila["titulo"],
        "plataforma": "PS5",
        "anio_salida": "",
        "fecha_salida": "",
        "desarrollador": "",
        "resumen": "",
        "estado": "fecha_publicada",
        "fuente": fila.get("fuente", ""),
        "categoria": "",
        "imagen_url": "",
        "en_catalogo": "no",
    }
    registro.update(campos)
    return registro


def cargar_colecciones() -> None:
    """Lee las listas curadas y crea fichas para lo que no está en el catálogo."""
    global GOTY, MAS_DESCARGADOS, MAS_ESPERADOS, EXPANSIONES
    global EXTRAS_POR_ID, GENEROS_POR_JUEGO
    EXTRAS_POR_ID = {}
    GOTY = leer_coleccion("goty.csv")
    MAS_DESCARGADOS = leer_coleccion("mas_descargados.csv")
    MAS_ESPERADOS = leer_coleccion("mas_esperados.csv")
    EXPANSIONES = leer_coleccion("expansiones_dlc.csv")

    for fila in (*MAS_DESCARGADOS, *MAS_ESPERADOS):
        if fila["id"] in VIDEOJUEGOS_POR_ID:
            continue
        if fila["id"]:
            logger.warning("La colección cita un id inexistente: %s", fila["id"])
        extra = registro_extra(fila)
        fila["id"] = extra["id"]
        EXTRAS_POR_ID.setdefault(extra["id"], extra)

    for fila in EXPANSIONES:
        base = VIDEOJUEGOS_POR_ID.get(fila["juego_base_id"], {})
        EXTRAS_POR_ID[fila["id"]] = registro_extra(
            fila,
            id=fila["id"],
            anio_salida=fila["fecha_salida"][:4],
            fecha_salida=fila["fecha_salida"],
            desarrollador=fila["desarrollador"],
            resumen=fila["resumen"],
            categoria=base.get("categoria", ""),
            tipo=fila["tipo"],
            juego_base_id=fila["juego_base_id"],
            juego_base=base.get("titulo", ""),
            en_catalogo="si",
        )

    GENEROS_POR_JUEGO = {
        videojuego_id: generos_de_categoria(videojuego.get("categoria", ""))
        for videojuego_id, videojuego in (
            *VIDEOJUEGOS_POR_ID.items(), *EXTRAS_POR_ID.items()
        )
    }


def nota(videojuego: dict[str, str], campo: str) -> float | None:
    try:
        valor = float(videojuego.get(campo, "") or "nan")
    except ValueError:
        return None
    return valor if valor == valor and valor > 0 else None


def fecha_de(videojuego: dict[str, str]) -> date | None:
    try:
        return date.fromisoformat(videojuego.get("fecha_salida", ""))
    except ValueError:
        return None


def todos_los_juegos() -> Iterator[dict[str, str]]:
    return iter(VIDEOJUEGOS_POR_ID.values())


def con_destacado(
    videojuego: dict[str, str], destacado: str, **extra: object
) -> dict[str, object]:
    return {
        **videojuego,
        "generos": [NOMBRES_GENERO[g] for g in generos_de(videojuego)],
        "destacado": destacado,
        **extra,
    }


def ficha_por_id(videojuego_id: str) -> dict[str, str] | None:
    return VIDEOJUEGOS_POR_ID.get(videojuego_id) or EXTRAS_POR_ID.get(videojuego_id)


def juegos_coleccion(slug_coleccion: str, anio: str) -> list[dict[str, object]]:
    """Devuelve la colección ya ordenada, antes de filtrar por género o límite."""
    if slug_coleccion == "mejor-valorados":
        puntuados = [
            (valor, juego) for juego in todos_los_juegos()
            if (valor := nota(juego, "puntuacion_metacritic_criticos")) is not None
            and (not anio or juego.get("anio_salida") == anio)
        ]
        puntuados.sort(key=lambda par: (-par[0], par[1]["titulo"].casefold()))
        return [
            con_destacado(juego, f"{valor:.0f} Metacritic")
            for valor, juego in puntuados
        ]

    if slug_coleccion == "resenas-usuarios":
        puntuados = [
            (valor, juego) for juego in todos_los_juegos()
            if (valor := nota(juego, "puntuacion_metacritic_usuarios")) is not None
            and (not anio or juego.get("anio_salida") == anio)
        ]
        puntuados.sort(key=lambda par: (-par[0], par[1]["titulo"].casefold()))
        return [
            con_destacado(juego, f"{valor:.1f} usuarios")
            for valor, juego in puntuados
        ]

    if slug_coleccion == "mas-descargados":
        anios = sorted({fila["anio"] for fila in MAS_DESCARGADOS}, reverse=True)
        anio_ranking = anio or (anios[0] if anios else "")
        return [
            con_destacado(
                juego,
                f"#{fila['posicion']} descargas EU {fila['anio']}",
                ranking={"anio": int(fila["anio"]), "posicion": int(fila["posicion"]),
                         "region": fila["region"], "fuente": fila["fuente"]},
            )
            for fila in MAS_DESCARGADOS
            if fila["anio"] == anio_ranking and (juego := ficha_por_id(fila["id"]))
        ]

    if slug_coleccion == "goty":
        return [
            con_destacado(
                juego,
                f"GOTY {fila['anio']}",
                premio={"anio": int(fila["anio"]), "nombre": fila["premio"],
                        "nota": fila["nota"], "fuente": fila["fuente"]},
            )
            for fila in sorted(GOTY, key=lambda fila: fila["anio"], reverse=True)
            if (not anio or fila["anio"] == anio) and (juego := ficha_por_id(fila["id"]))
        ]

    if slug_coleccion == "mas-esperados":
        resultado = []
        for fila in sorted(MAS_ESPERADOS, key=lambda fila: int(fila["posicion"])):
            juego = ficha_por_id(fila["id"])
            if juego is None or (anio and juego.get("anio_salida") != anio):
                continue
            # Si ya salió (p. ej. tras actualizar fechas), deja de ser "esperado".
            fecha = fecha_de(juego)
            if fecha is not None and fecha <= hoy():
                continue
            resultado.append(con_destacado(
                juego,
                # releases.com redondea a "1K" a partir de mil seguidores.
                f"{int(fila['seguidores_aprox']):,}{'+' if int(fila['seguidores_aprox']) >= 1000 else ''} seguidores".replace(",", "."),
                expectacion={"posicion": int(fila["posicion"]),
                             "seguidores_aprox": int(fila["seguidores_aprox"]),
                             "fuente": fila["fuente"],
                             "consultado_el": fila["consultado_el"]},
            ))
        return resultado

    if slug_coleccion == "proximos":
        hoy_ = hoy()
        con_fecha = []
        solo_anio = []
        for juego in todos_los_juegos():
            if anio and juego.get("anio_salida") != anio:
                continue
            fecha = fecha_de(juego)
            if fecha is not None:
                if fecha > hoy_:
                    con_fecha.append((fecha, juego))
            elif juego.get("anio_salida", "").isdecimal() and int(
                juego["anio_salida"]
            ) > hoy_.year:
                solo_anio.append(juego)
        con_fecha.sort(key=lambda par: (par[0], par[1]["titulo"].casefold()))
        solo_anio.sort(key=lambda juego: (juego["anio_salida"], juego["titulo"].casefold()))
        return [
            con_destacado(juego, f"Sale el {fecha.strftime('%d/%m/%Y')}")
            for fecha, juego in con_fecha
        ] + [
            con_destacado(juego, f"Previsto para {juego['anio_salida']}")
            for juego in solo_anio
        ]

    if slug_coleccion == "recientes":
        hoy_ = hoy()
        recientes = [
            (fecha, juego) for juego in todos_los_juegos()
            if (fecha := fecha_de(juego)) is not None
            and 0 <= (hoy_ - fecha).days <= DIAS_RECIENTES
            and (not anio or juego.get("anio_salida") == anio)
        ]
        recientes.sort(key=lambda par: (par[0], par[1]["titulo"]), reverse=True)
        return [
            con_destacado(juego, f"Salió el {fecha.strftime('%d/%m/%Y')}")
            for fecha, juego in recientes
        ]

    if slug_coleccion == "expansiones-dlc":
        expansiones = [
            EXTRAS_POR_ID[fila["id"]] for fila in EXPANSIONES
            if not anio or fila["fecha_salida"].startswith(anio)
        ]
        expansiones.sort(key=lambda juego: juego["fecha_salida"], reverse=True)
        return [
            con_destacado(juego, f"{juego['tipo']} de {juego['juego_base'] or 'otro juego'}")
            for juego in expansiones
        ]

    return []


def error_json(mensaje: str, codigo: int):
    return jsonify({"error": mensaje}), codigo


@app.route("/api/generos", methods=["GET"])
def obtener_generos():
    """Géneros unificados con el número de juegos del catálogo en cada uno."""
    contador = Counter(
        genero
        for videojuego_id in VIDEOJUEGOS_POR_ID
        for genero in GENEROS_POR_JUEGO.get(videojuego_id, ())
    )
    return respuesta_json_cacheable(json.dumps(
        [
            {"slug": slug_genero, "nombre": nombre, "total": contador[slug_genero]}
            for slug_genero, nombre, _ in GENEROS
        ],
        ensure_ascii=False,
    ).encode())


@app.route("/api/descubrir", methods=["GET"])
def listar_colecciones():
    return jsonify([
        {
            "slug": coleccion.slug,
            "titulo": coleccion.titulo,
            "descripcion": coleccion.descripcion,
            "url": url_for("obtener_coleccion", slug_coleccion=coleccion.slug),
        }
        for coleccion in COLECCIONES
    ])


@app.route("/api/descubrir/<slug_coleccion>", methods=["GET"])
def obtener_coleccion(slug_coleccion: str):
    coleccion = COLECCIONES_POR_SLUG.get(slug_coleccion)
    if coleccion is None:
        return error_json(
            "Colección no encontrada. Consulta /api/descubrir para ver las disponibles.",
            404,
        )
    anio = request.args.get("anio", "").strip()
    if anio and not (anio.isdecimal() and len(anio) == 4):
        return error_json("El año debe tener cuatro cifras, por ejemplo 2024.", 400)
    genero = request.args.get("genero", "").strip()
    if genero and genero not in NOMBRES_GENERO:
        return error_json(
            "Género no válido. Consulta /api/generos para ver los disponibles.", 400
        )
    limite_texto = request.args.get("limite", str(LIMITE_COLECCION)).strip()
    if not limite_texto.isdecimal() or not 1 <= int(limite_texto) <= LIMITE_COLECCION_MAX:
        return error_json(
            f"El límite debe ser un número entre 1 y {LIMITE_COLECCION_MAX}.", 400
        )

    juegos = juegos_coleccion(coleccion.slug, anio)
    if genero:
        juegos = [juego for juego in juegos if NOMBRES_GENERO[genero] in juego["generos"]]
    total = len(juegos)
    juegos = juegos[: int(limite_texto)]
    for posicion, juego in enumerate(juegos, start=1):
        juego["posicion"] = posicion

    cuerpo = {
        "coleccion": coleccion.slug,
        "titulo": coleccion.titulo,
        "descripcion": coleccion.descripcion,
        "criterio": coleccion.criterio,
        "filtros": {"anio": anio or None, "genero": genero or None},
        "total": total,
        "juegos": juegos,
    }
    if coleccion.slug == "mas-descargados":
        cuerpo["anios_disponibles"] = sorted(
            {int(fila["anio"]) for fila in MAS_DESCARGADOS}, reverse=True
        )
    return respuesta_json_cacheable(json.dumps(cuerpo, ensure_ascii=False).encode())


@app.route("/videojuegos.csv", methods=["GET"])
def descargar_videojuegos_csv():
    anio = request.args.get("anio", "").strip()
    if not anio:
        return (
            jsonify({"error": "Indica el año del CSV en el parámetro anio."}),
            400,
        )
    path = archivo_para_anio(anio)
    if path is None:
        return jsonify({"error": "No existe un archivo para ese año."}), 404
    return send_file(
        path,
        mimetype="application/gzip" if path.suffix == ".gz" else "text/csv",
        as_attachment=True,
        download_name=path.name.removeprefix("videojuegos_"),
    )


# ---------------------------------------------------------------------------
# Documentación de la API
# ---------------------------------------------------------------------------
# Una sola descripción sirve para la página /api/docs y para /api/openapi.json,
# así las dos no se desincronizan. Un test comprueba que toda ruta pública /api
# aparece aquí.
@dataclass(frozen=True, slots=True)
class Parametro:
    nombre: str
    lugar: str  # "query" o "path"
    tipo: str
    descripcion: str
    requerido: bool = False
    ejemplo: str = ""


@dataclass(frozen=True, slots=True)
class Endpoint:
    ruta: str
    titulo: str
    descripcion: str
    formato: str = "JSON"
    parametros: tuple[Parametro, ...] = ()
    ejemplos: tuple[str, ...] = ()
    errores: tuple[tuple[int, str], ...] = ()
    grupo: str = "Catálogo"

    @property
    def ancla(self) -> str:
        return slug(self.ruta.replace("<", "").replace(">", "")) or "inicio"


PARAMETRO_ANIO_COLECCION = Parametro(
    "anio", "query", "integer", "Solo juegos de ese año (cuatro cifras).", ejemplo="2024"
)
PARAMETRO_GENERO = Parametro(
    "genero", "query", "string", "Slug de género de /api/generos, por ejemplo rol o terror.",
    ejemplo="rol",
)
ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        "/api/anios", "Años disponibles",
        "Lista los años con archivo de catálogo y si existe el archivo de juegos sin fecha.",
        ejemplos=("/api/anios",),
    ),
    Endpoint(
        "/api/videojuegos", "Buscar y listar videojuegos",
        "Devuelve los juegos de un año, o de todo el catálogo con anio=todos. "
        "La búsqueda por nombre tolera tildes, mayúsculas y pequeñas erratas. "
        "Si se indica q sin anio, se busca en todos los años.",
        parametros=(
            Parametro("anio", "query", "string", "Año (2024), 'sin-fecha' o 'todos'. Obligatorio salvo que se indique q.", ejemplo="2024"),
            Parametro("q", "query", "string", "Texto a buscar en el título.", ejemplo="resident evil"),
            Parametro("categoria", "query", "string", "Categoría exacta tal y como la devuelve /api/categorias."),
            Parametro("mes", "query", "integer", "Mes de salida, de 1 a 12.", ejemplo="10"),
        ),
        ejemplos=("/api/videojuegos?anio=2024&mes=10", "/api/videojuegos?q=resident evil"),
        errores=((400, "Falta el año o el mes no es válido."), (404, "No existe archivo para ese año.")),
    ),
    Endpoint(
        "/api/videojuegos/<videojuego_id>", "Ficha de un videojuego",
        "Devuelve un juego por su identificador. También sirve para expansiones y "
        "para los juegos citados en colecciones que no están en el catálogo.",
        parametros=(Parametro("videojuego_id", "path", "string", "Identificador del juego.", True, "elden-ring"),),
        ejemplos=("/api/videojuegos/elden-ring",),
        errores=((404, "No existe ningún juego con ese identificador."),),
    ),
    Endpoint(
        "/api/videojuegos/<videojuego_id>/similares", "Juegos parecidos",
        "Recomienda juegos por saga, géneros en común, estudio, nota y cercanía de año. "
        "Cada recomendación explica el motivo en el campo destacado.",
        parametros=(
            Parametro("videojuego_id", "path", "string", "Identificador del juego.", True, "elden-ring"),
            Parametro("limite", "query", "integer", f"Número de recomendaciones (1-{LIMITE_SIMILARES_MAX}, por defecto {LIMITE_SIMILARES}).", ejemplo="6"),
        ),
        ejemplos=("/api/videojuegos/elden-ring/similares",),
        errores=((400, "Límite fuera de rango."), (404, "No existe ningún juego con ese identificador.")),
    ),
    Endpoint(
        "/api/categorias", "Categorías de un año",
        "Categorías originales (de Wikipedia) presentes en un año, para usarlas en el filtro categoria.",
        parametros=(Parametro("anio", "query", "string", "Año, 'sin-fecha' o 'todos'.", True, "2024"),),
        ejemplos=("/api/categorias?anio=2024",),
        errores=((404, "No existe archivo para ese año."),),
    ),
    Endpoint(
        "/api/generos", "Géneros unificados",
        "Los 16 géneros en español que agrupan las categorías de Wikipedia, con el número de juegos de cada uno.",
        ejemplos=("/api/generos",), grupo="Descubrir",
    ),
    Endpoint(
        "/api/descubrir", "Colecciones disponibles",
        "Lista las colecciones para descubrir juegos con su descripción y su URL.",
        ejemplos=("/api/descubrir",), grupo="Descubrir",
    ),
    Endpoint(
        "/api/descubrir/<slug_coleccion>", "Juegos de una colección",
        "Juegos de una colección ya ordenados por su criterio: "
        + ", ".join(coleccion.slug for coleccion in COLECCIONES) + ".",
        parametros=(
            Parametro("slug_coleccion", "path", "string", "Colección de /api/descubrir.", True, "mejor-valorados"),
            PARAMETRO_GENERO,
            PARAMETRO_ANIO_COLECCION,
            Parametro("limite", "query", "integer", f"Máximo de juegos (1-{LIMITE_COLECCION_MAX}, por defecto {LIMITE_COLECCION}).", ejemplo="10"),
        ),
        ejemplos=("/api/descubrir/mejor-valorados?genero=rol&limite=10", "/api/descubrir/goty"),
        errores=((400, "Año, género o límite no válidos."), (404, "La colección no existe.")),
        grupo="Descubrir",
    ),
    Endpoint(
        "/imagenes/<videojuego_id>", "Portada de un videojuego",
        "Portada del juego (oficial si se encuentra; si no, una ilustración SVG generada con su título).",
        formato="Imagen",
        parametros=(Parametro("videojuego_id", "path", "string", "Identificador del juego.", True, "astro-bot"),),
        ejemplos=("/imagenes/astro-bot",),
        errores=((404, "No existe ningún juego con ese identificador."),),
        grupo="Archivos",
    ),
    Endpoint(
        "/videojuegos.csv", "Descargar el CSV de un año",
        "Descarga el archivo original del catálogo de un año (CSV o CSV comprimido).",
        formato="CSV",
        parametros=(Parametro("anio", "query", "string", "Año o 'sin-fecha'.", True, "2026"),),
        ejemplos=("/videojuegos.csv?anio=2026",),
        errores=((400, "Falta el año."), (404, "No existe archivo para ese año.")),
        grupo="Archivos",
    ),
    Endpoint(
        "/api/openapi.json", "Especificación OpenAPI",
        "Esta misma documentación en formato OpenAPI 3.1, para importarla en Postman, Insomnia o Swagger.",
        ejemplos=("/api/openapi.json",), grupo="Documentación",
    ),
)


def especificacion_openapi() -> dict[str, object]:
    tipos_contenido = {"JSON": "application/json", "CSV": "text/csv", "Imagen": "image/*"}
    rutas: dict[str, object] = {}
    for endpoint in ENDPOINTS:
        ruta = re.sub(r"<([^>]+)>", r"{\1}", endpoint.ruta)
        respuestas: dict[str, object] = {
            "200": {
                "description": "Respuesta correcta.",
                "content": {tipos_contenido[endpoint.formato]: {}},
            }
        }
        for codigo, mensaje in endpoint.errores:
            respuestas[str(codigo)] = {
                "description": mensaje,
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
            }
        rutas[ruta] = {
            "get": {
                "summary": endpoint.titulo,
                "description": endpoint.descripcion,
                "tags": [endpoint.grupo],
                "operationId": endpoint.ancla,
                "parameters": [
                    {
                        "name": parametro.nombre,
                        "in": parametro.lugar,
                        "required": parametro.requerido or parametro.lugar == "path",
                        "description": parametro.descripcion,
                        "schema": {"type": parametro.tipo},
                        **({"example": parametro.ejemplo} if parametro.ejemplo else {}),
                    }
                    for parametro in endpoint.parametros
                ],
                "responses": respuestas,
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "API Calendario PS5",
            "version": "1.0.0",
            "description": "Catálogo de videojuegos de PS5 por año, con búsqueda, fichas, colecciones y recomendaciones.",
        },
        "servers": [{"url": request.host_url.rstrip("/")}],
        "paths": rutas,
        "components": {
            "schemas": {
                "Error": {"type": "object", "properties": {"error": {"type": "string"}}}
            }
        },
    }


@app.route("/api/openapi.json", methods=["GET"])
def obtener_openapi():
    return jsonify(especificacion_openapi())


@app.route("/api/docs", methods=["GET"])
def documentacion_api():
    grupos: dict[str, list[Endpoint]] = {}
    for endpoint in ENDPOINTS:
        grupos.setdefault(endpoint.grupo, []).append(endpoint)
    return render_template(
        "docs.html",
        grupos=grupos,
        base_url=request.host_url.rstrip("/"),
        total=len(ENDPOINTS),
    )


cargar_catalogo()
cargar_colecciones()


if __name__ == "__main__":
    app.run(debug=False, port=5000)
