"""Entidad central del dominio: una canción con todos sus metadatos."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tamalio.modelos.caratula import Caratula
from tamalio.modelos.plataforma import Plataforma


@dataclass(slots=True)
class Pista:
    """
    Una canción extraída de una plataforma fuente.

    Contiene exactamente los metadatos que se escriben en el fichero de audio:
    nombre, álbum, artistas de la pista, artistas del álbum, número de pista,
    géneros, año y carátula en alta resolución.

    Attributes:
        plataforma: Plataforma de origen.
        id_externo: Identificador de la pista dentro de la plataforma (el de
            ``watch?v=`` en YouTube, el ``track_id`` en Bandcamp, etc.).
        url: Enlace canónico a la pista.
        titulo: Nombre de la canción (ya limpio, sin «Artista - » ni «(Official Video)»).
        album: Nombre del álbum. En sencillos se usa el propio título.
        artistas: Artistas de la canción (principal + invitados), sin duplicados.
        artistas_album: Artistas del álbum.
        numero_pista: Posición dentro del álbum (``1``-based).
        total_pistas: Número total de pistas del álbum, si se conoce.
        generos: Géneros musicales.
        anio: Año de lanzamiento.
        duracion: Duración en segundos.
        caratula: Imagen de portada.
        es_sencillo: ``True`` si no pertenece a un álbum (se guarda en «Sencillos»).
        codec_origen: Códec entregado por la plataforma (``opus``, ``mp4a.40.2``, ``mp3``…).
        bitrate_origen: Tasa de bits de origen en kbps.
        ruta_archivo: Ruta final en la biblioteca, una vez descargada.
        formato: Formato con el que se guardó (valor de :class:`FormatoAudio`).
        info_extraccion: Diccionario crudo de ``yt-dlp`` necesario para descargar.
            No se compara, no se imprime y no se persiste.
    """

    plataforma: Plataforma
    id_externo: str
    url: str
    titulo: str
    album: str
    artistas: list[str]
    artistas_album: list[str]
    numero_pista: int | None = None
    total_pistas: int | None = None
    generos: list[str] = field(default_factory=list)
    anio: int | None = None
    duracion: float | None = None
    caratula: Caratula | None = None
    es_sencillo: bool = False
    codec_origen: str | None = None
    bitrate_origen: float | None = None
    ruta_archivo: Path | None = None
    formato: str | None = None
    info_extraccion: dict[str, Any] | None = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------ #
    # Propiedades de conveniencia
    # ------------------------------------------------------------------ #
    @property
    def clave(self) -> tuple[str, str]:
        """Identidad única dentro del catálogo: ``(plataforma, id_externo)``."""
        return (self.plataforma.value, self.id_externo)

    @property
    def artista_principal(self) -> str:
        """Primer artista de la pista o ``"Artista desconocido"``."""
        return self.artistas[0] if self.artistas else "Artista desconocido"

    @property
    def artista_album_principal(self) -> str:
        """Primer artista del álbum; si no hay, el artista principal de la pista."""
        return self.artistas_album[0] if self.artistas_album else self.artista_principal

    @property
    def descargada(self) -> bool:
        """``True`` si el fichero de audio existe en disco."""
        return self.ruta_archivo is not None and self.ruta_archivo.is_file()

    # ------------------------------------------------------------------ #
    # Sobrescritura de metadatos (desde el fichero de fuentes)
    # ------------------------------------------------------------------ #
    def aplicar_metadatos(self, metadatos: dict[str, Any]) -> None:
        """
        Reemplaza metadatos con los valores que el usuario indicó a mano.

        Las claves admitidas son las del bloque ``metadatos`` del esquema
        ``fuentes.schema.json``: ``titulo``, ``album``, ``artistas``,
        ``artistas_album``, ``generos``, ``anio``, ``numero_pista``,
        ``total_pistas``, ``es_sencillo`` y ``caratula`` (URL). Las claves
        desconocidas se ignoran.
        """
        if not metadatos:
            return
        if "titulo" in metadatos:
            self.titulo = str(metadatos["titulo"])
        if "album" in metadatos:
            self.album = str(metadatos["album"])
            # Si el usuario asigna un álbum explícito, deja de ser sencillo y el
            # «1/1» que se asigna a los sencillos ya no aplica.
            if self.es_sencillo:
                self.numero_pista = self.total_pistas = None
            self.es_sencillo = False
        for clave in ("artistas", "artistas_album", "generos"):
            if clave in metadatos:
                valor = metadatos[clave]
                setattr(self, clave, [valor] if isinstance(valor, str) else list(valor))
        for clave in ("anio", "numero_pista", "total_pistas"):
            if clave in metadatos and metadatos[clave] is not None:
                setattr(self, clave, int(metadatos[clave]))
        # Se procesa después de «album» para que el valor explícito tenga la última palabra.
        if "es_sencillo" in metadatos:
            self.es_sencillo = bool(metadatos["es_sencillo"])
        if metadatos.get("caratula"):
            self.caratula = Caratula(str(metadatos["caratula"]))
        # Sin artista conocido, se asume el artista del álbum indicado por el usuario.
        if self.artistas == ["Artista desconocido"] and self.artistas_album:
            self.artistas = list(self.artistas_album)

    def metadatos_fijos(self) -> dict[str, Any]:
        """
        Metadatos que reproducen exactamente esta pista al volver a descargarla.

        Se usan al importar un catálogo: la pista se descarga suelta (sin el
        contexto de su álbum), así que se fuerzan los datos originales.
        """
        datos: dict[str, Any] = {
            "titulo": self.titulo,
            "album": self.album,
            "artistas": list(self.artistas),
            "artistas_album": list(self.artistas_album),
            "generos": list(self.generos),
            "es_sencillo": self.es_sencillo,
        }
        for clave in ("anio", "numero_pista", "total_pistas"):
            if getattr(self, clave) is not None:
                datos[clave] = getattr(self, clave)
        if self.caratula is not None:
            datos["caratula"] = self.caratula.url
        return datos

    # ------------------------------------------------------------------ #
    # Serialización (catálogo exportable)
    # ------------------------------------------------------------------ #
    def a_diccionario(self, raiz_biblioteca: Path | None = None) -> dict[str, Any]:
        """
        Convierte la pista a un diccionario compatible con ``catalogo.schema.json``.

        Args:
            raiz_biblioteca: Si se indica, la ruta del fichero se exporta como
                relativa a esta carpeta para que sea portable entre equipos.
        """
        ruta_relativa: str | None = None
        if self.ruta_archivo is not None:
            ruta = self.ruta_archivo
            if raiz_biblioteca is not None and ruta.is_relative_to(raiz_biblioteca):
                ruta = ruta.relative_to(raiz_biblioteca)
            # as_posix() → separadores «/» también en Windows (portabilidad).
            ruta_relativa = ruta.as_posix()
        return {
            "plataforma": self.plataforma.value,
            "id_externo": self.id_externo,
            "url": self.url,
            "titulo": self.titulo,
            "album": self.album,
            "artistas": list(self.artistas),
            "artistas_album": list(self.artistas_album),
            "numero_pista": self.numero_pista,
            "total_pistas": self.total_pistas,
            "generos": list(self.generos),
            "anio": self.anio,
            "duracion": self.duracion,
            "es_sencillo": self.es_sencillo,
            "caratula": self.caratula.url if self.caratula else None,
            "formato": self.formato,
            "ruta_relativa": ruta_relativa,
        }

    @classmethod
    def desde_diccionario(cls, datos: dict[str, Any], raiz_biblioteca: Path | None = None) -> Pista:
        """Operación inversa de :meth:`a_diccionario`."""
        ruta: Path | None = None
        if datos.get("ruta_relativa"):
            ruta = Path(datos["ruta_relativa"])
            if raiz_biblioteca is not None and not ruta.is_absolute():
                ruta = raiz_biblioteca / ruta
        caratula = Caratula(datos["caratula"]) if datos.get("caratula") else None
        return cls(
            plataforma=Plataforma(datos["plataforma"]),
            id_externo=str(datos["id_externo"]),
            url=datos["url"],
            titulo=datos["titulo"],
            album=datos.get("album") or datos["titulo"],
            artistas=list(datos.get("artistas") or []),
            artistas_album=list(datos.get("artistas_album") or []),
            numero_pista=datos.get("numero_pista"),
            total_pistas=datos.get("total_pistas"),
            generos=list(datos.get("generos") or []),
            anio=datos.get("anio"),
            duracion=datos.get("duracion"),
            caratula=caratula,
            es_sencillo=bool(datos.get("es_sencillo", False)),
            formato=datos.get("formato"),
            ruta_archivo=ruta,
        )
