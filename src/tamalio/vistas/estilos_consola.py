"""Colores y estilos ANSI para la terminal, con soporte para ``NO_COLOR`` y Windows."""

import os
import re
import sys
from typing import TextIO


class EstilosConsola:
    """
    Aplica estilos ANSI solo cuando la terminal los soporta.

    Reglas para decidir si se usa color:

    1. ``--sin-color`` o la variable ``NO_COLOR`` (estándar https://no-color.org) → sin color.
    2. ``FORCE_COLOR`` → con color aunque la salida no sea una terminal.
    3. En otro caso, color solo si la salida es una terminal interactiva.

    En Windows se activa el modo de «procesamiento de terminal virtual» para que
    la consola clásica también interprete las secuencias ANSI.

    Args:
        salida: Flujo de salida (``sys.stdout`` por defecto).
        color: Fuerza (``True``/``False``) o detecta automáticamente (``None``).
    """

    _ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

    def __init__(self, salida: TextIO | None = None, color: bool | None = None) -> None:
        self._salida = salida or sys.stdout
        self.es_terminal = self._es_terminal(self._salida)
        if color is None:
            if os.environ.get("NO_COLOR"):
                color = False
            elif os.environ.get("FORCE_COLOR"):
                color = True
            else:
                color = self.es_terminal
        self.color = color
        if self.color and os.name == "nt":
            self._activar_vt_windows()
        codificacion = (getattr(self._salida, "encoding", "") or "").lower()
        #: ``True`` si se pueden imprimir símbolos Unicode (barras, viñetas, emoji).
        self.unicode = "utf" in codificacion

    # ------------------------------------------------------------------ #
    @staticmethod
    def _es_terminal(salida: TextIO) -> bool:
        try:
            return salida.isatty()
        except AttributeError, ValueError:
            return False

    @staticmethod
    def _activar_vt_windows() -> None:
        """Habilita ENABLE_VIRTUAL_TERMINAL_PROCESSING en la consola de Windows."""
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            manejador = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            modo = ctypes.c_uint32()
            if kernel32.GetConsoleMode(manejador, ctypes.byref(modo)):
                kernel32.SetConsoleMode(manejador, modo.value | 0x0004)
        except AttributeError, OSError:
            pass

    # ------------------------------------------------------------------ #
    def aplicar(self, texto: str, *codigos: str) -> str:
        """Envuelve ``texto`` con los códigos SGR indicados (p. ej. ``"1"``, ``"36"``)."""
        if not self.color or not codigos:
            return texto
        return f"\x1b[{';'.join(codigos)}m{texto}\x1b[0m"

    def negrita(self, texto: str) -> str:
        """Texto en negrita."""
        return self.aplicar(texto, "1")

    def tenue(self, texto: str) -> str:
        """Texto atenuado (gris)."""
        return self.aplicar(texto, "2")

    def acento(self, texto: str) -> str:
        """Color de acento de Tamalio (amarillo maíz)."""
        return self.aplicar(texto, "38;5;214")

    def exito(self, texto: str) -> str:
        """Verde."""
        return self.aplicar(texto, "32")

    def aviso(self, texto: str) -> str:
        """Amarillo."""
        return self.aplicar(texto, "33")

    def error(self, texto: str) -> str:
        """Rojo."""
        return self.aplicar(texto, "31")

    def info(self, texto: str) -> str:
        """Cian."""
        return self.aplicar(texto, "36")

    def simbolo(self, unicode: str, ascii_: str) -> str:
        """Elige el símbolo Unicode o su alternativa ASCII según la terminal."""
        return unicode if self.unicode else ascii_

    @classmethod
    def sin_estilo(cls, texto: str) -> str:
        """Quita las secuencias ANSI (para medir el ancho visible)."""
        return cls._ANSI.sub("", texto)
