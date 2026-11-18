"""Implementación PostgreSQL del catálogo musical."""

from pathlib import Path
from typing import Any

from tamalio.interfaces.repositorio_catalogo import RepositorioCatalogo
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.conexion_postgres import ConexionPostgres


class RepositorioCatalogoPostgres(RepositorioCatalogo):
    """
    Guarda las pistas en la tabla ``pistas``.

    Las listas de Python (``artistas``, ``generos``…) se guardan como ``TEXT[]``
    nativos de PostgreSQL; psycopg 3 hace la conversión automáticamente.

    Args:
        conexion: Conexión compartida.
    """

    _COLUMNAS = (
        "plataforma, id_externo, url, titulo, album, artistas, artistas_album, numero_pista, total_pistas, "
        "generos, anio, duracion, url_caratula, es_sencillo, codec_origen, bitrate_origen, formato, ruta_archivo"
    )

    def __init__(self, conexion: ConexionPostgres) -> None:
        self._bd = conexion

    def guardar(self, pista: Pista) -> None:
        """*Upsert* por ``(plataforma, id_externo)``: inserta o actualiza todos los campos."""
        valores = {
            "plataforma": pista.plataforma.value,
            "id_externo": pista.id_externo,
            "url": pista.url,
            "titulo": pista.titulo,
            "album": pista.album,
            "artistas": list(pista.artistas),
            "artistas_album": list(pista.artistas_album),
            "numero_pista": pista.numero_pista,
            "total_pistas": pista.total_pistas,
            "generos": list(pista.generos),
            "anio": pista.anio,
            "duracion": pista.duracion,
            "url_caratula": pista.caratula.url if pista.caratula else None,
            "es_sencillo": pista.es_sencillo,
            "codec_origen": pista.codec_origen,
            "bitrate_origen": pista.bitrate_origen,
            "formato": pista.formato,
            "ruta_archivo": str(pista.ruta_archivo) if pista.ruta_archivo else None,
        }
        marcadores = ", ".join(f"%({clave})s" for clave in valores)
        actualizaciones = ", ".join(
            f"{clave} = EXCLUDED.{clave}" for clave in valores if clave not in {"plataforma", "id_externo"}
        )
        self._bd.conexion.execute(
            f"INSERT INTO pistas ({self._COLUMNAS}) VALUES ({marcadores}) "
            f"ON CONFLICT (plataforma, id_externo) DO UPDATE SET {actualizaciones}",
            valores,
        )

    def obtener(self, plataforma: Plataforma, id_externo: str) -> Pista | None:
        """Ver :meth:`RepositorioCatalogo.obtener`."""
        fila = self._bd.conexion.execute(
            f"SELECT {self._COLUMNAS} FROM pistas WHERE plataforma = %s AND id_externo = %s",
            (plataforma.value, id_externo),
        ).fetchone()
        return self._a_pista(fila) if fila else None

    def buscar_por_ruta(self, ruta: Path) -> Pista | None:
        """Ver :meth:`RepositorioCatalogo.buscar_por_ruta`."""
        fila = self._bd.conexion.execute(
            f"SELECT {self._COLUMNAS} FROM pistas WHERE ruta_archivo = %s", (str(ruta),)
        ).fetchone()
        return self._a_pista(fila) if fila else None

    def listar(self, plataforma: Plataforma | None = None, texto: str | None = None) -> list[Pista]:
        """Ver :meth:`RepositorioCatalogo.listar`."""
        condiciones: list[str] = []
        parametros: list[Any] = []
        if plataforma is not None:
            condiciones.append("plataforma = %s")
            parametros.append(plataforma.value)
        if texto:
            # ILIKE sin distinguir mayúsculas; se busca también dentro de los arreglos de artistas.
            condiciones.append(
                "(titulo ILIKE %s OR album ILIKE %s OR array_to_string(artistas, ' ') ILIKE %s "
                "OR array_to_string(artistas_album, ' ') ILIKE %s)"
            )
            parametros.extend([f"%{texto}%"] * 4)
        donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        filas = self._bd.conexion.execute(
            f"SELECT {self._COLUMNAS} FROM pistas {donde} "
            "ORDER BY plataforma, artistas_album[1], album, numero_pista NULLS LAST, titulo",
            parametros,
        ).fetchall()
        return [self._a_pista(fila) for fila in filas]

    @staticmethod
    def _a_pista(fila: dict[str, Any]) -> Pista:
        """Convierte una fila de la base de datos en :class:`Pista`."""
        return Pista(
            plataforma=Plataforma(fila["plataforma"]),
            id_externo=fila["id_externo"],
            url=fila["url"],
            titulo=fila["titulo"],
            album=fila["album"],
            artistas=list(fila["artistas"] or []),
            artistas_album=list(fila["artistas_album"] or []),
            numero_pista=fila["numero_pista"],
            total_pistas=fila["total_pistas"],
            generos=list(fila["generos"] or []),
            anio=fila["anio"],
            duracion=float(fila["duracion"]) if fila["duracion"] is not None else None,
            caratula=Caratula(fila["url_caratula"]) if fila["url_caratula"] else None,
            es_sencillo=fila["es_sencillo"],
            codec_origen=fila["codec_origen"],
            bitrate_origen=float(fila["bitrate_origen"]) if fila["bitrate_origen"] is not None else None,
            formato=fila["formato"],
            ruta_archivo=Path(fila["ruta_archivo"]) if fila["ruta_archivo"] else None,
        )
