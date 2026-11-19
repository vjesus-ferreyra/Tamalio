# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Registro de cookies en memoria para pruebas unitarias."""

from pathlib import Path

from tamalio.interfaces.repositorio_sesiones import RepositorioSesiones
from tamalio.modelos.plataforma import Plataforma


class RepositorioSesionesMemoria(RepositorioSesiones):
    """Diccionario plataforma → ruta."""

    def __init__(self) -> None:
        self.rutas: dict[Plataforma, Path] = {}

    def obtener(self, plataforma: Plataforma) -> Path | None:
        return self.rutas.get(plataforma)

    def guardar(self, plataforma: Plataforma, ruta: Path) -> None:
        self.rutas[plataforma] = ruta

    def eliminar(self, plataforma: Plataforma) -> bool:
        return self.rutas.pop(plataforma, None) is not None

    def listar(self) -> dict[Plataforma, Path]:
        return dict(self.rutas)
