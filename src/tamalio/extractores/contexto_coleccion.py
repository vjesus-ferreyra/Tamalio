"""Datos compartidos por todas las pistas de un álbum o lista."""

from dataclasses import dataclass

from tamalio.modelos.caratula import Caratula


@dataclass(frozen=True, slots=True)
class ContextoColeccion:
    """
    Información de la colección que se hereda a cada pista.

    Por ejemplo, en el álbum de YouTube «FIRESTARTER» las tres primeras
    entradas son videos oficiales sin metadatos musicales: el nombre del álbum,
    su artista, su año y su carátula salen de este contexto.

    Attributes:
        titulo: Nombre de la colección (álbum o lista).
        identificador: ID de la colección en la plataforma.
        es_album: ``True`` si la colección es un álbum/EP real. Si es una lista
            de reproducción cualquiera, cada pista conserva su propio álbum.
        total: Número de pistas disponibles.
        artista: Artista del álbum (el más frecuente entre las pistas).
        anio: Año más frecuente entre las pistas.
        caratula: Carátula del álbum.
    """

    titulo: str
    identificador: str
    es_album: bool
    total: int
    artista: str | None = None
    anio: int | None = None
    caratula: Caratula | None = None
