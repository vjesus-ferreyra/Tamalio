# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Conjuntos de datos que se pueden borrar con ``tamalio bd borrar``."""

from enum import StrEnum


class ConjuntoDatos(StrEnum):
    """
    Grupos de información guardados en PostgreSQL.

    El valor es el nombre de la opción en la línea de comandos; :attr:`tabla`
    es la tabla real. Así la lista de tablas borrables está cerrada y nunca
    depende de texto escrito por el usuario.
    """

    #: Catálogo de pistas (no borra los ficheros de audio).
    CATALOGO = "catalogo"
    #: Cola de descargas (pendientes, pausadas, fallidas…).
    COLA = "cola"
    #: Rutas registradas de los ficheros de cookies (no borra los ficheros).
    SESIONES = "sesiones"

    @property
    def tabla(self) -> str:
        """Nombre de la tabla de PostgreSQL."""
        return _TABLAS[self]

    @property
    def descripcion(self) -> str:
        """Texto para mostrar al usuario."""
        return _DESCRIPCIONES[self]


_TABLAS: dict[ConjuntoDatos, str] = {
    ConjuntoDatos.CATALOGO: "pistas",
    ConjuntoDatos.COLA: "tareas_descarga",
    ConjuntoDatos.SESIONES: "sesiones_plataforma",
}

_DESCRIPCIONES: dict[ConjuntoDatos, str] = {
    ConjuntoDatos.CATALOGO: "Catálogo de pistas",
    ConjuntoDatos.COLA: "Cola de descargas",
    ConjuntoDatos.SESIONES: "Rutas de cookies registradas",
}
