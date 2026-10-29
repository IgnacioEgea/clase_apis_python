import csv
import io
import json
import os
import re
import unittest
from urllib.error import URLError
from unittest.mock import MagicMock, patch

try:
    from app import app
except ModuleNotFoundError:
    from ejercicios_api.api_videojuegos.app import app


class ApiVideojuegosTests(unittest.TestCase):
    def setUp(self):
        self.password_environment = patch.dict(
            os.environ, {"CLIENTES_PASSWORD": "test-password"}
        )
        self.password_environment.start()
        self.cliente = app.test_client()

    def tearDown(self):
        self.password_environment.stop()

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
        respuesta = self.cliente.get("/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.headers["Cache-Control"], "no-store")
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
        self.assertIn(b'value="2027" selected', respuesta.data)
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
        respuesta = self.cliente.get("/modo-oscuro")

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b'<body class="theme-gamer">', respuesta.data)
        self.assertIn(b"Modo oscuro", respuesta.data)
        self.assertIn(b'Dise\xc3\xb1o original', respuesta.data)
        self.assertNotIn(b"Modo gamer", respuesta.data)
        self.assertIn(b"b9ff38", respuesta.data)
        self.assertIn(b"position: sticky;", respuesta.data)
        self.assertIn(b"color: #f1f2ff;", respuesta.data)
        self.assertIn(b'aria-current="page">Modo oscuro</a>', respuesta.data)
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
                "anios": [2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027],
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
        self.assertTrue(respuesta.is_streamed)
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

    def test_catalogo_incluye_lanzamientos_de_ps_vr2(self):
        respuesta = self.cliente.get(
            "/api/videojuegos?anio=2023&q=Zenith+Nexus"
        )

        self.assertEqual(respuesta.status_code, 200)
        juegos = respuesta.get_json()
        self.assertEqual(len(juegos), 1)
        self.assertEqual(juegos[0]["id"], "zenith-nexus")
        self.assertEqual(juegos[0]["plataforma"], "PS5 · PS VR2")

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

    def test_juego_sin_foto_real_muestra_sustituto_identificado(self):
        respuesta = self.cliente.get("/imagenes/zenith-nexus")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "image/svg+xml")
        self.assertEqual(respuesta.headers["X-Image-Fallback"], "true")
        self.assertIn(b"Zenith: Nexus", respuesta.data)
        self.assertIn(b"IMAGEN ORIGINAL NO DISPONIBLE", respuesta.data)

    def test_todos_los_juegos_tienen_url_de_imagen(self):
        ids = []
        metacritic_scores = 0
        for anio in range(2020, 2028):
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
        self.assertGreaterEqual(len(ids) + len(sin_fecha), 1128)
        self.assertGreaterEqual(metacritic_scores, 480)
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


if __name__ == "__main__":
    unittest.main()
