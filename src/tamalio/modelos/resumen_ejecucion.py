# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Contadores de lo ocurrido durante una ejecución, para el resumen final."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class ResumenEjecucion:
    """
    Totales acumulados de una tarea o de un lote completo.

    Attributes:
        completadas: Pistas descargadas y guardadas correctamente.
        omitidas: Pistas que ya estaban en el catálogo o que el usuario saltó.
        saltadas: De las omitidas, cuántas saltó el usuario con la tecla [s].
        fallidas: Pistas que fallaron.
        bytes_totales: Tamaño acumulado de los ficheros finales.
        errores: Mensajes de error (uno por pista fallida).
    """

    completadas: int = 0
    omitidas: int = 0
    saltadas: int = 0
    fallidas: int = 0
    bytes_totales: int = 0
    errores: list[str] = field(default_factory=list)

    def sumar(self, otro: ResumenEjecucion) -> None:
        """Acumula en este resumen los valores de ``otro``."""
        self.completadas += otro.completadas
        self.omitidas += otro.omitidas
        self.saltadas += otro.saltadas
        self.fallidas += otro.fallidas
        self.bytes_totales += otro.bytes_totales
        self.errores.extend(otro.errores)

    @property
    def total(self) -> int:
        """Pistas vistas en total."""
        return self.completadas + self.omitidas + self.fallidas
