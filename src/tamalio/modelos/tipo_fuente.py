"""Clasificación de una fuente: pista individual o colección de pistas."""

from enum import StrEnum


class TipoFuente(StrEnum):
    """Qué contiene una URL antes de consultarla con ``yt-dlp``."""

    #: Una sola canción (``watch?v=``, ``/track/``, ``soundcloud.com/usuario/pista``).
    PISTA = "pista"
    #: Álbum, EP, lista de reproducción, *set* o discografía.
    COLECCION = "coleccion"
    #: No se puede saber solo con la URL (enlaces cortos, dominios propios…).
    DESCONOCIDO = "desconocido"
