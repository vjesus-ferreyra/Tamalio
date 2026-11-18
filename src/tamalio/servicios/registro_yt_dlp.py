"""Adaptador que redirige los mensajes de ``yt-dlp`` al módulo ``logging``."""

import logging
import re


class RegistroYtDlp:
    """
    Objeto *logger* con la interfaz que espera ``yt-dlp`` (``debug``, ``info``,
    ``warning`` y ``error``).

    Sin este adaptador ``yt-dlp`` imprimiría directo en la terminal y rompería
    las barras de progreso. Así sus mensajes van al fichero de registro y, en
    modo ``--detallado``, la vista los muestra con estilo.
    """

    # yt-dlp colorea algunos mensajes con secuencias ANSI; se quitan.
    _ANSI = re.compile(r"\x1b\[[0-9;]*m")

    def __init__(self, nombre: str = "tamalio.yt_dlp") -> None:
        self._registro = logging.getLogger(nombre)

    def _limpiar(self, mensaje: str) -> str:
        """Quita colores ANSI y espacios sobrantes."""
        return self._ANSI.sub("", mensaje).strip()

    def debug(self, mensaje: str) -> None:
        """``yt-dlp`` envía aquí tanto la depuración como los mensajes informativos."""
        texto = self._limpiar(mensaje)
        if texto.startswith("[debug] "):
            self._registro.debug(texto.removeprefix("[debug] "))
        else:
            self._registro.info(texto)

    def info(self, mensaje: str) -> None:
        """Mensajes informativos."""
        self._registro.info(self._limpiar(mensaje))

    def warning(self, mensaje: str) -> None:
        """Advertencias (p. ej. formato no disponible, firma JS lenta…)."""
        self._registro.warning(self._limpiar(mensaje).removeprefix("WARNING: "))

    def error(self, mensaje: str) -> None:
        """Errores; Tamalio además los recibe como excepciones."""
        self._registro.error(self._limpiar(mensaje).removeprefix("ERROR: "))
