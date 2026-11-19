# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Implementación PostgreSQL del registro de ficheros de cookies."""

from pathlib import Path

from tamalio.interfaces.repositorio_sesiones import RepositorioSesiones
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.conexion_postgres import ConexionPostgres


class RepositorioSesionesPostgres(RepositorioSesiones):
    """
    Guarda en ``sesiones_plataforma`` la **ruta** del fichero de cookies.

    Args:
        conexion: Conexión compartida.
    """

    def __init__(self, conexion: ConexionPostgres) -> None:
        self._bd = conexion

    def obtener(self, plataforma: Plataforma) -> Path | None:
        """Ver :meth:`RepositorioSesiones.obtener`."""
        fila = self._bd.una("SELECT ruta_cookies FROM sesiones_plataforma WHERE plataforma = %s", (plataforma.value,))
        return Path(fila["ruta_cookies"]) if fila else None

    def guardar(self, plataforma: Plataforma, ruta: Path) -> None:
        """Ver :meth:`RepositorioSesiones.guardar`."""
        self._bd.ejecutar(
            "INSERT INTO sesiones_plataforma (plataforma, ruta_cookies) VALUES (%s, %s) "
            "ON CONFLICT (plataforma) DO UPDATE SET ruta_cookies = EXCLUDED.ruta_cookies",
            (plataforma.value, str(ruta)),
        )

    def eliminar(self, plataforma: Plataforma) -> bool:
        """Ver :meth:`RepositorioSesiones.eliminar`."""
        cursor = self._bd.ejecutar("DELETE FROM sesiones_plataforma WHERE plataforma = %s", (plataforma.value,))
        return cursor.rowcount > 0

    def listar(self) -> dict[Plataforma, Path]:
        """Ver :meth:`RepositorioSesiones.listar`."""
        filas = self._bd.todas("SELECT plataforma, ruta_cookies FROM sesiones_plataforma ORDER BY plataforma")
        return {Plataforma(fila["plataforma"]): Path(fila["ruta_cookies"]) for fila in filas}
