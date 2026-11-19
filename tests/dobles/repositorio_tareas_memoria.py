# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Cola de descargas en memoria para pruebas unitarias."""

import copy
from collections.abc import Iterable

from tamalio.interfaces.repositorio_tareas import RepositorioTareas
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.tarea_descarga import TareaDescarga


class RepositorioTareasMemoria(RepositorioTareas):
    """Imita la tabla ``tareas_descarga`` (incluida la regla de «URL activa única»)."""

    def __init__(self) -> None:
        self.tareas: dict[int, TareaDescarga] = {}
        self._siguiente = 1

    def agregar(self, fuente: Fuente) -> tuple[TareaDescarga, bool]:
        for tarea in self.tareas.values():
            if tarea.fuente.url == fuente.url and tarea.estado.es_activo:
                return copy.copy(tarea), False
        id_tarea = self._siguiente
        self._siguiente += 1
        tarea = TareaDescarga(fuente=fuente, id=id_tarea)
        self.tareas[id_tarea] = copy.copy(tarea)
        return tarea, True

    def actualizar(self, tarea: TareaDescarga) -> None:
        if tarea.id is None:
            raise ValueError("La tarea no tiene ID.")
        self.tareas[tarea.id] = copy.copy(tarea)

    def obtener(self, id_tarea: int) -> TareaDescarga | None:
        tarea = self.tareas.get(id_tarea)
        return copy.copy(tarea) if tarea else None

    def estado_actual(self, id_tarea: int) -> EstadoDescarga | None:
        tarea = self.tareas.get(id_tarea)
        return tarea.estado if tarea else None

    def listar(self, estados: Iterable[EstadoDescarga] | None = None) -> list[TareaDescarga]:
        filtro = set(estados) if estados is not None else None
        return [copy.copy(t) for t in self.tareas.values() if filtro is None or t.estado in filtro]
