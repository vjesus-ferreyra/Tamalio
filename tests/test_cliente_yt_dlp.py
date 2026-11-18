"""Pruebas de la configuración de yt-dlp y del manejo del desafío «Client Challenge»."""

import random

from tamalio.configuracion.configuracion import Configuracion
from tamalio.excepciones.error_deteccion_bot import ErrorDeteccionBot
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.cliente_yt_dlp import ClienteYtDlp
from tamalio.servicios.temporizador_humano import TemporizadorHumano

DESAFIO = (
    "ERROR: [Bandcamp] fluorite-fault: Got client challenge webpage response with chrome-152:windows-10; "
    "please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate "
    "issue template. Confirm you are on the latest version using  yt-dlp -U"
)


def cliente(tmp_path, suplantar: str) -> ClienteYtDlp:
    config = Configuracion(red_suplantar_navegador=suplantar, carpeta_cache=tmp_path)
    return ClienteYtDlp(config, tmp_path / "trabajo", TemporizadorHumano(azar=random.Random(1)))


def test_auto_no_fuerza_la_suplantacion(tmp_path):
    assert "impersonate" not in cliente(tmp_path, "auto").opciones()
    assert "impersonate" not in cliente(tmp_path, "").opciones()
    assert "impersonate" in cliente(tmp_path, "chrome").opciones()


def test_desafio_se_traduce_a_bloqueo_sin_coletilla(tmp_path):
    error = cliente(tmp_path, "auto")._traducir(Exception(DESAFIO), Plataforma.BANDCAMP)
    assert isinstance(error, ErrorDeteccionBot)
    assert "please report" not in error.mensaje
    assert error.mensaje.endswith("chrome-152:windows-10")


def test_desafio_con_suplantacion_forzada_reintenta_sin_ella(tmp_path, detector):
    instancia = cliente(tmp_path, "chrome")
    llamadas = []

    def extraer_con(opciones, fuente):
        llamadas.append("impersonate" in opciones)
        if "impersonate" in opciones:
            raise instancia._traducir(Exception(DESAFIO), Plataforma.BANDCAMP)
        return {"id": "968977920", "title": "Fluorite Fault"}

    instancia._extraer_con = extraer_con
    info = instancia.extraer(detector.detectar("https://ghostdata.bandcamp.com/track/fluorite-fault"))
    assert info["title"] == "Fluorite Fault"
    assert llamadas == [True, False]
