import csv
import gzip
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


DATA_DIR = Path(__file__).resolve().parent / "data" / "videojuegos"
API_URL = (
    "https://en.wikipedia.org/w/api.php?action=parse"
    "&page=List_of_PlayStation_5_games&prop=text&format=json"
)
LIST_URL = "https://en.wikipedia.org/wiki/List_of_PlayStation_5_games"
VR2_API_URL = (
    "https://en.wikipedia.org/w/api.php?action=parse"
    "&page=List_of_PlayStation_VR2_games&prop=text&format=json"
)
VR2_LIST_URL = "https://en.wikipedia.org/wiki/List_of_PlayStation_VR2_games"
FIELDS = (
    "id",
    "titulo",
    "plataforma",
    "anio_salida",
    "fecha_salida",
    "desarrollador",
    "resumen",
    "estado",
    "fuente",
    "fuente_fecha",
    "verificado_el",
    "notas",
    "categoria",
    "imagen_url",
    "fuente_imagen",
    "puntuacion_3djuegos",
    "votos_3djuegos",
    "puntuacion_vandal",
    "puntuacion_metacritic_criticos",
    "puntuacion_metacritic_usuarios",
    "puntuacion_hobbyconsolas",
    "fuente_puntuacion_3djuegos",
    "fuente_puntuacion_vandal",
    "fuente_puntuacion_metacritic",
    "fuente_puntuacion_hobbyconsolas",
)
CURATED_ADDITIONS = [
    {
        "id": "arknights-endfield",
        "titulo": "Arknights: Endfield",
        "plataforma": "PS5",
        "anio_salida": "2026",
        "imagen_url": (
            "https://i.3djuegos.com/juegos/19439/arknights_endfield/"
            "fotos/ficha/arknights_endfield-5856097.jpg"
        ),
        "fuente_imagen": "https://www.3djuegos.com/juegos/arknights-endfield/",
        "puntuacion_3djuegos": "8.4",
        "votos_3djuegos": "15",
        "puntuacion_metacritic_criticos": "78",
        "puntuacion_metacritic_usuarios": "6.1",
        "fuente_puntuacion_3djuegos": "https://www.3djuegos.com/juegos/arknights-endfield/",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/arknights-endfield/",
    },
    {
        "id": "stray",
        "titulo": "Stray",
        "plataforma": "PS5",
        "anio_salida": "2022",
        "puntuacion_3djuegos": "8.6",
        "votos_3djuegos": "64",
        "puntuacion_metacritic_criticos": "83",
        "puntuacion_metacritic_usuarios": "8.2",
        "fuente_puntuacion_3djuegos": "https://www.3djuegos.com/juegos/stray/",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/stray/",
    },
    {
        "id": "returnal",
        "titulo": "Returnal",
        "plataforma": "PS5",
        "anio_salida": "2021",
        "puntuacion_metacritic_criticos": "86",
        "puntuacion_metacritic_usuarios": "7.4",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/returnal/",
    },
    {
        "id": "hogwarts-legacy",
        "titulo": "Hogwarts Legacy",
        "plataforma": "PS5",
        "anio_salida": "2023",
        "puntuacion_metacritic_criticos": "84",
        "puntuacion_metacritic_usuarios": "8.0",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/hogwarts-legacy/",
    },
    {
        "id": "resident-evil-4",
        "titulo": "Resident Evil 4",
        "plataforma": "PS5",
        "anio_salida": "2023",
        "puntuacion_metacritic_criticos": "93",
        "puntuacion_metacritic_usuarios": "9.0",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/resident-evil-4/",
    },
    {
        "id": "final-fantasy-xvi",
        "titulo": "Final Fantasy XVI",
        "plataforma": "PS5",
        "anio_salida": "2023",
        "puntuacion_metacritic_criticos": "87",
        "puntuacion_metacritic_usuarios": "8.3",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/final-fantasy-xvi/",
    },
    {
        "id": "monster-hunter-wilds",
        "titulo": "Monster Hunter Wilds",
        "plataforma": "PS5",
        "anio_salida": "2025",
        "imagen_url": (
            "https://i.3djuegos.com/juegos/19449/monster_hunter_wilds/"
            "fotos/ficha/monster_hunter_wilds-5856980.jpg"
        ),
        "fuente_imagen": "https://www.3djuegos.com/juegos/monster-hunter-wilds/",
        "puntuacion_3djuegos": "8.8",
        "votos_3djuegos": "22",
        "puntuacion_metacritic_criticos": "88",
        "puntuacion_metacritic_usuarios": "7.1",
        "fuente_puntuacion_3djuegos": "https://www.3djuegos.com/juegos/monster-hunter-wilds/",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/monster-hunter-wilds/",
    },
    {
        "id": "ghost-of-yotei",
        "titulo": "Ghost of Yōtei",
        "plataforma": "PS5",
        "anio_salida": "2025",
        "fecha_salida": "2025-10-02",
        "desarrollador": "Sucker Punch Productions",
        "resumen": (
            "Aventura de acción en el Japón rural del siglo XVII, protagonizada "
            "por Atsu en una historia de venganza y descubrimiento."
        ),
        "estado": "fecha_publicada",
        "fuente": "https://www.playstation.com/es-es/games/ghost-of-yotei/",
        "fuente_fecha": "https://www.playstation.com/es-es/games/ghost-of-yotei/",
        "verificado_el": "2026-10-24",
        "notas": "Ficha recuperada y verificada en PlayStation.",
        "categoria": "Acción y aventura",
        "imagen_url": (
            "https://i.3djuegos.com/juegos/20010/ghost_of_yotei/"
            "fotos/ficha/ghost_of_yotei-5923135.jpg"
        ),
        "fuente_imagen": "https://www.3djuegos.com/juegos/ghost-of-yotei/",
        "puntuacion_3djuegos": "8.7",
        "votos_3djuegos": "60",
        "puntuacion_metacritic_criticos": "86",
        "puntuacion_metacritic_usuarios": "8.0",
        "fuente_puntuacion_3djuegos": "https://www.3djuegos.com/juegos/ghost-of-yotei/",
        "fuente_puntuacion_metacritic": "https://www.metacritic.com/game/ghost-of-yotei/",
    }
]
DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
SORT_DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def slugify(value: str) -> str:
    return normalize(value).replace(" ", "-") or "juego-ps5"


class GameTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_game_table = False
        self.table_depth = 0
        self.current_row: list[dict[str, object]] | None = None
        self.current_cell: dict[str, object] | None = None
        self.ignored_depth = 0
        self.rows: list[list[dict[str, object]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "softwarelist":
            self.in_game_table = True
            self.table_depth = 1
            return
        if not self.in_game_table:
            return
        if self.current_cell is not None and tag in {"script", "style"}:
            self.ignored_depth += 1
            return
        if tag == "table":
            self.table_depth += 1
        elif tag == "tr" and self.table_depth == 1:
            self.current_row = []
        elif tag in {"th", "td"} and self.table_depth == 1:
            if self.current_row is not None:
                self.current_cell = {
                    "tag": tag,
                    "text": [],
                    "sort_values": [],
                    "href": "",
                }
        elif self.current_cell is not None:
            if tag == "span" and attributes.get("data-sort-value"):
                sort_values = self.current_cell["sort_values"]
                assert isinstance(sort_values, list)
                sort_values.append(attributes["data-sort-value"])
            elif tag == "a" and not self.current_cell["href"]:
                self.current_cell["href"] = attributes.get("href") or ""

    def handle_endtag(self, tag: str) -> None:
        if not self.in_game_table:
            return
        if self.ignored_depth and tag in {"script", "style"}:
            self.ignored_depth -= 1
            return
        if tag in {"th", "td"} and self.current_cell is not None:
            text_parts = self.current_cell["text"]
            assert isinstance(text_parts, list)
            self.current_cell["value"] = " ".join(" ".join(text_parts).split())
            if self.current_row is not None:
                self.current_row.append(self.current_cell)
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_game_table = False

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None and not self.ignored_depth:
            text_parts = self.current_cell["text"]
            assert isinstance(text_parts, list)
            text_parts.append(data)


def release_date(cell: dict[str, object]) -> tuple[str, str]:
    sort_values = cell["sort_values"]
    assert isinstance(sort_values, list)
    for sort_value in sort_values:
        match = SORT_DATE_PATTERN.search(str(sort_value))
        if match:
            year, month, day = map(int, match.groups())
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}", str(year)
            return "", str(year)

    value = str(cell.get("value", ""))
    match = DATE_PATTERN.search(value)
    if match:
        year, month, day = map(int, match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}", str(year)
        return "", str(year)
    year_match = re.search(r"\b(?:19|20|21)\d{2}\b", value)
    if year_match:
        return "", year_match.group()
    return "", ""


def records_from_html(
    markup: str,
    *,
    list_url: str = LIST_URL,
    platform: str = "PS5",
) -> list[dict[str, str]]:
    parser = GameTableParser()
    parser.feed(markup)
    records: list[dict[str, str]] = []
    identifiers: set[str] = set()

    for row in parser.rows:
        if len(row) < 7 or row[0]["tag"] != "th":
            continue
        title = str(row[0].get("value", "")).strip()
        if not title or title.casefold() == "title":
            continue

        dates = [release_date(row[index]) for index in (6, 5, 4) if index < len(row)]
        date, year = next(
            ((date, year) for date, year in dates if year),
            ("", ""),
        )
        game_id = slugify(title)
        if game_id in identifiers:
            suffix = hashlib.sha1(title.encode("utf-8")).hexdigest()[:7]
            game_id = f"{game_id}-{suffix}"
        identifiers.add(game_id)

        genres = str(row[1].get("value", "")).strip()
        developers = str(row[2].get("value", "")).strip()
        href = str(row[0].get("href", "")).strip()
        source = f"https://en.wikipedia.org{href}" if href.startswith("/wiki/") else list_url
        records.append(
            {
                "id": game_id,
                "titulo": title,
                "plataforma": platform,
                "anio_salida": year,
                "fecha_salida": date,
                "desarrollador": developers,
                "resumen": "",
                "estado": "fecha_listada" if year else "sin_fecha_confirmada",
                "fuente": source,
                "fuente_fecha": list_url,
                "verificado_el": "",
                "notas": "Fecha PAL/Europa; si falta, se usa NA y después Japón.",
                "categoria": genres,
                "imagen_url": "",
                "fuente_imagen": "",
            }
        )
    return records


def combine_source_records(
    ps5_records: list[dict[str, str]],
    vr2_records: list[dict[str, str]],
) -> list[dict[str, str]]:
    combined = {normalize(game["titulo"]): game for game in ps5_records}
    for game in vr2_records:
        key = normalize(game["titulo"])
        if key in combined:
            existing = combined[key]
            existing["plataforma"] = "PS5 · PS VR2"
            if "PS VR2" not in existing["notas"]:
                existing["notas"] += " También listado para PS VR2."
            for field in ("fecha_salida", "anio_salida", "desarrollador", "categoria"):
                if not existing[field] and game[field]:
                    existing[field] = game[field]
            continue
        game["notas"] += " Listado de juegos de PS VR2."
        combined[key] = game
    return list(combined.values())


def load_existing_records() -> dict[str, dict[str, str]]:
    existing: dict[str, dict[str, str]] = {}
    for path in DATA_DIR.glob("videojuegos_*"):
        if path.suffix not in {".csv", ".gz"}:
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                title_key = normalize(row.get("titulo", ""))
                if title_key:
                    existing[title_key] = row
    return existing


def merge_existing(
    source_records: list[dict[str, str]],
    existing_records: dict[str, dict[str, str]],
    verified_date: str,
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    consumed: set[str] = set()
    curated_by_title = {
        normalize(game["titulo"]): game for game in CURATED_ADDITIONS
    }
    for game in source_records:
        key = normalize(game["titulo"])
        old = existing_records.get(key, {})
        consumed.add(key)
        for field in FIELDS:
            previous = old.get(field, "")
            if field == "plataforma" and game[field] == "PS5 · PS VR2" and previous == "PS5":
                continue
            if field == "imagen_url" and previous.startswith(("/portadas/", "/imagenes/")):
                continue
            if previous:
                game[field] = previous
        for field, value in curated_by_title.get(key, {}).items():
            if value:
                game[field] = value
        game["verificado_el"] = verified_date
        for field, value in curated_by_title.get(key, {}).items():
            if value:
                game[field] = value
        game["verificado_el"] = verified_date
        merged.append(game)

    for key, old in existing_records.items():
        if key in consumed:
            continue
        game = {field: old.get(field, "") for field in FIELDS}
        if not game["id"] or not game["titulo"]:
            continue
        if "mw-parser-output" in game["titulo"] or len(game["titulo"]) > 120:
            continue
        if not game["anio_salida"] and game["fecha_salida"]:
            game["anio_salida"] = game["fecha_salida"][:4]
        if game["imagen_url"].startswith(("/portadas/", "/imagenes/")):
            game["imagen_url"] = ""
            game["fuente_imagen"] = ""
        merged.append(game)

    used_ids: set[str] = set()
    for game in merged:
        if game["id"] in used_ids:
            base_id = slugify(game["titulo"])
            suffix = hashlib.sha1(game["titulo"].encode("utf-8")).hexdigest()[:7]
            game["id"] = f"{base_id}-{suffix}"
            while game["id"] in used_ids:
                game["id"] = f"{game['id']}-1"
        if not game["imagen_url"]:
            game["imagen_url"] = f"/imagenes/{game['id']}"
        used_ids.add(game["id"])
    return merged


def write_archives(records: list[dict[str, str]]) -> None:
    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        year = record.get("anio_salida", "").strip()
        if not year:
            year = "sin_fecha"
        by_year[year].append(record)

    for year, games in by_year.items():
        games.sort(
            key=lambda game: (
                game.get("fecha_salida") or "9999-99-99",
                game["titulo"].casefold(),
            )
        )
        path = DATA_DIR / f"videojuegos_{year}.csv"
        if year.isdecimal() and int(year) <= 2025:
            with gzip.open(path.with_suffix(".csv.gz"), "wt", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(games)
            path.unlink(missing_ok=True)
        else:
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(games)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "PS5CalendarUniversityProject/1.0 (personal educational project)",
        "Accept": "application/json",
    }
    with urlopen(Request(API_URL, headers=headers), timeout=45) as response:
        ps5_payload = json.load(response)
    with urlopen(Request(VR2_API_URL, headers=headers), timeout=45) as response:
        vr2_payload = json.load(response)

    ps5_records = records_from_html(ps5_payload["parse"]["text"]["*"])
    vr2_records = records_from_html(
        vr2_payload["parse"]["text"]["*"],
        list_url=VR2_LIST_URL,
        platform="PS5 · PS VR2",
    )
    source_keys = {normalize(game["titulo"]) for game in ps5_records + vr2_records}
    ps5_records.extend(
        {field: addition.get(field, "") for field in FIELDS}
        for addition in CURATED_ADDITIONS
        if normalize(addition["titulo"]) not in source_keys
    )
    if len(ps5_records) < 1000 or len(vr2_records) < 400:
        raise RuntimeError(
            "Las fuentes devolvieron menos registros de los esperados; "
            "no se reemplazaron los CSV."
        )

    source_records = combine_source_records(ps5_records, vr2_records)
    existing = load_existing_records()
    records = merge_existing(
        source_records,
        existing,
        date.today().isoformat(),
    )
    write_archives(records)
    print(f"Registros de PS5: {len(ps5_records)}")
    print(f"Registros de PS VR2: {len(vr2_records)}")
    print(f"Títulos distintos en las fuentes: {len(source_records)}")
    print(f"Registros totales escritos: {len(records)}")
    print(f"Juegos Arknights: Endfield: {sum('arknights endfield' in normalize(g['titulo']) for g in records)}")


if __name__ == "__main__":
    main()
