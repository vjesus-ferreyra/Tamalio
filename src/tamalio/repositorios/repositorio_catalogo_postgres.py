# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Implementación PostgreSQL del catálogo musical."""

from pathlib import Path
from typing import Any, ClassVar

from psycopg import sql

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

    #: Columnas en el orden en que se insertan y leen.
    _CAMPOS: ClassVar[tuple[str, ...]] = (
        "plataforma",
        "id_externo",
        "url",
        "titulo",
        "album",
        "artistas",
        "artistas_album",
        "numero_pista",
        "total_pistas",
        "generos",
        "anio",
        "duracion",
        "url_caratula",
        "es_sencillo",
        "codec_origen",
        "bitrate_origen",
        "formato",
        "ruta_archivo",
    )
    #: Lista de columnas como SQL seguro (identificadores escapados por psycopg).
    _COLUMNAS: ClassVar[sql.Composed] = sql.SQL(", ").join(sql.Identifier(c) for c in _CAMPOS)

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
        # Se compone con psycopg.sql: los nombres de columna se escapan como
        # identificadores y los valores viajan como parámetros (sin inyección SQL).
        actualizables = [c for c in self._CAMPOS if c not in {"plataforma", "id_externo"}]
        consulta = sql.SQL(
            "INSERT INTO pistas ({columnas}) VALUES ({marcadores}) "
            "ON CONFLICT (plataforma, id_externo) DO UPDATE SET {actualizaciones}"
        ).format(
            columnas=self._COLUMNAS,
            marcadores=sql.SQL(", ").join(sql.Placeholder(c) for c in self._CAMPOS),
            actualizaciones=sql.SQL(", ").join(
                sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(c)) for c in actualizables
            ),
        )
        self._bd.ejecutar(consulta, valores)

    def obtener(self, plataforma: Plataforma, id_externo: str) -> Pista | None:
        """Ver :meth:`RepositorioCatalogo.obtener`."""
        fila = self._bd.una(
            sql.SQL("SELECT {} FROM pistas WHERE plataforma = %s AND id_externo = %s").format(self._COLUMNAS),
            (plataforma.value, id_externo),
        )
        return self._a_pista(fila) if fila else None

    def buscar_por_ruta(self, ruta: Path) -> Pista | None:
        """Ver :meth:`RepositorioCatalogo.buscar_por_ruta`."""
        fila = self._bd.una(
            sql.SQL("SELECT {} FROM pistas WHERE ruta_archivo = %s").format(self._COLUMNAS), (str(ruta),)
        )
        return self._a_pista(fila) if fila else None

    def listar(self, plataforma: Plataforma | None = None, texto: str | None = None) -> list[Pista]:
        """Ver :meth:`RepositorioCatalogo.listar`."""
        condiciones: list[sql.SQL] = []
        parametros: list[Any] = []
        if plataforma is not None:
            condiciones.append(sql.SQL("plataforma = %s"))
            parametros.append(plataforma.value)
        if texto:
            # ILIKE sin distinguir mayúsculas; se busca también dentro de los arreglos de artistas.
            # El texto se escapa para que «%» y «_» se busquen literalmente y no como comodines.
            condiciones.append(
                sql.SQL(
                    "(titulo ILIKE %s ESCAPE '\\' OR album ILIKE %s ESCAPE '\\' "
                    "OR array_to_string(artistas, ' ') ILIKE %s ESCAPE '\\' "
                    "OR array_to_string(artistas_album, ' ') ILIKE %s ESCAPE '\\')"
                )
            )
            parametros.extend([self._patron_contiene(texto)] * 4)
        donde = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(condiciones)) if condiciones else sql.SQL("")
        filas = self._bd.todas(
            sql.SQL(
                "SELECT {} FROM pistas {} "
                "ORDER BY plataforma, artistas_album[1], album, numero_pista NULLS LAST, titulo"
            ).format(self._COLUMNAS, donde),
            parametros,
        )
        return [self._a_pista(fila) for fila in filas]

    @staticmethod
    def _patron_contiene(texto: str) -> str:
        """
        Patrón ``LIKE`` que busca ``texto`` en cualquier posición, sin comodines del usuario.

        Se escapa primero la barra invertida (el carácter de escape) y después ``%`` y ``_``;
        así «100%» o «mi_cancion» coinciden solo con ese texto exacto.
        """
        escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escapado}%"

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
