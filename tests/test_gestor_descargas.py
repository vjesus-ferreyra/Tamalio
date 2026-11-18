"""Pruebas del flujo completo de descarga con un cliente de yt-dlp simulado."""

import random
import shutil

import pytest

from dobles.observador_registrador import ObservadorRegistrador
from dobles.repositorio_catalogo_memoria import RepositorioCatalogoMemoria
from dobles.repositorio_sesiones_memoria import RepositorioSesionesMemoria
from dobles.repositorio_tareas_memoria import RepositorioTareasMemoria
from tamalio.configuracion.configuracion import Configuracion
from tamalio.excepciones.error_deteccion_bot import ErrorDeteccionBot
from tamalio.extractores.fabrica_extractores import FabricaExtractores
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.fase_proceso import FaseProceso
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.progreso_descarga import ProgresoDescarga
from tamalio.servicios.control_ejecucion import ControlEjecucion
from tamalio.servicios.conversor_audio import ConversorAudio
from tamalio.servicios.descargador_caratulas import DescargadorCaratulas
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg
from tamalio.servicios.etiquetador_audio import EtiquetadorAudio
from tamalio.servicios.gestor_descargas import GestorDescargas
from tamalio.servicios.gestor_sesiones import GestorSesiones
from tamalio.servicios.organizador_biblioteca import OrganizadorBiblioteca
from tamalio.servicios.temporizador_humano import TemporizadorHumano

pytestmark = pytest.mark.ffmpeg


class ClienteFalso:
    """Imita a ClienteYtDlp: devuelve el JSON real y «descarga» un audio generado."""

    def __init__(self, info, audio, cookies, bloqueos):
        self._info, self._audio, self._cookies, self._bloqueos = info, audio, cookies, bloqueos

    def extraer(self, fuente):
        if self._bloqueos["restantes"] and self._cookies is None:
            self._bloqueos["restantes"] -= 1
            raise ErrorDeteccionBot(fuente.plataforma, "Sign in to confirm you're not a bot")
        return self._info

    def descargar(self, pista, al_progreso, punto_control):
        punto_control()
        al_progreso(ProgresoDescarga(FaseProceso.DESCARGANDO, 50, 100))
        destino = self._audio.parent / f"Bandcamp-{pista.id_externo}.mp3"
        shutil.copy(self._audio, destino)
        return destino, {"acodec": "mp3", "abr": 128}


class CaratulasFalsas(DescargadorCaratulas):
    def __init__(self, imagen):
        self._imagen = imagen

    def obtener(self, caratula):
        return self._imagen


@pytest.fixture
def entorno(tmp_path, cargar_fixture, generar_audio, imagen_jpeg):
    """Arma un GestorDescargas con dobles en memoria y FFmpeg real."""
    config = Configuracion(usuario="quetzal", carpeta_destino=tmp_path / "Música", carpeta_cache=tmp_path / "cache")
    audio = generar_audio("tono.mp3", ["-c:a", "libmp3lame", "-b:a", "128k"], segundos=0.5)
    info = cargar_fixture("album_bandcamp")
    info["entries"] = info["entries"][:3]
    bloqueos = {"restantes": 0}
    reloj = [0.0]
    catalogo, tareas = RepositorioCatalogoMemoria(), RepositorioTareasMemoria()
    sesiones = GestorSesiones(RepositorioSesionesMemoria())
    gestor = GestorDescargas(
        config=config,
        fabrica_extractores=FabricaExtractores(),
        fabrica_cliente=lambda cookies: ClienteFalso(info, audio, cookies, bloqueos),
        caratulas=CaratulasFalsas(imagen_jpeg),
        conversor=ConversorAudio(EjecutorFfmpeg()),
        etiquetador=EtiquetadorAudio(),
        organizador=OrganizadorBiblioteca(config.raiz_biblioteca),
        catalogo=catalogo,
        tareas=tareas,
        sesiones=sesiones,
        # Reloj simulado: «dormir» adelanta el tiempo sin esperar de verdad.
        temporizador=TemporizadorHumano(
            0, 0, azar=random.Random(1), reloj=lambda: reloj[0], dormir=lambda s: reloj.__setitem__(0, reloj[0] + s)
        ),
    )
    return {
        "gestor": gestor,
        "catalogo": catalogo,
        "tareas": tareas,
        "sesiones": sesiones,
        "bloqueos": bloqueos,
        "config": config,
        "tmp": tmp_path,
    }


