"""Pruebas con FFmpeg real: conversión, etiquetado y procesamiento de carátulas."""

import base64
import subprocess

import mutagen
import pytest
from mutagen.flac import Picture

from tamalio.modelos.caratula import Caratula
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.conversor_audio import ConversorAudio
from tamalio.servicios.descargador_caratulas import DescargadorCaratulas
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg
from tamalio.servicios.etiquetador_audio import EtiquetadorAudio

pytestmark = pytest.mark.ffmpeg

PISTA = Pista(
    plataforma=Plataforma.BANDCAMP,
    id_externo="4125386728",
    url="https://ghostdata.bandcamp.com/track/beyond-eternity-feat-skye-light-2",
    titulo="Beyond Eternity (feat. Skye Light)",
    album="Symphony of the Shepherdess",
    artistas=["GHOST DATA", "Skye Light"],
    artistas_album=["GHOST DATA"],
    numero_pista=1,
    total_pistas=15,
    generos=["Aether Pop", "Electronic"],
    anio=2022,
)


@pytest.mark.parametrize(
    ("formato", "extension", "codec"),
    [
        (FormatoAudio.ORIGINAL, "opus", "opus"),
        (FormatoAudio.FLAC, "flac", "flac"),
        (FormatoAudio.ALAC, "m4a", "alac"),
        (FormatoAudio.MP3, "mp3", "mp3"),
        (FormatoAudio.AAC, "m4a", "aac"),
        (FormatoAudio.WAV, "wav", "pcm_s24le"),
        (FormatoAudio.VORBIS, "ogg", "vorbis"),
    ],
)
def test_conversion_y_etiquetado(generar_audio, imagen_jpeg, tmp_path, formato, extension, codec):
    # Simula lo que entrega YouTube: Opus dentro de WebM.
    origen = generar_audio("descarga.webm", ["-c:a", "libopus", "-b:a", "96k"])
    ffmpeg = EjecutorFfmpeg()
    avances = []
    salida = ConversorAudio(ffmpeg).convertir(
        origen, formato, tmp_path / "salida", duracion=1.5, al_progreso=lambda h, t: avances.append(h)
    )
    assert salida.suffix == f".{extension}"
    assert ffmpeg.codec_audio(salida) == codec

    EtiquetadorAudio().etiquetar(salida, PISTA, imagen_jpeg)
    audio = mutagen.File(salida, easy=False)
    texto = str(audio.tags)
    for esperado in ("Beyond Eternity", "Symphony of the Shepherdess", "GHOST DATA", "Skye Light", "2022"):
        assert esperado in texto
    # Carátula incrustada en todos los formatos.
    if extension == "flac":
        assert audio.pictures[0].data == imagen_jpeg
    elif extension in {"opus", "ogg"}:
        bloque = Picture(base64.b64decode(audio["metadata_block_picture"][0]))
        assert bloque.data == imagen_jpeg
    elif extension == "m4a":
        assert bytes(audio["covr"][0]) == imagen_jpeg
        assert audio["trkn"] == [(1, 15)]
    else:
        assert audio.tags.getall("APIC")[0].data == imagen_jpeg


def test_caratula_16_9_se_recorta_a_cuadrado(tmp_path, imagen_jpeg):
    class SesionFalsa:
        headers: dict = {}  # noqa: RUF012

        def get(self, url, timeout):
            class Respuesta:
                content = imagen_jpeg

                def raise_for_status(self):
                    pass

            return Respuesta()

    descargador = DescargadorCaratulas(tmp_path, EjecutorFfmpeg(), sesion=SesionFalsa())
    datos = descargador.obtener(Caratula("https://i.ytimg.com/vi/x/maxresdefault.jpg", recortar_cuadrada=True))
    salida = tmp_path / "c.jpg"
    salida.write_bytes(datos)
    dimensiones = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(salida)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert dimensiones == "720,720"
    # La segunda vez sale de la caché.
    assert descargador.obtener(Caratula("https://i.ytimg.com/vi/x/maxresdefault.jpg", recortar_cuadrada=True)) == datos


def test_perdida_de_calidad():
    assert ConversorAudio.pierde_calidad(FormatoAudio.MP3, "opus")
    assert not ConversorAudio.pierde_calidad(FormatoAudio.FLAC, "opus")
    assert not ConversorAudio.pierde_calidad(FormatoAudio.ORIGINAL, "opus")
    assert not ConversorAudio.pierde_calidad(FormatoAudio.MP3, "flac")
