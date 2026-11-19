# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Excepción para herramientas externas ausentes (FFmpeg, QuickJS, PostgreSQL…)."""

from tamalio.excepciones.error_tamalio import ErrorTamalio


class ErrorDependenciaFaltante(ErrorTamalio):
    """
    Falta un programa o servicio externo necesario para continuar.

    Attributes:
        dependencia: Nombre de la herramienta ausente.
    """

    def __init__(self, dependencia: str, sugerencia: str) -> None:
        super().__init__(f"No se encontró la dependencia «{dependencia}».", sugerencia=sugerencia)
        self.dependencia = dependencia
