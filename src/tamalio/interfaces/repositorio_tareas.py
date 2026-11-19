# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Contrato de persistencia de la cola de descargas."""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.tarea_descarga import TareaDescarga


class RepositorioTareas(ABC):
    """Cola persistente que hace posible pausar, reanudar, reintentar y cancelar."""

    @abstractmethod
    def agregar(self, fuente: Fuente) -> tuple[TareaDescarga, bool]:
        """
        Encola la fuente. Si ya existe una tarea **activa** con la misma URL, la reutiliza.

        Returns:
            La tarea y ``True`` si se creó, ``False`` si ya existía.
        """

    @abstractmethod
    def actualizar(self, tarea: TareaDescarga) -> None:
        """Guarda estado, intentos y último error de la tarea."""

    @abstractmethod
    def obtener(self, id_tarea: int) -> TareaDescarga | None:
        """Devuelve la tarea por su ID."""

    @abstractmethod
    def estado_actual(self, id_tarea: int) -> EstadoDescarga | None:
        """
        Lee **solo** el estado desde la base de datos.

        Se consulta periódicamente durante la descarga para detectar si otra
        terminal ejecutó ``tamalio pausar`` o ``tamalio cancelar``.
        """

    @abstractmethod
    def listar(self, estados: Iterable[EstadoDescarga] | None = None) -> list[TareaDescarga]:
        """Lista tareas (opcionalmente filtradas por estado) en orden de creación."""
