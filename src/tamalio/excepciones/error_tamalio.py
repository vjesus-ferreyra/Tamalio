# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""
Excepción base de la aplicación.

Todas las excepciones propias heredan de :class:`ErrorTamalio`. Así la capa de
vista puede capturar un único tipo y mostrar un mensaje amable al usuario sin
ocultar errores inesperados de Python (que no heredan de esta clase).
"""


class ErrorTamalio(Exception):
    """
    Error genérico y controlado de Tamalio.

    Attributes:
        mensaje: Texto pensado para mostrarse tal cual al usuario.
        sugerencia: Acción opcional que el usuario puede realizar para resolverlo.
    """

    def __init__(self, mensaje: str, sugerencia: str | None = None) -> None:
        # Se llama al constructor de ``Exception`` para que ``str(error)`` funcione.
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.sugerencia = sugerencia
