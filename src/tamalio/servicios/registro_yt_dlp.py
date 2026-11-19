"""Adaptador que redirige los mensajes de ``yt-dlp`` al módulo ``logging``."""

import logging
import re
import threading
from collections.abc import Callable

from yt_dlp.utils import DownloadCancelled

from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada


class RegistroYtDlp:
    """
    Objeto *logger* con la interfaz que espera ``yt-dlp`` (``debug``, ``info``,
    ``warning`` y ``error``).

    Sin este adaptador ``yt-dlp`` imprimiría directo en la terminal y rompería
    las barras de progreso. Así sus mensajes van al fichero de registro y, en
    modo ``--detallado`` o ``--debug``, la vista los muestra con estilo.

    **Cancelación durante la extracción.** ``yt-dlp`` no tiene *hooks* mientras
    analiza una página (en un álbum de YouTube eso puede tardar decenas de
    segundos), pero sí escribe un mensaje antes de cada petición. Si se asigna
    :attr:`punto_control`, se ejecuta en cada mensaje: así una pausa o
    cancelación se atiende en cuanto ``yt-dlp`` termina la petición en curso,
    en lugar de esperar a que acabe toda la extracción.
    """

    # yt-dlp colorea algunos mensajes con secuencias ANSI; se quitan.
    _ANSI = re.compile(r"\x1b\[[0-9;]*m")

    def __init__(self, nombre: str = "tamalio.yt_dlp") -> None:
        self._registro = logging.getLogger(nombre)
        #: Se ejecuta con cada mensaje; puede bloquear (pausa) o cancelar.
        self.punto_control: Callable[[], None] | None = None
        #: Señal de cancelación capturada (para relanzarla fuera de yt-dlp).
        self.senal: ErrorDescargaCancelada | None = None
        #: Se activa cuando Tamalio ya dejó de esperar a esta operación (el usuario
        #: canceló): el hilo de yt-dlp se detiene en su siguiente mensaje.
        self.abandonar = threading.Event()

    def _revisar(self) -> None:
        """Ejecuta el punto de control y convierte la cancelación en ``DownloadCancelled``."""
        if self.abandonar.is_set():
            raise DownloadCancelled("Operación abandonada por Tamalio.")
        if self.punto_control is None:
            return
        try:
            self.punto_control()
        except ErrorDescargaCancelada as senal:
            self.senal = senal
            # Es la excepción que yt-dlp deja pasar sin envolver ni reintentar.
            raise DownloadCancelled(str(senal)) from senal

    def _limpiar(self, mensaje: str) -> str:
        """Quita colores ANSI y espacios sobrantes."""
        return self._ANSI.sub("", mensaje).strip()

    def debug(self, mensaje: str) -> None:
        """``yt-dlp`` envía aquí tanto la depuración como los mensajes informativos."""
        texto = self._limpiar(mensaje)
        self._revisar()
        if texto.startswith("[debug] "):
            self._registro.debug(texto.removeprefix("[debug] "))
        else:
            self._registro.info(texto)

    def info(self, mensaje: str) -> None:
        """Mensajes informativos."""
        self._revisar()
        self._registro.info(self._limpiar(mensaje))

    def warning(self, mensaje: str) -> None:
        """Advertencias (p. ej. formato no disponible, firma JS lenta…)."""
        self._revisar()
        self._registro.warning(self._limpiar(mensaje).removeprefix("WARNING: "))

    def error(self, mensaje: str) -> None:
        """
        Errores de yt-dlp. Se registran solo en el fichero (nivel INFO) porque
        Tamalio también los recibe como excepción y la vista ya los muestra;
        así no aparecen duplicados en la terminal.
        """
        self._registro.info("error: %s", self._limpiar(mensaje).removeprefix("ERROR: "))
