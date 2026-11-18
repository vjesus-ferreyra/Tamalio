"""Puente entre el módulo ``logging`` y la vista de consola."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Solo para el verificador de tipos; evita importaciones circulares.
    from tamalio.vistas.vista_consola import VistaConsola


class ManejadorRegistroConsola(logging.Handler):
    """
    Envía los mensajes de registro a la vista en lugar de imprimirlos directamente.

    Así las advertencias de ``yt-dlp`` o de cualquier módulo aparecen **encima**
    de las barras de progreso, sin romperlas.

    Args:
        vista: Vista de consola que los mostrará.
        nivel: Nivel mínimo (``WARNING`` normalmente, ``DEBUG`` con ``--detallado``).
    """

    def __init__(self, vista: VistaConsola, nivel: int = logging.WARNING) -> None:
        super().__init__(nivel)
        self._vista = vista

    def emit(self, registro: logging.LogRecord) -> None:
        """Formatea el registro y lo pasa a la vista."""
        try:
            self._vista.mostrar_registro(registro.levelno, registro.name, registro.getMessage())
        except Exception:
            self.handleError(registro)
