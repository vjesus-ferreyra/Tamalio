# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Pruebas del modo depuración, de la cancelación rápida y de la confirmación de borrado."""

import io
import logging

import pytest
from yt_dlp.utils import DownloadCancelled

from tamalio.configuracion.configuracion import Configuracion
from tamalio.controladores.controlador_sistema import ControladorSistema
from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada
from tamalio.modelos.alcance_cancelacion import AlcanceCancelacion
from tamalio.modelos.conjunto_datos import ConjuntoDatos
from tamalio.repositorios.conexion_postgres import ConexionPostgres
from tamalio.servicios.control_ejecucion import ControlEjecucion
from tamalio.servicios.registro_yt_dlp import RegistroYtDlp
from tamalio.vistas.analizador_argumentos import AnalizadorArgumentos
from tamalio.vistas.vista_consola import VistaConsola


# ---------------------------------------------------------------------- #
# Cancelación durante la extracción
# ---------------------------------------------------------------------- #
def test_registro_de_yt_dlp_atiende_la_cancelacion():
    """Cada mensaje de yt-dlp (uno por petición) es un punto de control."""
    control = ControlEjecucion()
    registro = RegistroYtDlp()
    registro.punto_control = control.punto_control
    registro.debug("[youtube:tab] Downloading webpage")  # Sin cancelación: no pasa nada.
    control.cancelar_tarea()
    with pytest.raises(DownloadCancelled):
        registro.debug("[youtube] abc: Downloading webpage")
    assert registro.senal is not None and registro.senal.alcance is AlcanceCancelacion.TAREA


def test_registro_sin_punto_de_control_no_interrumpe():
    RegistroYtDlp().warning("WARNING: algo")  # No debe lanzar nada.


# ---------------------------------------------------------------------- #
# Vista: modo depuración y aviso de orden pendiente
# ---------------------------------------------------------------------- #
def test_vista_en_depuracion_muestra_hora_nivel_y_componente():
    salida = io.StringIO()
    vista = VistaConsola(salida=salida, color=False, depuracion=True)
    vista.mostrar_registro(logging.DEBUG, "tamalio.servicios.ejecutor_ffmpeg", "FFmpeg $ ffmpeg -i a\nlinea 2")
    texto = salida.getvalue()
    assert "DEBUG" in texto and "ffmpeg" in texto and "FFmpeg $ ffmpeg -i a" in texto
    assert "linea 2" in texto.splitlines()[1]


def test_vista_normal_oculta_depuracion():
    salida = io.StringIO()
    VistaConsola(salida=salida, color=False).mostrar_registro(logging.DEBUG, "tamalio.x", "secreto")
    assert salida.getvalue() == ""


def test_orden_pendiente_se_dibuja_en_la_zona_en_vivo():
    vista = VistaConsola(salida=io.StringIO(), color=False)
    vista.iniciar_lote(1)
    vista.mostrar_accion_pendiente("Cancelando tarea")
    lineas = vista._lineas_vivas()
    assert "Cancelando tarea" in lineas[1] and "petición en curso" in lineas[1]
    vista.mostrar_accion_pendiente(None)
    assert "Cancelando" not in vista._lineas_vivas()[1]
    vista.terminar_lote()


# ---------------------------------------------------------------------- #
# Configuración y argumentos
# ---------------------------------------------------------------------- #
def test_resumen_oculta_la_contrasena():
    config = Configuracion(bd_url="postgresql://tamalio:secreta@localhost:5432/tamalio")
    assert config.resumen()["bd_url"] == "postgresql://tamalio:****@localhost:5432/tamalio"


def test_debug_por_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("TAMALIO_DEBUG", "1")
    config = Configuracion()
    config._aplicar_entorno()
    assert config.depuracion


def test_argumentos_de_borrado():
    espacio = AnalizadorArgumentos(color=False).analizar(["bd", "borrar", "--cola", "--sesiones"])
    assert espacio.conjuntos == ["cola", "sesiones"] and espacio.confirmar is None
    espacio = AnalizadorArgumentos(color=False).analizar(["--debug", "bd", "borrar", "--confirmar", "BORRAR"])
    assert espacio.debug and espacio.conjuntos is None


# ---------------------------------------------------------------------- #
# Confirmación del borrado (sin PostgreSQL)
# ---------------------------------------------------------------------- #
class ConexionFalsa(ConexionPostgres):
    """Cuenta y «vacía» en memoria."""

    def __init__(self) -> None:
        super().__init__("postgresql://falsa")
        self.datos = {ConjuntoDatos.CATALOGO: 12, ConjuntoDatos.COLA: 3, ConjuntoDatos.SESIONES: 1}
        self.vaciados: list[ConjuntoDatos] = []

    def contar(self, conjuntos):
        return {c: self.datos[c] for c in conjuntos}

    def vaciar(self, conjuntos):
        self.vaciados.extend(conjuntos)


class VistaConRespuesta(VistaConsola):
    """Vista que responde automáticamente a la pregunta de confirmación."""

    def __init__(self, respuesta: str | None) -> None:
        self.texto = io.StringIO()
        super().__init__(salida=self.texto, color=False)
        self.respuesta = respuesta

    def preguntar(self, pregunta, predeterminado=None):
        return self.respuesta


@pytest.mark.parametrize(
    ("respuesta", "codigo", "borra"),
    [("BORRAR", 0, True), ("si", 1, False), ("", 1, False), (None, 1, False), ("  BORRAR  ", 0, True)],
)
def test_borrado_pide_escribir_borrar(respuesta, codigo, borra):
    conexion = ConexionFalsa()
    vista = VistaConRespuesta(respuesta)
    assert ControladorSistema(vista).borrar_bd(conexion, list(ConjuntoDatos), None) == codigo
    assert bool(conexion.vaciados) is borra
    texto = vista.texto.getvalue()
    assert "IRREVERSIBLE" in texto and "12" in texto


def test_borrado_con_confirmar_no_pregunta():
    conexion = ConexionFalsa()
    vista = VistaConRespuesta("esto no se usa")
    assert ControladorSistema(vista).borrar_bd(conexion, [ConjuntoDatos.COLA], "BORRAR") == 0
    assert conexion.vaciados == [ConjuntoDatos.COLA]


def test_cancelacion_en_extraccion_llega_al_cliente(tmp_path, detector, monkeypatch):
    """ClienteYtDlp relanza la señal del usuario en lugar del error de yt-dlp."""
    import random

    from tamalio.servicios.cliente_yt_dlp import ClienteYtDlp
    from tamalio.servicios.temporizador_humano import TemporizadorHumano

    cliente = ClienteYtDlp(Configuracion(carpeta_cache=tmp_path), tmp_path, TemporizadorHumano(azar=random.Random(1)))
    control = ControlEjecucion()

    class YdlFalso:
        def __init__(self, opciones):
            self.logger = opciones["logger"]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, url, download=False):
            control.cancelar_tarea()  # El usuario pulsa [c] a mitad de la extracción…
            self.logger.debug("[youtube] siguiente petición")  # …y la siguiente petición lo detecta.
            raise AssertionError("no debió llegar aquí")

    monkeypatch.setattr(cliente, "_crear", YdlFalso)
    with pytest.raises(ErrorDescargaCancelada):
        cliente.extraer(detector.detectar("https://youtu.be/FB9u24ZpDek"), control.punto_control)
