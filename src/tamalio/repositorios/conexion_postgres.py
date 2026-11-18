"""Conexión a PostgreSQL con psycopg 3 y aplicación de migraciones."""

import psycopg
from psycopg.rows import dict_row

from tamalio.excepciones.error_dependencia_faltante import ErrorDependenciaFaltante
from tamalio.servicios.recursos_empaquetados import RecursosEmpaquetados


class ConexionPostgres:
    """
    Abre (de forma perezosa) una única conexión por proceso.

    - Las filas se devuelven como diccionarios (``dict_row``).
    - Se usa ``autocommit``: cada operación de los repositorios es corta e
      independiente, y así otra terminal ve los cambios de estado al instante
      (necesario para ``tamalio pausar`` / ``cancelar`` en paralelo).

    Args:
        url: Cadena de conexión, p. ej.
            ``postgresql://tamalio:tamalio@localhost:5432/tamalio``.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._conexion: psycopg.Connection | None = None

    @property
    def conexion(self) -> psycopg.Connection:
        """Conexión abierta (se crea en el primer uso y se reabre si se cerró)."""
        if self._conexion is None or self._conexion.closed:
            try:
                self._conexion = psycopg.connect(self._url, autocommit=True, row_factory=dict_row, connect_timeout=5)
            except psycopg.OperationalError as error:
                primera_linea = str(error).strip().splitlines()[0] if str(error).strip() else "sin detalle"
                raise ErrorDependenciaFaltante(
                    "PostgreSQL",
                    f"No se pudo conectar ({primera_linea}). Revisa [base_datos] url o TAMALIO_BD_URL "
                    "y ejecuta «tamalio bd iniciar».",
                ) from error
        return self._conexion

    def version_servidor(self) -> str:
        """Versión del servidor, p. ej. ``"PostgreSQL 18.1"`` (la usa ``tamalio doctor``)."""
        fila = self.conexion.execute("SELECT current_setting('server_version') AS version").fetchone()
        return f"PostgreSQL {fila['version']}"

    def migrar(self) -> list[str]:
        """
        Aplica, en orden y dentro de una transacción cada uno, los guiones SQL pendientes.

        Returns:
            Nombres de los guiones aplicados en esta llamada.
        """
        conexion = self.conexion
        conexion.execute(
            "CREATE TABLE IF NOT EXISTS esquema_migraciones ("
            " nombre TEXT PRIMARY KEY, aplicado_en TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        aplicados = {fila["nombre"] for fila in conexion.execute("SELECT nombre FROM esquema_migraciones")}
        nuevos: list[str] = []
        for nombre in RecursosEmpaquetados.guiones_sql():
            if nombre in aplicados:
                continue
            with conexion.transaction():
                conexion.execute(RecursosEmpaquetados.sql(nombre))
                conexion.execute("INSERT INTO esquema_migraciones (nombre) VALUES (%s)", (nombre,))
            nuevos.append(nombre)
        return nuevos

    def cerrar(self) -> None:
        """Cierra la conexión si estaba abierta."""
        if self._conexion is not None and not self._conexion.closed:
            self._conexion.close()
        self._conexion = None
