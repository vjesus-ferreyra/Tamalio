"""Pruebas de la clasificación y normalización de URL."""

import pytest

from tamalio.excepciones.error_plataforma_no_soportada import ErrorPlataformaNoSoportada
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.tipo_fuente import TipoFuente


@pytest.mark.parametrize(
    "url",
    [
        "https://music.youtube.com/watch?v=FB9u24ZpDek",
        "https://www.youtube.com/watch?v=FB9u24ZpDek",
        "https://youtu.be/FB9u24ZpDek",
        "youtu.be/FB9u24ZpDek",
        "https://m.youtube.com/watch?v=FB9u24ZpDek&feature=share",
        "https://www.youtube.com/shorts/FB9u24ZpDek",
    ],
)
def test_youtube_y_youtube_music_son_la_misma_pista(detector, url):
    fuente = detector.detectar(url)
    assert fuente.plataforma is Plataforma.YOUTUBE
    assert fuente.tipo is TipoFuente.PISTA
    assert fuente.identificador == "FB9u24ZpDek"
    assert fuente.url == "https://www.youtube.com/watch?v=FB9u24ZpDek"


def test_watch_con_lista_descarga_solo_la_pista(detector):
    fuente = detector.detectar("https://music.youtube.com/watch?v=FB9u24ZpDek&list=OLAK5uy_abc")
    assert fuente.tipo is TipoFuente.PISTA
    assert fuente.solo_pista


def test_album_de_youtube_music(detector):
    fuente = detector.detectar("https://music.youtube.com/playlist?list=OLAK5uy_mspJKZ25TV32cAhLcJi40QtsihifLQ_oM")
    assert fuente.tipo is TipoFuente.COLECCION
    assert fuente.url == "https://www.youtube.com/playlist?list=OLAK5uy_mspJKZ25TV32cAhLcJi40QtsihifLQ_oM"


def test_album_browse_de_youtube_music(detector):
    fuente = detector.detectar("https://music.youtube.com/browse/MPREb_abc123")
    assert fuente.tipo is TipoFuente.COLECCION
    assert fuente.identificador == "MPREb_abc123"


@pytest.mark.parametrize(
    ("url", "tipo"),
    [
        ("https://soundcloud.com/kadenza-hitti/john-kenza-nightmare", TipoFuente.PISTA),
        ("https://soundcloud.com/klaypex/sets/loosedirt", TipoFuente.COLECCION),
        ("https://soundcloud.com/klaypex", TipoFuente.COLECCION),
        ("https://soundcloud.com/klaypex/tracks", TipoFuente.COLECCION),
        ("https://on.soundcloud.com/AbC123", TipoFuente.DESCONOCIDO),
    ],
)
def test_soundcloud(detector, url, tipo):
    fuente = detector.detectar(url)
    assert fuente.plataforma is Plataforma.SOUNDCLOUD
    assert fuente.tipo is tipo


@pytest.mark.parametrize(
    ("url", "tipo"),
    [
        ("https://ghostdata.bandcamp.com/track/fluorite-fault", TipoFuente.PISTA),
        ("https://ghostdata.bandcamp.com/album/symphony-of-the-shepherdess", TipoFuente.COLECCION),
        ("https://ghostdata.bandcamp.com/", TipoFuente.COLECCION),
    ],
)
def test_bandcamp(detector, url, tipo):
    fuente = detector.detectar(url)
    assert fuente.plataforma is Plataforma.BANDCAMP
    assert fuente.tipo is tipo


def test_bandcamp_con_dominio_propio_requiere_plataforma_forzada(detector):
    with pytest.raises(ErrorPlataformaNoSoportada):
        detector.detectar("https://musica.artista.com/album/x")
    fuente = detector.detectar("https://musica.artista.com/album/x", plataforma=Plataforma.BANDCAMP)
    assert fuente.tipo is TipoFuente.DESCONOCIDO
    assert fuente.url == "https://musica.artista.com/album/x"


@pytest.mark.parametrize("url", ["https://vimeo.com/123", "https://www.youtube.com/watch?v=corto", "texto"])
def test_url_no_soportada(detector, url):
    with pytest.raises(ErrorPlataformaNoSoportada):
        detector.detectar(url)


def test_sinonimos_de_plataforma():
    assert Plataforma.desde_texto("YouTube Music") is Plataforma.YOUTUBE
    assert Plataforma.desde_texto("youtube_music") is Plataforma.YOUTUBE
    assert Plataforma.desde_texto("BC") is Plataforma.BANDCAMP
    with pytest.raises(ValueError):
        Plataforma.desde_texto("spotify")
