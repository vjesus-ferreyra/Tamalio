"""Enumeración de las plataformas fuente soportadas por Tamalio."""

from enum import StrEnum


class Plataforma(StrEnum):
    """
    Plataformas de donde se puede extraer música.

    YouTube y YouTube Music son **la misma plataforma**: comparten el mismo
    identificador de video (el parámetro ``watch?v=``) y solo cambia el dominio,
    por eso ambas se representan con :attr:`YOUTUBE`.

    El valor de cada miembro (``"youtube"``, …) es el que se guarda en la base
    de datos y en los ficheros de fuentes/catálogo.
    """

    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    BANDCAMP = "bandcamp"

    @property
    def nombre_visible(self) -> str:
        """Nombre bonito para mostrar en la terminal."""
        return _NOMBRES_VISIBLES[self]

    @property
    def nombre_carpeta(self) -> str:
        """Nombre de la carpeta hija dentro de la biblioteca del usuario."""
        # Coincide con el nombre visible; se separa por si en el futuro cambia.
        return _NOMBRES_VISIBLES[self]

    @classmethod
    def desde_texto(cls, texto: str) -> Plataforma:
        """
        Convierte un texto escrito por el usuario en una plataforma.

        Acepta sinónimos comunes: ``"yt"``, ``"ytmusic"``, ``"youtube_music"``,
        ``"sc"``, ``"bc"``… sin importar mayúsculas, espacios o guiones.

        Raises:
            ValueError: Si el texto no corresponde a ninguna plataforma.
        """
        clave = texto.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        try:
            return _SINONIMOS[clave]
        except KeyError:
            validos = ", ".join(miembro.value for miembro in cls)
            raise ValueError(f"Plataforma desconocida «{texto}». Usa una de: {validos}.") from None


# Nombres para la interfaz y las carpetas (diccionario privado del módulo).
_NOMBRES_VISIBLES: dict[Plataforma, str] = {
    Plataforma.YOUTUBE: "YouTube",
    Plataforma.SOUNDCLOUD: "SoundCloud",
    Plataforma.BANDCAMP: "Bandcamp",
}

# Sinónimos normalizados (sin guiones, espacios ni mayúsculas) → plataforma.
_SINONIMOS: dict[str, Plataforma] = {
    "youtube": Plataforma.YOUTUBE,
    "yt": Plataforma.YOUTUBE,
    "youtubemusic": Plataforma.YOUTUBE,
    "ytmusic": Plataforma.YOUTUBE,
    "ytm": Plataforma.YOUTUBE,
    "soundcloud": Plataforma.SOUNDCLOUD,
    "sc": Plataforma.SOUNDCLOUD,
    "bandcamp": Plataforma.BANDCAMP,
    "bc": Plataforma.BANDCAMP,
}
