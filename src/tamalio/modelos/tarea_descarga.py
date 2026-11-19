# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Entidad persistente que permite pausar, reanudar, reintentar y cancelar descargas."""

from dataclasses import dataclass
from datetime import UTC, datetime

from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.fuente import Fuente


@dataclass(slots=True)
class TareaDescarga:
    """
    Una fuente en la cola de descargas, con su estado y su historial de intentos.

    Las tareas viven en PostgreSQL (tabla ``tareas_descarga``); por eso, si el
    programa se cierra, una tarea *pausada* o *pendiente* se puede reanudar
    después con ``tamalio reanudar``, incluso desde otra terminal.

    Attributes:
        id: Clave primaria en la base de datos (``None`` antes de guardarse).
        fuente: Enlace a procesar.
        estado: Estado actual de la máquina de estados.
        intentos: Veces que se ha intentado procesar.
        ultimo_error: Mensaje del último fallo, si lo hubo.
        creado_en: Marca de tiempo de creación.
        actualizado_en: Última modificación.
    """

    fuente: Fuente
    id: int | None = None
    estado: EstadoDescarga = EstadoDescarga.PENDIENTE
    intentos: int = 0
    ultimo_error: str | None = None
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None

    # ------------------------------------------------------------------ #
    # Transiciones de estado: cada método valida que el cambio sea legal.
    # ------------------------------------------------------------------ #
    def _cambiar(self, destino: EstadoDescarga) -> None:
        """Aplica la transición o lanza ``ValueError`` si no está permitida."""
        if self.estado is destino:
            return
        if not self.estado.puede_pasar_a(destino):
            raise ValueError(f"Transición inválida: {self.estado.value} → {destino.value}.")
        self.estado = destino
        self.actualizado_en = datetime.now(UTC)

    def iniciar(self) -> None:
        """Marca la tarea como en proceso y cuenta un intento más."""
        self._cambiar(EstadoDescarga.EN_PROCESO)
        self.intentos += 1

    def pausar(self) -> None:
        """Deja la tarea pausada; se reanudará con ``tamalio reanudar``."""
        self._cambiar(EstadoDescarga.PAUSADA)

    def reanudar(self) -> None:
        """Devuelve una tarea pausada a la cola (pendiente)."""
        self._cambiar(EstadoDescarga.PENDIENTE)

    def completar(self) -> None:
        """Marca la tarea como terminada con éxito y limpia el último error."""
        self._cambiar(EstadoDescarga.COMPLETADA)
        self.ultimo_error = None

    def fallar(self, mensaje: str) -> None:
        """Marca la tarea como fallida guardando el motivo."""
        self._cambiar(EstadoDescarga.FALLIDA)
        self.ultimo_error = mensaje

    def cancelar(self) -> None:
        """Cancela la tarea; puede volver a la cola con ``reintentar``."""
        self._cambiar(EstadoDescarga.CANCELADA)

    def reintentar(self) -> None:
        """Devuelve a pendiente una tarea fallida, cancelada o completada."""
        self._cambiar(EstadoDescarga.PENDIENTE)
