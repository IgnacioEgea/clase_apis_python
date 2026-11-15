import csv
import gzip
import io
import json
import os
import re
import unittest
from urllib.error import URLError
from unittest.mock import MagicMock, patch

try:
    import app as modulo_app
except ModuleNotFoundError:
    from ejercicios_api.api_videojuegos import app as modulo_app

app = modulo_app.app


class ApiVideojuegosTests(unittest.TestCase):
    def setUp(self):
        self.password_environment = patch.dict(
            os.environ, {"CLIENTES_PASSWORD": "test-password"}
        )
        self.password_environment.start()
        modulo_app.CACHE_IMAGENES.clear()
        modulo_app.CACHE_PORTADAS.clear()
        self.cliente = app.test_client()

    def tearDown(self):
        self.password_environment.stop()

    def pagina_con_recursos(self, ruta):
        """Devuelve la página junto con su CSS y JS externos."""
        respuesta = self.cliente.get(ruta)
        recursos = re.findall(
            rb'(?:href|src)="(/static/[^"]+)"', respuesta.data
        )
        self.assertEqual(len(recursos), 2)
        contenido = respuesta.data
        for recurso in recursos:
            estatico = self.cliente.get(recurso.decode().replace("&amp;", "&"))
            self.assertEqual(estatico.status_code, 200)
            contenido += estatico.data
            estatico.close()
        return respuesta, contenido

    def iniciar_sesion_clientes(self, password="test-password"):
        pagina = self.cliente.get("/clientes")
        token = re.search(
            rb'name="csrf_token" value="([^"]+)"', pagina.data
        ).group(1).decode()
        return self.cliente.post(
            "/clientes/login",
            data={"csrf_token": token, "password": password},
        )

    def test_home_explains_calendar_and_api(self):
        pagina, contenido = self.pagina_con_recursos("/")
        respuesta = type("Pagina", (), {"data": contenido})

        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.headers["Cache-Control"], "no-store")
        self.assertIn(b"Calendario PS5", respuesta.data)
        self.assertIn(b"position: sticky;", respuesta.data)
        self.assertIn(b'<nav class="topbar-actions" aria-label="Navegaci\xc3\xb3n principal">', respuesta.data)
        self.assertIn(b'class="nav-link nav-link-primary"', respuesta.data)
        self.assertIn(b"color: #f5fbfa;", respuesta.data)
        self.assertIn(b"class=\"hero-explainer\"", respuesta.data)
        self.assertIn(b"Gu\xc3\xada interactiva", respuesta.data)
        self.assertIn(b'class="guide-step" open', respuesta.data)
        self.assertIn(b"Busca y filtra", respuesta.data)
        self.assertIn(b"Abre la ficha", respuesta.data)
        self.assertIn(b"Consulta los datos", respuesta.data)
        self.assertNotIn(b"class=\"topbar-note\"", respuesta.data)
        footer = respuesta.data.split(b"<footer>", 1)[1].split(b"</footer>", 1)[0]
        self.assertIn(b"Tarea universitaria \xc2\xb7 Sin fines lucrativos", footer)
        self.assertIn(
            b"\xc2\xa9 Ignacio Egea 2026 \xc2\xb7 Todos los derechos reservados.",
            footer,
        )
        self.assertIn(b"2026", respuesta.data)
        self.assertIn(b"2027", respuesta.data)
        self.assertIn(b"2021", respuesta.data)
        self.assertIn(b"categoryCache", respuesta.data)
        self.assertIn(b"game-detail", respuesta.data)
        anio_actual = str(modulo_app.date.today().year).encode()
        self.assertIn(b'value="' + anio_actual + b'" selected', respuesta.data)
        self.assertIn(b"Desarrollador", respuesta.data)
        self.assertIn(b"saveSelectedGame", respuesta.data)
        self.assertNotIn(b"function saveSearch", respuesta.data)
        self.assertIn(b"Nombre del juego", respuesta.data)
        self.assertIn(b"Filtros opcionales", respuesta.data)
        self.assertIn(b".game-list { display: flex; flex-direction: column", respuesta.data)
        self.assertIn(b"button.append(date, title)", respuesta.data)
        self.assertIn(b"repeat(3, minmax(0, 1fr))", respuesta.data)
        self.assertIn(b"Volver al inicio de la lista", respuesta.data)
        self.assertIn(b"renderRatings(game)", respuesta.data)
        self.assertIn(b"rating-donut", respuesta.data)
        self.assertIn(b"MEDIA / 10", respuesta.data)
        self.assertIn(b"rating-legend", respuesta.data)
        self.assertNotIn(b"rating-circle", respuesta.data)
        self.assertIn(b"Comparaci\xc3\xb3n de notas de prensa", respuesta.data)
        self.assertIn(b"/imagenes/${encodeURIComponent(game.id)}", respuesta.data)
        self.assertNotIn(b"/portadas/", respuesta.data)
        self.assertIn(b"puntuacion_metacritic_criticos", respuesta.data)
        self.assertIn(b"puntuacion_hobbyconsolas", respuesta.data)
        self.assertIn('categorySelect.addEventListener("change", () => form.requestSubmit())'.encode(), respuesta.data)
        self.assertIn('monthSelect.addEventListener("change", () => form.requestSubmit())'.encode(), respuesta.data)
        self.assertIn(b"data-year=", respuesta.data)
        self.assertIn(b"cover-dialog", respuesta.data)
        self.assertIn(b"coverDialog.showModal()", respuesta.data)
        self.assertNotIn(b"cover-unavailable", respuesta.data)
        self.assertIn(b"Sin fecha confirmada", respuesta.data)
        self.assertIn(b"localStorage.setItem", respuesta.data)
        self.assertIn(b"JSON bajo demanda", respuesta.data)
        self.assertIn(b"An\xc3\xa1lisis de clientes", respuesta.data)
        self.assertIn(b'id="favorite-toggle"', respuesta.data)
        self.assertIn(b'id="favorites-list"', respuesta.data)
        self.assertIn(b"videojuegos-api-favorites", respuesta.data)
        self.assertLess(
            respuesta.data.index(b'id="history-title"'),
            respuesta.data.index(b'id="favorites-title"'),
        )
        self.assertIn(b'class="footer-format"', respuesta.data)
        self.assertIn(b"Cambiar formato", respuesta.data)
        for formato in (b"automatico", b"movil", b"tablet", b"escritorio", b"portatil", b"panoramica"):
            self.assertIn(b'data-layout-format="' + formato + b'"', respuesta.data)
        self.assertIn(b"videojuegos-api-layout-format", respuesta.data)
        self.assertIn(b"text-align: center;", respuesta.data)
        self.assertIn(b"@media (max-width: 900px)", respuesta.data)
        self.assertIn(b"@media (max-width: 520px)", respuesta.data)

    def test_pagina_de_analisis_de_clientes_incluye_filtros_y_graficos(self):
        respuesta = self.cliente.get("/clientes")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.headers["Cache-Control"], "no-store")
        self.assertIn(b'name="password"', respuesta.data)
        self.assertNotIn(b'id="debt-chart"', respuesta.data)

        login = self.iniciar_sesion_clientes()
        self.assertEqual(login.status_code, 302)
        respuesta = self.cliente.get("/clientes")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.headers["Cache-Control"], "no-store")
        self.assertIn(b"Datos sint\xc3\xa9ticos", respuesta.data)
        self.assertIn(b'id="debt-chart"', respuesta.data)
        self.assertIn(b'id="health-chart"', respuesta.data)
        self.assertIn(b'fetch("/api/clientes"', respuesta.data)
        self.assertIn(b'id="type-filter"', respuesta.data)
        self.assertIn(b'href="#developer-data"', respuesta.data)
        self.assertIn(b'id="developer-data"', respuesta.data)
        self.assertIn(b'id="endpoint-url"', respuesta.data)
        self.assertIn(b'id="copy-endpoint"', respuesta.data)
        self.assertIn(b"https://tu-dominio/api/clientes", respuesta.data)
        self.assertIn(b"response.raise_for_status()", respuesta.data)
        self.assertIn(b"Cerrar sesi\xc3\xb3n", respuesta.data)

    def test_acceso_a_clientes_rechaza_contrasena_incorrecta(self):
        respuesta = self.iniciar_sesion_clientes(password="incorrecta")

        self.assertEqual(respuesta.status_code, 401)
        self.assertIn(b"Contrase\xc3\xb1a incorrecta", respuesta.data)

    def test_api_clientes_exige_sesion_y_cerrar_sesion_la_revoca(self):
        sin_sesion = self.cliente.get("/api/clientes")
        self.assertEqual(sin_sesion.status_code, 401)

        self.assertEqual(self.iniciar_sesion_clientes().status_code, 302)
        token = re.search(
            rb'name="csrf_token" value="([^"]+)"',
            self.cliente.get("/clientes").data,
        ).group(1).decode()
        logout = self.cliente.post("/clientes/logout", data={"csrf_token": token})

        self.assertEqual(logout.status_code, 302)
        respuesta = self.cliente.get("/api/clientes")
        self.assertEqual(respuesta.status_code, 401)

    @patch.dict("os.environ", {"API_CLIENTES_URL": "https://clientes.example/clientes"})
    @patch(f"{app.import_name}.urlopen")
    def test_api_clientes_reenvia_datos_del_servicio(self, mock_urlopen):
        cliente = {
            "id_cliente": "CLI-TEST-1",
            "informacion_personal": {"nombre": "Ada"},
        }
        upstream = MagicMock()
        upstream.headers.get_content_type.return_value = "application/json"
        upstream.read.return_value = json.dumps([cliente]).encode()
        mock_urlopen.return_value.__enter__.return_value = upstream

        self.assertEqual(self.iniciar_sesion_clientes().status_code, 302)
        respuesta = self.cliente.get("/api/clientes")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), [cliente])
        self.assertEqual(respuesta.headers["Cache-Control"], "no-store")
        mock_urlopen.assert_called_once()
        self.assertEqual(
            mock_urlopen.call_args.args[0].full_url,
            "https://clientes.example/clientes",
        )
        self.assertEqual(
            mock_urlopen.call_args.args[0].get_header("X-api-key"),
            "test-password",
        )

    @patch.dict("os.environ", {"API_CLIENTES_URL": "https://clientes.example/clientes"})
    @patch(f"{app.import_name}.urlopen")
    def test_api_clientes_informa_si_el_servicio_no_esta_disponible(
        self, mock_urlopen
    ):
        mock_urlopen.side_effect = URLError("connection failed")

        self.assertEqual(self.iniciar_sesion_clientes().status_code, 302)
        respuesta = self.cliente.get("/api/clientes")

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(
            respuesta.get_json(),
            {"error": "La API de clientes no está disponible."},
        )

    def test_pagina_modo_oscuro_reutiliza_catalogo_sin_cambiar_la_api(self):
        pagina, contenido = self.pagina_con_recursos("/modo-oscuro")
        respuesta = type("Pagina", (), {"data": contenido})

        self.assertEqual(pagina.status_code, 200)
        self.assertIn(b'<body class="theme-gamer">', respuesta.data)
        self.assertIn(b"Modo oscuro", respuesta.data)
        self.assertIn(b'Dise\xc3\xb1o original', respuesta.data)
        self.assertNotIn(b"Modo gamer", respuesta.data)
        self.assertIn(b"b9ff38", respuesta.data)
        self.assertIn(b"position: sticky;", respuesta.data)
        self.assertIn(b"color: #f1f2ff;", respuesta.data)
        self.assertIn(b'data-layout-format="movil">M\xc3\xb3vil</button>', respuesta.data)
        self.assertIn(b'id="favorites-list"', respuesta.data)
        self.assertIn(b'class="footer-format"', respuesta.data)
        self.assertIn(b'<nav class="topbar-actions" aria-label="Navegaci\xc3\xb3n principal">', respuesta.data)
        self.assertIn(b'id="search-form"', respuesta.data)
        self.assertIn(b'id="game-detail"', respuesta.data)

    def test_api_lists_available_year_archives(self):
        respuesta = self.cliente.get("/api/anios")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.get_json(),
            {
                "anios": [2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028],
                "incluye_sin_fecha": True,
            },
        )

    def test_rutas_usan_catalogo_cargado_al_iniciar(self):
        with patch(
            f"{app.import_name}.archivos_disponibles",
            side_effect=AssertionError("No debe redescubrir archivos por petición"),
        ), patch(
            f"{app.import_name}.leer_videojuegos",
            side_effect=AssertionError("No debe releer CSV por petición"),
        ):
            anios = self.cliente.get("/api/anios")
            listado = self.cliente.get("/api/videojuegos?anio=2026")
            ficha = self.cliente.get("/api/videojuegos/stray")

        self.assertEqual(anios.status_code, 200)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(ficha.status_code, 200)

    def test_listado_anual_genera_json_desde_csv(self):
        respuesta = self.cliente.get("/api/videojuegos?anio=2026")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "application/json")
        juegos = respuesta.get_json()
        self.assertGreater(len(juegos), 50)
        phantom = next(juego for juego in juegos if juego["id"] == "phantom-blade-zero")
        self.assertEqual(phantom["titulo"], "Phantom Blade Zero")
        self.assertEqual(phantom["fecha_salida"], "2026-10-29")
        self.assertIn(juegos[0]["plataforma"], {"PS5", "PS5 · PS VR2"})
        self.assertTrue(juegos[0]["fuente"].startswith("https://"))
        gta = next(juego for juego in juegos if juego["id"] == "grand-theft-auto-vi")
        self.assertEqual(gta["estado"], "fuentes_discrepan")
        self.assertIn("26/05/2026", gta["notas"])

    def test_busqueda_ignora_mayusculas_y_tildes(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2026&q=PHANTOM+BLADE"
        )

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertEqual(len(juegos), 1)
        self.assertEqual(juegos[0]["id"], "phantom-blade-zero")

    def test_busqueda_sin_coincidencias_devuelve_lista_vacia(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2026&q=no-existe"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), [])

    def test_archivo_comprimido_2021_se_lee_y_se_filtra(self):
        respuesta = self.cliente.get("/api/videojuegos?anio=2021")

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertGreater(len(juegos), 200)
        self.assertIn("returnal", [juego["id"] for juego in juegos])

    def test_catalogo_historico_2025_y_busqueda_con_errata(self):
        respuesta = self.cliente.get("/api/videojuegos?anio=2022&q=Stry")

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertEqual([juego["id"] for juego in juegos], ["stray"])

    def test_busqueda_encuentra_arknights_endfield_en_2026_con_errata(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2026&q=aknights+endfield"
        )

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertEqual(len(juegos), 1)
        self.assertEqual(juegos[0]["id"], "arknights-endfield")
        self.assertEqual(juegos[0]["fecha_salida"], "2026-01-22")

    def test_catalogo_no_incluye_juegos_de_realidad_virtual(self):
        for anio in ["2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "sin-fecha"]:
            with self.subTest(anio=anio):
                juegos = self.cliente.get(f"/api/videojuegos?anio={anio}").get_json()
                self.assertTrue(all(juego["plataforma"] == "PS5" for juego in juegos))
                self.assertFalse(
                    any("VR" in juego["notas"] for juego in juegos)
                )
        self.assertEqual(self.cliente.get("/api/videojuegos/zenith-nexus").status_code, 404)
        # Los juegos normales con modo VR opcional se conservan como PS5.
        gt7 = self.cliente.get("/api/videojuegos/gran-turismo-7").get_json()
        self.assertEqual(gt7["plataforma"], "PS5")

    def test_catalogo_incluye_titulos_conocidos_que_faltaban(self):
        for anio, titulo in [
            ("2026", "Hades II"),
            ("2024", "Star Wars Outlaws"),
            ("2024", "Prince of Persia: The Lost Crown"),
            ("2023", "Sea of Stars"),
            ("2022", "Tunic"),
            ("2024", "Neva"),
            ("2022", "Outer Wilds"),
            ("2024", "Marvel Rivals"),
        ]:
            with self.subTest(titulo=titulo):
                juegos = self.cliente.get(
                    f"/api/videojuegos?anio={anio}&q={titulo}"
                ).get_json()
                self.assertIn(titulo, [juego["titulo"] for juego in juegos])

    def test_busqueda_aproximada_y_filtros_se_combinan(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2025&q=monster+huntr&categoria=accion&mes=02"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            [juego["id"] for juego in respuesta.get_json()],
            ["monster-hunter-wilds"],
        )

    def test_busqueda_de_titulo_no_encuentra_palabras_del_resumen(self):
        respuesta = self.cliente.get("/api/videojuegos?anio=2025&q=caza")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), [])

    def test_categoria_no_depende_de_mayusculas_ni_tildes(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2022&categoria=aventura"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            [juego["id"] for juego in respuesta.get_json()],
            ["horizon-forbidden-west", "stray"],
        )

    def test_todos_los_anios_historicos_tienen_categoria_y_fecha(self):
        for anio in range(2021, 2026):
            with self.subTest(anio=anio):
                respuesta = self.cliente.get(f"/api/videojuegos?anio={anio}")
                self.assertEqual(respuesta.status_code, 200)
                juegos = respuesta.get_json()
                self.assertTrue(juegos)
                self.assertTrue(all(juego["categoria"] for juego in juegos))
                self.assertTrue(all(juego["anio_salida"] == str(anio) for juego in juegos))

    def test_filtros_por_categoria_y_mes(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2022&categoria=Aventura&mes=07"
        )

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertEqual([juego["id"] for juego in juegos], ["stray"])

    def test_mes_invalido_devuelve_error_claro(self):
        respuesta = self.cliente.get("/api/videojuegos?anio=2022&mes=13")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("mes", respuesta.get_json()["error"])

    def test_ficha_incluye_categoria_y_portada_opcional(self):
        respuesta = self.cliente.get("/api/videojuegos/stray")

        self.assertEqual(respuesta.status_code, 200)
        juego = respuesta.get_json()
        self.assertEqual(juego["categoria"], "Aventura")
        self.assertTrue(juego["imagen_url"].startswith("https://"))
        self.assertTrue(juego["fuente_imagen"].startswith("https://"))
        self.assertEqual(juego["puntuacion_3djuegos"], "8.6")
        self.assertEqual(juego["votos_3djuegos"], "64")
        self.assertEqual(juego["puntuacion_metacritic_criticos"], "83")
        self.assertEqual(juego["puntuacion_metacritic_usuarios"], "8.2")

    def test_juegos_populares_incluyen_notas_metacritic_verificadas(self):
        expected = {
            "returnal": ("86", "7.4"),
            "hogwarts-legacy": ("84", "8.0"),
            "resident-evil-4": ("93", "9.0"),
            "final-fantasy-xvi": ("87", "8.3"),
        }
        for game_id, (critics, users) in expected.items():
            with self.subTest(game_id=game_id):
                respuesta = self.cliente.get(f"/api/videojuegos/{game_id}")
                self.assertEqual(respuesta.status_code, 200)
                juego = respuesta.get_json()
                self.assertEqual(juego["puntuacion_metacritic_criticos"], critics)
                self.assertEqual(juego["puntuacion_metacritic_usuarios"], users)
                self.assertTrue(juego["fuente_puntuacion_metacritic"].startswith("https://"))

    def test_ficha_ghost_of_yotei_conserva_arte_y_notas_verificadas(self):
        respuesta = self.cliente.get("/api/videojuegos/ghost-of-yotei")

        self.assertEqual(respuesta.status_code, 200)
        juego = respuesta.get_json()
        self.assertEqual(juego["titulo"], "Ghost of Yōtei")
        self.assertEqual(juego["fecha_salida"], "2025-10-02")
        self.assertTrue(juego["imagen_url"].endswith("ghost_of_yotei-5923135.jpg"))
        self.assertEqual(juego["puntuacion_3djuegos"], "8.7")
        self.assertEqual(juego["votos_3djuegos"], "60")
        self.assertEqual(juego["puntuacion_metacritic_criticos"], "86")
        self.assertEqual(juego["puntuacion_metacritic_usuarios"], "8.0")

    def test_monster_hunter_wilds_incluye_imagen_real_y_notas_verificadas(self):
        respuesta = self.cliente.get("/api/videojuegos/monster-hunter-wilds")

        self.assertEqual(respuesta.status_code, 200)
        juego = respuesta.get_json()
        self.assertTrue(juego["imagen_url"].endswith("monster_hunter_wilds-5856980.jpg"))
        self.assertEqual(juego["puntuacion_3djuegos"], "8.8")
        self.assertEqual(juego["votos_3djuegos"], "22")
        self.assertEqual(juego["puntuacion_metacritic_criticos"], "88")
        self.assertEqual(juego["puntuacion_metacritic_usuarios"], "7.1")

    def test_imagen_se_sirve_desde_la_api_como_jpeg(self):
        upstream = MagicMock()
        upstream.headers.get_content_type.return_value = "image/jpeg"
        upstream.geturl.return_value = (
            "https://i.3djuegos.com/juegos/17375/stray__2021_/"
            "fotos/ficha/stray__2021_-5712395.jpg"
        )
        upstream.read.return_value = b"jpeg-image"
        response_context = MagicMock()
        response_context.__enter__.return_value = upstream
        with patch(
            f"{app.import_name}.urlopen",
            return_value=response_context,
        ):
            respuesta = self.cliente.get("/imagenes/stray")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "image/jpeg")
        self.assertEqual(respuesta.data, b"jpeg-image")
        self.assertEqual(respuesta.headers["Cache-Control"], "public, max-age=86400")

    def test_imagen_metacritic_se_sirve_desde_la_api(self):
        game = self.cliente.get("/api/videojuegos/one-piece-odyssey").get_json()
        self.assertIn("www.metacritic.com/a/img/", game["imagen_url"])

        upstream = MagicMock()
        upstream.headers.get_content_type.return_value = "image/jpeg"
        upstream.geturl.return_value = (
            "https://www.metacritic.com/a/img/catalog/provider/"
            "6/3/6-1-916442-13.jpg"
        )
        upstream.read.return_value = b"metacritic-image"
        response_context = MagicMock()
        response_context.__enter__.return_value = upstream
        with patch(
            f"{app.import_name}.urlopen",
            return_value=response_context,
        ) as fetch:
            respuesta = self.cliente.get("/imagenes/one-piece-odyssey")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, b"metacritic-image")
        self.assertEqual(
            fetch.call_args.args[0].full_url,
            "https://www.metacritic.com/a/img/catalog/provider/6/3/6-1-916442-13.jpg",
        )

    def test_url_metacritic_usa_imagen_original_en_alta_resolucion(self):
        response_context = MagicMock()
        upstream = response_context.__enter__.return_value
        upstream.headers.get_content_type.return_value = "image/jpeg"
        upstream.geturl.return_value = (
            "https://www.metacritic.com/a/img/catalog/provider/6/3/"
            "6-1-916442-13.jpg"
        )
        upstream.read.return_value = b"high-resolution-image"
        original_url = (
            "https://www.metacritic.com/a/img/resize/"
            "62f081c77916ef9a534b908baf7f36971de0005d/catalog/provider/"
            "6/3/6-1-916442-13.jpg?auto=webp&fit=cover&height=144&"
            "quality=70&width=96"
        )
        with patch(
            f"{app.import_name}.buscar_videojuego",
            return_value={
                "id": "high-res-test",
                "titulo": "High Resolution Test",
                "imagen_url": original_url,
            },
        ), patch(
            f"{app.import_name}.urlopen",
            return_value=response_context,
        ) as fetch:
            response = self.cliente.get("/imagenes/high-res-test")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"high-resolution-image")
        self.assertEqual(
            fetch.call_args.args[0].full_url,
            "https://www.metacritic.com/a/img/catalog/provider/6/3/6-1-916442-13.jpg",
        )

    def test_arknights_endfield_muestra_imagen_real_y_notas_de_prensa(self):
        respuesta = self.cliente.get("/api/videojuegos/arknights-endfield")

        self.assertEqual(respuesta.status_code, 200)
        juego = respuesta.get_json()
        self.assertTrue(juego["imagen_url"].endswith("arknights_endfield-5856097.jpg"))
        self.assertEqual(juego["puntuacion_3djuegos"], "8.4")
        self.assertEqual(juego["votos_3djuegos"], "15")
        self.assertEqual(juego["puntuacion_metacritic_criticos"], "78")
        self.assertEqual(juego["puntuacion_metacritic_usuarios"], "6.1")

    def respuesta_imagen(self, contenido=b"portada", tipo="image/jpeg", url_final=None):
        contexto = MagicMock()
        upstream = contexto.__enter__.return_value
        upstream.headers.get_content_type.return_value = tipo
        upstream.read.return_value = contenido
        upstream.geturl.return_value = url_final
        return contexto, upstream

    def test_juego_sin_foto_real_muestra_sustituto_si_no_hay_portada(self):
        with patch(
            f"{app.import_name}.leer_json_externo",
            side_effect=URLError("sin conexión"),
        ):
            respuesta = self.cliente.get("/imagenes/sea-of-stars")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "image/svg+xml")
        self.assertEqual(respuesta.headers["X-Image-Fallback"], "true")
        self.assertIn(b"Sea of Stars", respuesta.data)
        self.assertIn(b"IMAGEN ORIGINAL NO DISPONIBLE", respuesta.data)

    def test_portada_se_obtiene_de_wikipedia(self):
        wikipedia = {
            "query": {"pages": [{
                "title": "Sea of Stars",
                "thumbnail": {
                    "source": "https://upload.wikimedia.org/wikipedia/en/thumb/a/ab/Sea_of_Stars.jpg/600px-Sea_of_Stars.jpg?utm_source=x"
                },
            }]}
        }
        url = "https://upload.wikimedia.org/wikipedia/en/thumb/a/ab/Sea_of_Stars.jpg/600px-Sea_of_Stars.jpg"
        contexto, _ = self.respuesta_imagen(b"wiki", url_final=url)
        with patch(
            f"{app.import_name}.leer_json_externo", return_value=wikipedia
        ) as buscar, patch(
            f"{app.import_name}.urlopen", return_value=contexto
        ) as descargar:
            primera = self.cliente.get("/imagenes/sea-of-stars")
            segunda = self.cliente.get("/imagenes/sea-of-stars")

        self.assertEqual(primera.data, b"wiki")
        self.assertEqual(segunda.data, b"wiki")
        self.assertIn("pilicense=any", buscar.call_args.args[0])
        self.assertIn("titles=Sea+of+Stars", buscar.call_args.args[0])
        self.assertEqual(descargar.call_args.args[0].full_url, url)
        # La segunda petición sale de la caché: ni búsqueda ni descarga nuevas.
        self.assertEqual(buscar.call_count, 1)
        self.assertEqual(descargar.call_count, 1)

    def test_portada_de_steam_si_no_hay_articulo(self):
        juego = {
            "id": "juego-indie",
            "titulo": "Juego Indie™",
            "fuente": "https://en.wikipedia.org/wiki/List_of_PlayStation_5_games",
            "imagen_url": "/imagenes/juego-indie",
        }
        steam = {"items": [
            {"id": 1, "name": "Juego Indie 2", "tiny_image": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1/capsule_231x87.jpg"},
            {"id": 790850, "name": "Juego Indie", "tiny_image": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/790850/capsule_231x87.jpg?t=1"},
        ]}
        url = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/790850/library_600x900.jpg"
        contexto, _ = self.respuesta_imagen(b"steam", url_final=url)
        with patch(f"{app.import_name}.buscar_videojuego", return_value=juego), patch(
            f"{app.import_name}.leer_json_externo", return_value=steam
        ) as buscar, patch(f"{app.import_name}.urlopen", return_value=contexto) as descargar:
            respuesta = self.cliente.get("/imagenes/juego-indie")

        self.assertEqual(respuesta.data, b"steam")
        self.assertIn("store.steampowered.com", buscar.call_args.args[0])
        self.assertEqual(descargar.call_args.args[0].full_url, url)

    def test_portada_rechaza_hosts_no_permitidos(self):
        wikipedia = {"query": {"pages": [{"thumbnail": {"source": "https://evil.example/x.jpg"}}]}}
        with patch(
            f"{app.import_name}.leer_json_externo",
            side_effect=[wikipedia, {"items": []}],
        ), patch(f"{app.import_name}.urlopen") as descargar:
            respuesta = self.cliente.get("/imagenes/sea-of-stars")

        self.assertEqual(respuesta.headers["X-Image-Fallback"], "true")
        descargar.assert_not_called()

    def test_todos_los_juegos_tienen_url_de_imagen(self):
        ids = []
        metacritic_scores = 0
        for anio in range(2020, 2029):
            catalogo = self.cliente.get(
                f"/api/videojuegos?anio={anio}"
            ).get_json()
            ids.extend(juego["id"] for juego in catalogo)
            for juego in catalogo:
                if juego["puntuacion_metacritic_criticos"]:
                    metacritic_scores += 1
                    self.assertTrue(
                        juego["fuente_puntuacion_metacritic"].startswith("https://")
                    )
            self.assertTrue(
                all(
                    juego["imagen_url"].startswith(("https://", "/imagenes/"))
                    for juego in catalogo
                )
            )
            self.assertTrue(
                all(
                    not juego["fuente_imagen"]
                    or juego["fuente_imagen"].startswith("https://")
                    for juego in catalogo
                )
            )
        sin_fecha = self.cliente.get(
            "/api/videojuegos?anio=sin-fecha"
        ).get_json()
        self.assertTrue(
            all(
                juego["imagen_url"].startswith(("https://", "/imagenes/"))
                for juego in sin_fecha
            )
        )
        self.assertTrue(
            all(
                not juego["fuente_imagen"]
                or juego["fuente_imagen"].startswith("https://")
                for juego in sin_fecha
            )
        )
        self.assertGreaterEqual(len(ids) + len(sin_fecha), 1600)
        self.assertGreaterEqual(metacritic_scores, 440)
        all_ids = ids + [juego["id"] for juego in sin_fecha]
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_2027_contiene_lanzamientos_publicados_por_fuentes(self):
        respuesta = self.cliente.get("/api/videojuegos?anio=2027")

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        stranger = next(juego for juego in juegos if juego["titulo"] == "Stranger Than Heaven")
        self.assertEqual(stranger["fecha_salida"], "2027-01-15")

    def test_juegos_sin_fecha_tienen_archivo_separado(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=sin-fecha"
        )

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertGreaterEqual(len(juegos), 2)
        intergalactic = next(
            juego
            for juego in juegos
            if juego["id"] == "intergalactic-the-heretic-prophet"
        )
        self.assertEqual(intergalactic["estado"], "sin_fecha_confirmada")
        self.assertEqual(intergalactic["fecha_salida"], "")

    def test_requiere_anio_y_rechaza_archivo_inexistente(self):
        sin_anio = self.cliente.get("/api/videojuegos")
        anio_inexistente = self.cliente.get("/api/videojuegos?anio=2019")

        self.assertEqual(sin_anio.status_code, 400)
        self.assertIn("error", sin_anio.get_json())
        self.assertEqual(anio_inexistente.status_code, 404)

    def test_busqueda_por_id_y_juego_inexistente(self):
        encontrado = self.cliente.get(
            "/api/videojuegos/phantom-blade-zero"
        )
        inexistente = self.cliente.get("/api/videojuegos/no-existe")

        self.assertEqual(encontrado.status_code, 200)
        self.assertEqual(
            encontrado.get_json()["desarrollador"], "S-Game"
        )
        self.assertEqual(inexistente.status_code, 404)

    def test_descarga_csv_por_anio(self):
        respuesta = self.cliente.get("/videojuegos.csv?anio=2026")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "text/csv")
        filas = list(
            csv.DictReader(io.StringIO(respuesta.get_data(as_text=True)))
        )
        self.assertGreater(len(filas), 50)
        phantom = next(fila for fila in filas if fila["id"] == "phantom-blade-zero")
        self.assertEqual(phantom["titulo"], "Phantom Blade Zero")
        self.assertIn("fuente", phantom)
        self.assertIn("fuente_fecha", phantom)
        respuesta.close()

    def test_descarga_historica_conserva_archivo_comprimido(self):
        respuesta = self.cliente.get("/videojuegos.csv?anio=2021")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "application/gzip")
        self.assertIn("2021.csv.gz", respuesta.headers["Content-Disposition"])
        respuesta.close()

    def test_recursos_estaticos_versionados_se_cachean_un_anio(self):
        pagina = self.cliente.get("/")
        css = re.search(rb'href="(/static/css/app\.css\?v=[0-9a-f]+)"', pagina.data)
        self.assertIsNotNone(css)
        respuesta = self.cliente.get(css.group(1).decode())

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("immutable", respuesta.headers["Cache-Control"])
        respuesta.close()

    def test_categorias_por_anio_sin_descargar_catalogo(self):
        respuesta = self.cliente.get("/api/categorias?anio=2026")

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.get_json()
        catalogo = self.cliente.get("/api/videojuegos?anio=2026").get_json()
        normalizar = modulo_app.normalizar_categoria
        esperadas = {
            normalizar(juego["categoria"]) for juego in catalogo if juego["categoria"]
        }
        self.assertEqual({normalizar(c) for c in datos["categorias"]}, esperadas)
        self.assertEqual(len(datos["categorias"]), len(esperadas))

    def test_categorias_no_repiten_variantes_de_mayusculas(self):
        categorias = self.cliente.get("/api/categorias?anio=2024").get_json()[
            "categorias"
        ]
        normalizadas = [modulo_app.normalizar_categoria(c) for c in categorias]

        self.assertEqual(len(normalizadas), len(set(normalizadas)))
        self.assertEqual(
            sum(c in {"Action-Adventure", "Action-adventure"} for c in categorias), 1
        )
        self.assertEqual(
            self.cliente.get("/api/categorias?anio=1990").status_code, 404
        )
        self.assertEqual(
            self.cliente.get("/api/categorias?anio=sin-fecha").status_code, 200
        )

    def test_listado_usa_etag_y_responde_304(self):
        primera = self.cliente.get("/api/videojuegos?anio=2026")
        etag = primera.headers["ETag"]

        segunda = self.cliente.get(
            "/api/videojuegos?anio=2026", headers={"If-None-Match": etag}
        )

        self.assertEqual(segunda.status_code, 304)
        self.assertEqual(segunda.data, b"")

    def test_json_se_comprime_con_gzip_si_el_navegador_lo_acepta(self):
        normal = self.cliente.get("/api/videojuegos?anio=2026")
        comprimida = self.cliente.get(
            "/api/videojuegos?anio=2026", headers={"Accept-Encoding": "gzip"}
        )

        self.assertEqual(comprimida.headers["Content-Encoding"], "gzip")
        self.assertIn("Accept-Encoding", comprimida.headers["Vary"])
        self.assertLess(len(comprimida.data), len(normal.data) / 3)
        self.assertEqual(gzip.decompress(comprimida.data), normal.data)

    def test_imagen_se_descarga_una_vez_y_despues_sale_de_cache(self):
        upstream = MagicMock()
        upstream.headers.get_content_type.return_value = "image/jpeg"
        upstream.geturl.return_value = (
            "https://i.3djuegos.com/juegos/17375/stray__2021_/"
            "fotos/ficha/stray__2021_-5712395.jpg"
        )
        upstream.read.return_value = b"jpeg-image"
        response_context = MagicMock()
        response_context.__enter__.return_value = upstream
        with patch(
            f"{app.import_name}.urlopen", return_value=response_context
        ) as fetch:
            primera = self.cliente.get("/imagenes/stray")
            segunda = self.cliente.get("/imagenes/stray")

        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(primera.data, segunda.data)

    def test_busqueda_filtrada_coincide_con_filtrado_manual(self):
        catalogo = self.cliente.get("/api/videojuegos?anio=2023").get_json()
        categoria = catalogo[0]["categoria"]
        respuesta = self.cliente.get(
            f"/api/videojuegos?anio=2023&categoria={categoria}"
        ).get_json()

        self.assertEqual(
            [juego["id"] for juego in respuesta],
            [
                juego["id"]
                for juego in catalogo
                if modulo_app.normalizar_categoria(juego["categoria"])
                == modulo_app.normalizar_categoria(categoria)
            ],
        )


if __name__ == "__main__":
    unittest.main()