def encolar(entorno, detector, url="https://ghostdata.bandcamp.com/album/symphony-of-the-shepherdess"):
    tarea, _ = entorno["tareas"].agregar(detector.detectar(url))
    return tarea


def test_album_completo(entorno, detector):
    observador = ObservadorRegistrador()
    resumen = entorno["gestor"].procesar(encolar(entorno, detector), ControlEjecucion(), observador)
    assert (resumen.completadas, resumen.fallidas) == (3, 0)
    assert entorno["tareas"].tareas[1].estado is EstadoDescarga.COMPLETADA
    carpeta = entorno["config"].raiz_biblioteca / "Bandcamp" / "GHOST DATA" / "Symphony of the Shepherdess (2022)"
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "01 - Beyond Eternity (feat. Skye Light).mp3",
        "02 - Adagio For Souls (feat. COR!S & dreamiecloud).mp3",
        "03 - Healing Light (feat. Azuria Sky).mp3",
    ]
    assert len(entorno["catalogo"].pistas) == 3
    assert observador.nombres().count("completar_pista") == 3


def test_segunda_vez_omite_lo_que_ya_esta(entorno, detector):
    entorno["gestor"].procesar(encolar(entorno, detector), ControlEjecucion(), ObservadorRegistrador())
    tarea = entorno["tareas"].obtener(1)
    tarea.reintentar()
    resumen = entorno["gestor"].procesar(tarea, ControlEjecucion(), ObservadorRegistrador())
    assert (resumen.completadas, resumen.omitidas) == (0, 3)


def test_bloqueo_pide_cookies_y_reintenta(entorno, detector, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    entorno["bloqueos"]["restantes"] = 1
    preguntas = []
    entorno["sesiones"].establecer_solicitante(lambda plataforma, error: preguntas.append(plataforma) or str(cookies))
    observador = ObservadorRegistrador()
    resumen = entorno["gestor"].procesar(encolar(entorno, detector), ControlEjecucion(), observador)
    assert preguntas == [Plataforma.BANDCAMP]
    assert resumen.completadas == 3
    assert entorno["sesiones"].ruta_cookies(Plataforma.BANDCAMP) == cookies.resolve()


def test_bloqueo_persistente_falla_la_tarea(entorno, detector):
    entorno["bloqueos"]["restantes"] = 99  # Nunca deja pasar y el usuario no da cookies.
    resumen = entorno["gestor"].procesar(encolar(entorno, detector), ControlEjecucion(), ObservadorRegistrador())
    assert resumen.completadas == 0
    tarea = entorno["tareas"].tareas[1]
    assert tarea.estado is EstadoDescarga.FALLIDA and "bot" in tarea.ultimo_error


def test_cancelacion_externa_cancela_la_tarea(entorno, detector):
    tarea = encolar(entorno, detector)
    control = ControlEjecucion(intervalo_consulta=0)
    observador = ObservadorRegistrador()
    original = observador.al_iniciar_pista

    def cancelar_desde_otra_terminal(pista, posicion, total):
        # Simula «tamalio cancelar 1» mientras se procesa la segunda pista.
        original(pista, posicion, total)
        if posicion == 2:
            guardada = entorno["tareas"].tareas[1]
            guardada.cancelar()

    observador.al_iniciar_pista = cancelar_desde_otra_terminal
    resumen = entorno["gestor"].procesar(tarea, control, observador)
    assert resumen.completadas == 1
    assert entorno["tareas"].tareas[1].estado is EstadoDescarga.CANCELADA
