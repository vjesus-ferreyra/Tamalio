# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

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

    def emit(self, record: logging.LogRecord) -> None:
        """Formatea el registro y lo pasa a la vista (el nombre ``record`` lo exige ``logging.Handler``)."""
        try:
            self._vista.mostrar_registro(record.levelno, record.name, record.getMessage())
        except Exception:
            self.handleError(record)
