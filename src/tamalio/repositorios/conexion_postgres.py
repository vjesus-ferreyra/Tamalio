# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Conexión a PostgreSQL con psycopg 3, migraciones y borrado de datos."""

import logging
import re
from collections.abc import Iterable
from typing import LiteralString, cast

import psycopg
from psycopg import sql
from psycopg.abc import Params
from psycopg.rows import DictRow, dict_row

from tamalio.excepciones.error_dependencia_faltante import ErrorDependenciaFaltante
from tamalio.modelos.conjunto_datos import ConjuntoDatos
from tamalio.servicios.recursos_empaquetados import RecursosEmpaquetados

registro = logging.getLogger(__name__)

#: Tipos de consulta aceptados: texto literal del código o SQL compuesto con ``psycopg.sql``.
#: (psycopg rechaza ``str`` arbitrarios para prevenir inyección SQL.)
type Consulta = LiteralString | sql.SQL | sql.Composed


class ConexionPostgres:
    """
    Abre (de forma perezosa) una única conexión por proceso.

    - Las filas se devuelven como diccionarios (``dict_row``), por eso la
      conexión se tipa como ``Connection[DictRow]``.
    - Se usa ``autocommit``: cada operación de los repositorios es corta e
      independiente, y así otra terminal ve los cambios de estado al instante
      (necesario para ``tamalio pausar`` / ``cancelar`` en paralelo).
    - Todas las consultas pasan por :meth:`ejecutar`, que las registra en modo
      depuración (``--debug``) junto con sus parámetros.

    Args:
        url: Cadena de conexión, p. ej.
            ``postgresql://tamalio:tamalio@localhost:5432/tamalio``.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._conexion: psycopg.Connection[DictRow] | None = None

    @property
    def conexion(self) -> psycopg.Connection[DictRow]:
        """Conexión abierta (se crea en el primer uso y se reabre si se cerró)."""
        if self._conexion is None or self._conexion.closed:
            try:
                # «Connection[DictRow].connect» (y no «psycopg.connect») para que el tipo de fila
                # quede como diccionario: así lo exige el tipado de psycopg ≥ 3.3.
                conexion = psycopg.Connection[DictRow].connect(
                    self._url, autocommit=True, row_factory=dict_row, connect_timeout=5
                )
            except psycopg.OperationalError as error:
                primera_linea = str(error).strip().splitlines()[0] if str(error).strip() else "sin detalle"
                raise ErrorDependenciaFaltante(
                    "PostgreSQL",
                    f"No se pudo conectar ({primera_linea}). Revisa [base_datos] url o TAMALIO_BD_URL "
                    "y ejecuta «tamalio bd iniciar».",
                ) from error
            registro.debug("Conectado a PostgreSQL %s", conexion.info.parameter_status("server_version"))
            self._conexion = conexion
        return self._conexion

    # ------------------------------------------------------------------ #
    # Ejecución de consultas
    # ------------------------------------------------------------------ #
    def ejecutar(self, consulta: Consulta, parametros: Params | None = None) -> psycopg.Cursor[DictRow]:
        """
        Ejecuta una consulta y devuelve el cursor.

        Args:
            consulta: Texto literal o SQL compuesto (``psycopg.sql``).
            parametros: Valores para los marcadores ``%s`` / ``%(nombre)s``.
        """
        conexion = self.conexion
        if registro.isEnabledFor(logging.DEBUG):
            texto = consulta if isinstance(consulta, str) else consulta.as_string(conexion)
            registro.debug("SQL %s · parámetros=%r", re.sub(r"\s+", " ", texto).strip(), parametros)
        return conexion.execute(consulta, parametros)

    def una(self, consulta: Consulta, parametros: Params | None = None) -> DictRow | None:
        """Primera fila del resultado o ``None``."""
        return self.ejecutar(consulta, parametros).fetchone()

    def todas(self, consulta: Consulta, parametros: Params | None = None) -> list[DictRow]:
        """Todas las filas del resultado."""
        return self.ejecutar(consulta, parametros).fetchall()

    # ------------------------------------------------------------------ #
    # Mantenimiento
    # ------------------------------------------------------------------ #
    def version_servidor(self) -> str:
        """Versión del servidor, p. ej. ``"PostgreSQL 18.1"`` (la usa ``tamalio doctor``)."""
        fila = self.una("SELECT current_setting('server_version') AS version")
        return f"PostgreSQL {fila['version']}" if fila else "PostgreSQL (versión desconocida)"

    def migrar(self) -> list[str]:
        """
        Aplica, en orden y dentro de una transacción cada uno, los guiones SQL pendientes.

        Returns:
            Nombres de los guiones aplicados en esta llamada.
        """
        self.ejecutar(
            "CREATE TABLE IF NOT EXISTS esquema_migraciones ("
            " nombre TEXT PRIMARY KEY, aplicado_en TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        aplicados = {fila["nombre"] for fila in self.todas("SELECT nombre FROM esquema_migraciones")}
        nuevos: list[str] = []
        for nombre in RecursosEmpaquetados.guiones_sql():
            if nombre in aplicados:
                continue
            with self.conexion.transaction():
                # El guion viaja dentro del paquete (no proviene del usuario): es seguro
                # tratarlo como literal. ``cast`` solo informa al verificador de tipos.
                self.ejecutar(cast(LiteralString, RecursosEmpaquetados.sql(nombre)))
                self.ejecutar("INSERT INTO esquema_migraciones (nombre) VALUES (%s)", (nombre,))
            nuevos.append(nombre)
        return nuevos

    def contar(self, conjuntos: Iterable[ConjuntoDatos]) -> dict[ConjuntoDatos, int]:
        """Número de filas de cada conjunto de datos (0 si la tabla aún no existe)."""
        resultado: dict[ConjuntoDatos, int] = {}
        for conjunto in conjuntos:
            if not self._existe(conjunto.tabla):
                resultado[conjunto] = 0
                continue
            fila = self.una(sql.SQL("SELECT count(*) AS total FROM {}").format(sql.Identifier(conjunto.tabla)))
            resultado[conjunto] = int(fila["total"]) if fila else 0
        return resultado

    def vaciar(self, conjuntos: Iterable[ConjuntoDatos]) -> None:
        """
        Borra **todas** las filas de los conjuntos indicados en una sola transacción.

        ``TRUNCATE … RESTART IDENTITY`` reinicia también los contadores de ID.
        La estructura (tablas, índices, migraciones) se conserva. Es irreversible.
        """
        existentes = [c for c, total in self.contar(conjuntos).items() if self._existe(c.tabla) or total]
        tablas = [sql.Identifier(conjunto.tabla) for conjunto in existentes]
        if not tablas:
            return
        with self.conexion.transaction():
            self.ejecutar(sql.SQL("TRUNCATE {} RESTART IDENTITY").format(sql.SQL(", ").join(tablas)))

    def _existe(self, tabla: str) -> bool:
        """``True`` si la tabla ya fue creada (``tamalio bd iniciar``)."""
        fila = self.una("SELECT to_regclass(%s) IS NOT NULL AS existe", (tabla,))
        return bool(fila and fila["existe"])

    def cerrar(self) -> None:
        """Cierra la conexión si estaba abierta."""
        if self._conexion is not None and not self._conexion.closed:
            self._conexion.close()
        self._conexion = None
