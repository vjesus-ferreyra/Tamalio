# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Objeto de transferencia (DTO) con el avance de la fase actual de una pista."""

from dataclasses import dataclass

from tamalio.modelos.fase_proceso import FaseProceso


@dataclass(frozen=True, slots=True)
class ProgresoDescarga:
    """
    Instantánea del avance que el modelo envía a la vista.

    Attributes:
        fase: Fase en la que está la pista.
        completado: Cantidad procesada (bytes al descargar, segundos al convertir).
        total: Cantidad total, si se conoce.
        velocidad: Bytes por segundo (solo al descargar).
        eta: Segundos estimados para terminar.
    """

    fase: FaseProceso
    completado: float = 0.0
    total: float | None = None
    velocidad: float | None = None
    eta: float | None = None

    @property
    def fraccion(self) -> float | None:
        """Avance entre ``0.0`` y ``1.0``, o ``None`` si el total es desconocido."""
        if not self.total:
            return None
        return max(0.0, min(1.0, self.completado / self.total))
