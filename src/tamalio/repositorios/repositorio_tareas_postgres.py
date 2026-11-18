"""Implementación PostgreSQL de la cola de descargas."""

from collections.abc import Iterable
from typing import Any

from psycopg.types.json import Jsonb

from tamalio.interfaces.repositorio_tareas import RepositorioTareas
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.tarea_descarga import TareaDescarga
from tamalio.repositorios.conexion_postgres import ConexionPostgres


class RepositorioTareasPostgres(RepositorioTareas):
    """
    Guarda las tareas en ``tareas_descarga``.

    Las opciones de la fuente (formato, metadatos manuales, comentario…) se
    guardan en una columna ``JSONB`` para no tener que alterar la tabla cada vez
    que se agregue una opción nueva.

    Args:
        conexion: Conexión compartida.
    """

    _COLUMNAS = "id, url, plataforma, estado, intentos, ultimo_error, opciones, creado_en, actualizado_en"

    def __init__(self, conexion: ConexionPostgres) -> None:
        self._bd = conexion

    def agregar(self, fuente: Fuente) -> tuple[TareaDescarga, bool]:
        """Ver :meth:`RepositorioTareas.agregar`."""
        conexion = self._bd.conexion
        existente = conexion.execute(
            f"SELECT {self._COLUMNAS} FROM tareas_descarga "
            "WHERE url = %s AND estado IN ('pendiente', 'en_proceso', 'pausada')",
            (fuente.url,),
        ).fetchone()
        if existente:
            return self._a_tarea(existente), False
        fila = conexion.execute(
            f"INSERT INTO tareas_descarga (url, plataforma, opciones) VALUES (%s, %s, %s) RETURNING {self._COLUMNAS}",
            (fuente.url, fuente.plataforma.value, Jsonb(fuente.opciones())),
        ).fetchone()
        return self._a_tarea(fila), True

    def actualizar(self, tarea: TareaDescarga) -> None:
        """Ver :meth:`RepositorioTareas.actualizar`."""
        if tarea.id is None:
            raise ValueError("No se puede actualizar una tarea sin ID.")
        self._bd.conexion.execute(
            "UPDATE tareas_descarga SET estado = %s, intentos = %s, ultimo_error = %s WHERE id = %s",
            (tarea.estado.value, tarea.intentos, tarea.ultimo_error, tarea.id),
        )

    def obtener(self, id_tarea: int) -> TareaDescarga | None:
        """Ver :meth:`RepositorioTareas.obtener`."""
        fila = self._bd.conexion.execute(
            f"SELECT {self._COLUMNAS} FROM tareas_descarga WHERE id = %s", (id_tarea,)
        ).fetchone()
        return self._a_tarea(fila) if fila else None

    def estado_actual(self, id_tarea: int) -> EstadoDescarga | None:
        """Ver :meth:`RepositorioTareas.estado_actual`."""
        fila = self._bd.conexion.execute("SELECT estado FROM tareas_descarga WHERE id = %s", (id_tarea,)).fetchone()
        return EstadoDescarga(fila["estado"]) if fila else None

    def listar(self, estados: Iterable[EstadoDescarga] | None = None) -> list[TareaDescarga]:
        """Ver :meth:`RepositorioTareas.listar`."""
        if estados is None:
            filas = self._bd.conexion.execute(
                f"SELECT {self._COLUMNAS} FROM tareas_descarga ORDER BY creado_en, id"
            ).fetchall()
        else:
            filas = self._bd.conexion.execute(
                f"SELECT {self._COLUMNAS} FROM tareas_descarga WHERE estado = ANY(%s) ORDER BY creado_en, id",
                ([estado.value for estado in estados],),
            ).fetchall()
        return [self._a_tarea(fila) for fila in filas]

    @staticmethod
    def _a_tarea(fila: dict[str, Any]) -> TareaDescarga:
        """Convierte una fila en :class:`TareaDescarga`."""
        return TareaDescarga(
            id=fila["id"],
            fuente=Fuente.desde_opciones(fila["url"], fila["plataforma"], fila["opciones"] or {}),
            estado=EstadoDescarga(fila["estado"]),
            intentos=fila["intentos"],
            ultimo_error=fila["ultimo_error"],
            creado_en=fila["creado_en"],
            actualizado_en=fila["actualizado_en"],
        )
