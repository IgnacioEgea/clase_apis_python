import csv
import gzip
import hmac
import html
import json
import logging
import os
import secrets
import unicodedata
from collections.abc import Iterator
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
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
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "false"
).casefold() in {"1", "true", "yes"}
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "videojuegos"
ARCHIVOS: dict[str, Path] = {}
VIDEOJUEGOS_POR_ANIO: dict[str, tuple[dict[str, str], ...]] = {}
VIDEOJUEGOS_POR_ID: dict[str, dict[str, str]] = {}
IMAGE_HOSTS = {
    "i.3djuegos.com",
    "image.api.playstation.com",
    "gmedia.playstation.com",
}
IMAGE_TYPES = {"image/avif", "image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_CLIENT_DATA_BYTES = 2 * 1024 * 1024
CLIENT_API_TIMEOUT_SECONDS = 10
logger = logging.getLogger(__name__)


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


def cargar_catalogo() -> None:
    global ARCHIVOS, VIDEOJUEGOS_POR_ANIO, VIDEOJUEGOS_POR_ID
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


cargar_catalogo()


def buscar_videojuego(videojuego_id: str) -> dict[str, str] | None:
    return VIDEOJUEGOS_POR_ID.get(videojuego_id)


def normalizar_texto(texto: str) -> str:
    texto_sin_tildes = unicodedata.normalize("NFD", texto.casefold())
    return "".join(
        caracter
        for caracter in texto_sin_tildes
        if unicodedata.category(caracter) != "Mn"
    )


def coincide_busqueda(videojuego: dict[str, str], consulta: str) -> bool:
    terminos = normalizar_texto(consulta).split()
    titulo = normalizar_texto(
        f"{videojuego.get('titulo', '')} {videojuego.get('id', '')}"
    )
    if not terminos:
        return False
    if " ".join(terminos) in titulo:
        return True

    palabras_titulo = titulo.split()
    return all(
        any(
            termino in palabra
            or (
                len(termino) >= 3
                and SequenceMatcher(None, termino, palabra).ratio() >= 0.82
                and (
                    len(termino) >= 5
                    or termino[:3] == palabra[:3]
                )
            )
            for palabra in palabras_titulo
        )
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
    for videojuego in videojuegos:
        if consulta and not coincide_busqueda(videojuego, consulta):
            continue
        if categoria and normalizar_categoria(
            videojuego.get("categoria", "")
        ) != normalizar_categoria(categoria):
            continue
        if mes and not videojuego.get("fecha_salida", "").startswith(
            f"{videojuego.get('anio_salida', '')}-{mes}-"
        ):
            continue
        yield videojuego


def serializar_videojuegos(
    videojuegos: tuple[dict[str, str], ...],
    consulta: str,
    categoria: str = "",
    mes: str = "",
) -> Iterator[str]:
    yield "["
    primero = True
    for videojuego in filtrar_videojuegos(videojuegos, consulta, categoria, mes):
        if not primero:
            yield ","
        yield json.dumps(videojuego, ensure_ascii=False)
        primero = False
    yield "]"


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
            "Cache-Control": "public, max-age=86400",
            "X-Image-Fallback": "true",
        },
    )


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
    response = make_response(
        render_template(
            "index.html",
            anios=anios,
            tiene_sin_fecha="sin_fecha" in ARCHIVOS,
            anio_inicial=anios[-1] if anios else "",
            anio_actual=2026,
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
    return Response(
        serializar_videojuegos(videojuegos, consulta, categoria, mes),
        mimetype="application/json",
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
    image_url = videojuego.get("imagen_url", "")
    if image_url.startswith("/imagenes/") or not image_url:
        return imagen_sustitutiva_response(videojuego["titulo"])
    parsed_url = urlsplit(image_url)
    if (
        parsed_url.hostname == "www.metacritic.com"
        and parsed_url.path.startswith("/a/img/resize/")
    ):
        resized_path = parsed_url.path.removeprefix("/a/img/resize/")
        _, separator, original_path = resized_path.partition("/")
        if separator and original_path.startswith("catalog/"):
            image_url = urlunsplit(
                ("https", "www.metacritic.com", f"/a/img/{original_path}", "", "")
            )
            parsed_url = urlsplit(image_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname not in IMAGE_HOSTS | {"www.metacritic.com"}
        or parsed_url.username
        or parsed_url.password
    ):
        logger.warning("No hay una fuente de imagen permitida para %s", videojuego_id)
        return imagen_sustitutiva_response(videojuego["titulo"])

    upstream_request = Request(
        image_url,
        headers={"User-Agent": "PS5CalendarUniversityProject/1.0"},
    )
    try:
        with urlopen(upstream_request, timeout=10) as upstream:
            content_type = upstream.headers.get_content_type()
            final_url = urlsplit(upstream.geturl())
            if (
                final_url.scheme != "https"
                or final_url.hostname not in IMAGE_HOSTS | {"www.metacritic.com"}
            ):
                raise URLError("La fuente redirigió a un destino no permitido.")
            if content_type not in IMAGE_TYPES:
                raise URLError("La fuente no devolvió una imagen.")
            content = upstream.read(MAX_IMAGE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("No se pudo cargar la imagen de %s: %s", videojuego_id, error)
        return imagen_sustitutiva_response(videojuego["titulo"])

    if len(content) > MAX_IMAGE_BYTES:
        logger.warning("La imagen de %s supera el tamaño permitido", videojuego_id)
        return imagen_sustitutiva_response(videojuego["titulo"])
    return Response(
        content,
        mimetype=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
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


if __name__ == "__main__":
    app.run(debug=False, port=5000)
