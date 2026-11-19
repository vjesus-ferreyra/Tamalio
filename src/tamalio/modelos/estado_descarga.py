# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Estados posibles de una tarea de descarga y sus transiciones válidas."""

from enum import StrEnum


class EstadoDescarga(StrEnum):
    """
    Ciclo de vida de una :class:`~tamalio.modelos.tarea_descarga.TareaDescarga`.

    El diagrama completo está en ``docs/arquitectura.md`` (diagrama de estados).
    """

    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    PAUSADA = "pausada"
    COMPLETADA = "completada"
    FALLIDA = "fallida"
    CANCELADA = "cancelada"

    @property
    def es_activo(self) -> bool:
        """``True`` si la tarea aún debe procesarse (pendiente, en proceso o pausada)."""
        return self in {EstadoDescarga.PENDIENTE, EstadoDescarga.EN_PROCESO, EstadoDescarga.PAUSADA}

    @property
    def es_final(self) -> bool:
        """``True`` si la tarea terminó (bien o mal) y no avanzará sola."""
        return not self.es_activo

    def puede_pasar_a(self, destino: EstadoDescarga) -> bool:
        """Indica si la transición ``self → destino`` está permitida."""
        return destino in _TRANSICIONES[self]


# Tabla de transiciones permitidas (máquina de estados).
_TRANSICIONES: dict[EstadoDescarga, frozenset[EstadoDescarga]] = {
    EstadoDescarga.PENDIENTE: frozenset({EstadoDescarga.EN_PROCESO, EstadoDescarga.PAUSADA, EstadoDescarga.CANCELADA}),
    EstadoDescarga.EN_PROCESO: frozenset(
        {
            EstadoDescarga.COMPLETADA,
            EstadoDescarga.FALLIDA,
            EstadoDescarga.PAUSADA,
            EstadoDescarga.CANCELADA,
            # Si el proceso murió (corte de luz, kill…) la tarea se recupera a pendiente.
            EstadoDescarga.PENDIENTE,
        }
    ),
    EstadoDescarga.PAUSADA: frozenset({EstadoDescarga.PENDIENTE, EstadoDescarga.EN_PROCESO, EstadoDescarga.CANCELADA}),
    EstadoDescarga.FALLIDA: frozenset({EstadoDescarga.PENDIENTE, EstadoDescarga.CANCELADA}),
    EstadoDescarga.CANCELADA: frozenset({EstadoDescarga.PENDIENTE}),
    # Una tarea completada puede volver a pendiente si el usuario fuerza la re-descarga.
    EstadoDescarga.COMPLETADA: frozenset({EstadoDescarga.PENDIENTE}),
}
