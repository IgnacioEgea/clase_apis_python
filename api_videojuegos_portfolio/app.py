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


def cargar_catalogo() -> None:
    """Lee los CSV una sola vez y prepara índices, categorías y JSON."""
    global ARCHIVOS, VIDEOJUEGOS_POR_ANIO, VIDEOJUEGOS_POR_ID
    global FICHAS_BUSQUEDA, CATEGORIAS_POR_ANIO, JSON_POR_ANIO
    ARCHIVOS = archivos_disponibles()
    VIDEOJUEGOS_POR_ANIO = {
        anio: tuple(leer_videojuegos(path))
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


def buscar_videojuego(videojuego_id: str) -> dict[str, str] | None:
    return VIDEOJUEGOS_POR_ID.get(videojuego_id)


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


def renderizar_imagen_sustitutiva(titulo: str) -> str:
    texto = html.escape(titulo)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 1350" '
        'role="img" aria-label="Imagen no disponible para '
        f'{html.escape(titulo, quote=True)}">'
        '<defs><linearGradient id="fondo" x2="1" y2="1">'
        '<stop stop-color="#123c49"/><stop offset="1" stop-color="#091b2b"/>'
        '</linearGradient></defs><rect width="900" height="1350" '
        'fill="url(#fondo)"/><circle cx="450" cy="450" r="220" '
        'fill="none" stroke="#57c3aa" stroke-width="10" opacity=".7"/>'
        '<path d="M280 480h340l-55 170H335z" fill="#57c3aa" opacity=".8"/>'
        '<text x="450" y="790" text-anchor="middle" fill="#fff" '
        'font-family="Arial,sans-serif" font-size="46" font-weight="700">'
        f'{texto}</text><text x="450" y="890" text-anchor="middle" '
        'fill="#b5ced2" font-family="Arial,sans-serif" font-size="25">'
        'IMAGEN ORIGINAL NO DISPONIBLE</text></svg>'
    )


def imagen_sustitutiva_response(titulo: str) -> Response:
    return Response(
        renderizar_imagen_sustitutiva(titulo),
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
    if not anio:
        return (
            jsonify(
                {
                    "error": (
                        "Indica un año o 'sin-fecha' en el parámetro anio."
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


@app.route("/imagenes/<videojuego_id>", methods=["GET"])
def obtener_imagen_real(videojuego_id: str):
    videojuego = buscar_videojuego(videojuego_id)
    if videojuego is None:
        return jsonify({"error": "Videojuego no encontrado."}), 404
    portada = obtener_portada(videojuego)
    if portada is None:
        return imagen_sustitutiva_response(videojuego["titulo"])
    content, content_type = portada
    return Response(
        content,
        mimetype=content_type,
        headers={"Cache-Control": f"public, max-age={IMAGE_CACHE_SECONDS}"},
    )


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


cargar_catalogo()


if __name__ == "__main__":
    app.run(debug=False, port=5000)
