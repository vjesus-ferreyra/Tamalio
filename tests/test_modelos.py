"""Pruebas de entidades del modelo: tareas, pistas, formatos y rutas del sistema."""

from pathlib import Path

import pytest

from tamalio.configuracion.rutas_sistema import RutasSistema
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.tarea_descarga import TareaDescarga


def crear_tarea(detector) -> TareaDescarga:
    return TareaDescarga(fuente=detector.detectar("https://youtu.be/FB9u24ZpDek"), id=1)


def test_ciclo_de_vida_de_tarea(detector):
    tarea = crear_tarea(detector)
    tarea.iniciar()
    assert tarea.estado is EstadoDescarga.EN_PROCESO and tarea.intentos == 1
    tarea.pausar()
    tarea.reanudar()
    tarea.iniciar()
    tarea.fallar("sin red")
    assert tarea.ultimo_error == "sin red"
    tarea.reintentar()
    tarea.iniciar()
    tarea.completar()
    assert tarea.estado is EstadoDescarga.COMPLETADA and tarea.ultimo_error is None
    assert tarea.intentos == 3


def test_transicion_invalida(detector):
    tarea = crear_tarea(detector)
    with pytest.raises(ValueError, match="pendiente → completada"):
        tarea.completar()


def test_formatos():
    assert FormatoAudio.extension_para_codec("opus") == "opus"
    assert FormatoAudio.extension_para_codec("mp4a.40.2") == "m4a"
    assert FormatoAudio.extension_para_codec("mp3") == "mp3"
    assert FormatoAudio.extension_para_codec(None) == "mka"
    assert FormatoAudio.FLAC.es_sin_perdida and not FormatoAudio.MP3.es_sin_perdida
    with pytest.raises(ValueError):
        _ = FormatoAudio.ORIGINAL.extension


def test_pista_ida_y_vuelta_de_diccionario(tmp_path: Path):
    pista = Pista(
        plataforma=Plataforma.BANDCAMP,
        id_externo="1",
        url="https://a.bandcamp.com/track/x",
        titulo="X",
        album="Y",
        artistas=["A"],
        artistas_album=["A"],
        numero_pista=3,
        total_pistas=9,
        generos=["Rock"],
        anio=2020,
        ruta_archivo=tmp_path / "Bandcamp" / "A" / "x.flac",
    )
    datos = pista.a_diccionario(tmp_path)
    assert datos["ruta_relativa"] == "Bandcamp/A/x.flac"
    copia = Pista.desde_diccionario(datos, tmp_path)
    assert copia == pista


def test_metadatos_de_sencillo_a_album():
    pista = Pista(Plataforma.YOUTUBE, "x", "u", "T", "T", ["A"], ["A"], 1, 1, es_sencillo=True)
    pista.aplicar_metadatos({"album": "Disco", "numero_pista": 4})
    assert (pista.album, pista.numero_pista, pista.total_pistas, pista.es_sencillo) == ("Disco", 4, None, False)


@pytest.mark.parametrize(
    ("so", "esperada"),
    [("linux", "Música"), ("darwin", "Música"), ("win32", "Music")],
)
def test_carpeta_de_musica_por_sistema(so, esperada, tmp_path):
    rutas = RutasSistema(plataforma_so=so, hogar=tmp_path, entorno={})
    assert rutas.carpeta_musica() == tmp_path / esperada


def test_carpeta_config_windows_usa_appdata(tmp_path):
    rutas = RutasSistema(plataforma_so="win32", hogar=tmp_path, entorno={"APPDATA": str(tmp_path / "Roaming")})
    assert rutas.carpeta_config() == tmp_path / "Roaming" / "tamalio"
