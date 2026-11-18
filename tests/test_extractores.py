"""
Pruebas de normalización de metadatos con las respuestas reales de yt-dlp.

Los fixtures de ``tests/fixtures`` son los JSON originales de cada plataforma
(reducidos: sin URL firmadas ni listas de formatos completas).
"""

from tamalio.extractores.fabrica_extractores import FabricaExtractores
from tamalio.modelos.plataforma import Plataforma

FABRICA = FabricaExtractores()


def normalizar(cargar_fixture, detector, nombre, plataforma, **metadatos):
    info = cargar_fixture(nombre)
    fuente = detector.detectar(info["webpage_url"], metadatos=metadatos)
    return FABRICA.obtener(plataforma).normalizar(info, fuente)


# ---------------------------------------------------------------------- #
# YouTube / YouTube Music
# ---------------------------------------------------------------------- #
def test_pista_youtube_topic(cargar_fixture, detector):
    (pista,) = normalizar(cargar_fixture, detector, "pista_youtube", Plataforma.YOUTUBE)
    assert pista.titulo == "Horn of Salvation"
    assert pista.artistas == ["ABOKAI"]  # Venía repetido tres veces.
    assert pista.album == "Horn of Salvation"
    assert pista.artistas_album == ["ABOKAI"]
    # release_year es 2839 (sacado de «℗ 2839655 Records»): se descarta y se usa release_date.
    assert pista.anio == 2026
    assert (pista.numero_pista, pista.total_pistas) == (1, 1)
    assert pista.url == "https://www.youtube.com/watch?v=FB9u24ZpDek"
    # La mejor miniatura tiene preference=0 (webp 1920×1080) y se recorta a cuadrado.
    assert pista.caratula.url.endswith("/maxresdefault.webp")
    assert pista.caratula.recortar_cuadrada


def test_album_youtube_usa_penultima_miniatura_como_caratula(cargar_fixture, detector):
    info = cargar_fixture("album_youtube")
    pistas = normalizar(cargar_fixture, detector, "album_youtube", Plataforma.YOUTUBE)
    esperada = info["thumbnails"][len(info["thumbnails"]) - 2]["url"]
    assert all(p.caratula.url == esperada for p in pistas)
    assert pistas[0].caratula.alternativas[0] == info["thumbnails"][-1]["url"]
    assert not pistas[0].caratula.recortar_cuadrada


def test_album_youtube_con_videos_oficiales(cargar_fixture, detector):
    pistas = normalizar(cargar_fixture, detector, "album_youtube", Plataforma.YOUTUBE)
    assert [p.numero_pista for p in pistas] == [1, 2, 3, 4]
    assert {p.album for p in pistas} == {"FIRESTARTER"}
    assert {p.total_pistas for p in pistas} == {4}
    assert all(p.artistas_album == ["K/DA"] for p in pistas)
    # Video oficial: se quita «K/DA - » y «(Official Music Video)»; los invitados pasan a artistas.
    primera = pistas[0]
    assert primera.titulo == "FIRESTARTER (feat. MIYEON and SOYEON of i-dle, Sophie Powers, Mimi Webb)"
    assert primera.artistas == ["K/DA", "MIYEON and SOYEON of i-dle", "Sophie Powers", "Mimi Webb"]
    assert pistas[1].titulo == "WATCH ME (feat. Sophie Powers, Mimi Webb)"
    # Las entradas 2 y 3 no traen fecha: heredan el año más frecuente del álbum.
    assert {p.anio for p in pistas} == {2026}
    # La pista «Topic» conserva sus artistas declarados.
    assert pistas[3].titulo == "GIRLS"
    assert pistas[3].artistas[0] == "K/DA"


def test_metadatos_manuales_ganan(cargar_fixture, detector):
    pistas = normalizar(cargar_fixture, detector, "album_youtube", Plataforma.YOUTUBE, generos=["K-Pop"], anio=2025)
    assert all(p.generos == ["K-Pop"] and p.anio == 2025 for p in pistas)


# ---------------------------------------------------------------------- #
# SoundCloud
# ---------------------------------------------------------------------- #
def test_pista_soundcloud(cargar_fixture, detector):
    (pista,) = normalizar(cargar_fixture, detector, "pista_soundcloud", Plataforma.SOUNDCLOUD)
    assert pista.titulo == "Nightmare"  # Sin «John Kenza - ».
    assert pista.artistas == ["John Kenza"]  # El que subió fue «Ryleo».
    assert pista.generos == ["Trance"]
    assert pista.anio == 2017
    assert pista.es_sencillo
    assert pista.caratula.url.endswith("-original.jpg")


def test_album_soundcloud(cargar_fixture, detector):
    pistas = normalizar(cargar_fixture, detector, "album_soundcloud", Plataforma.SOUNDCLOUD)
    assert len(pistas) == 7
    assert [p.numero_pista for p in pistas] == list(range(1, 8))
    assert pistas[0].titulo == "Lights"
    assert pistas[1].titulo == "Rain (feat. Sara Kay)"
    assert pistas[1].artistas == ["Klaypex", "Sara Kay"]
    assert {p.album for p in pistas} == {"Loose Dirt"}
    assert {p.anio for p in pistas} == {2011}
    # Todas comparten la carátula del set (no la de cada pista).
    assert len({p.caratula.url for p in pistas}) == 1
    assert "artworks-000011219468" in pistas[0].caratula.url


# ---------------------------------------------------------------------- #
# Bandcamp
# ---------------------------------------------------------------------- #
def test_pista_bandcamp(cargar_fixture, detector):
    (pista,) = normalizar(cargar_fixture, detector, "pista_bandcamp", Plataforma.BANDCAMP)
    assert pista.titulo == "Fluorite Fault"
    assert pista.es_sencillo
    assert pista.anio == 2025  # Sin release_year: se usa la fecha de subida.
    # «Houston» es la ubicación del artista, no un género.
    assert pista.generos == ["Aether Pop", "Electronic", "Progressive House", "Dreamsynth"]
    # _5.jpg (700 px) → _0.jpg (original) con respaldo _10 y la original recibida.
    assert pista.caratula.url == "https://f4.bcbits.com/img/a1074683926_0.jpg"
    assert pista.caratula.alternativas == (
        "https://f4.bcbits.com/img/a1074683926_10.jpg",
        "https://f4.bcbits.com/img/a1074683926_5.jpg",
    )


def test_album_bandcamp(cargar_fixture, detector):
    pistas = normalizar(cargar_fixture, detector, "album_bandcamp", Plataforma.BANDCAMP)
    assert len(pistas) == 15
    assert pistas[1].titulo == "Adagio For Souls (feat. COR!S & dreamiecloud)"
    assert pistas[1].artistas == ["GHOST DATA", "COR!S", "dreamiecloud"]
    assert all(p.artistas_album == ["GHOST DATA"] for p in pistas)
    assert {p.total_pistas for p in pistas} == {15}
    assert pistas[-1].numero_pista == 15
    assert {p.anio for p in pistas} == {2022}


def test_sin_agregar_invitados(cargar_fixture, detector):
    info = cargar_fixture("album_bandcamp")
    extractor = FabricaExtractores(agregar_invitados=False).obtener(Plataforma.BANDCAMP)
    pistas = extractor.normalizar(info, detector.detectar(info["webpage_url"]))
    assert pistas[1].artistas == ["GHOST DATA"]
