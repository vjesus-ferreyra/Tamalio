"""Clasifica y normaliza las URL (fuentes) que escribe el usuario."""

import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from tamalio.excepciones.error_plataforma_no_soportada import ErrorPlataformaNoSoportada
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.tipo_fuente import TipoFuente


class DetectorPlataforma:
    """
    Convierte una URL en una :class:`Fuente` con plataforma, tipo e ID.

    Reglas principales:

    - **YouTube / YouTube Music** son la misma plataforma: el ID de la pista es
      el valor de ``watch?v=`` en ambas, así que
      ``https://music.youtube.com/watch?v=ID`` y ``https://youtu.be/ID`` se
      normalizan a ``https://www.youtube.com/watch?v=ID``. Con eso se evita
      descargar dos veces la misma canción desde dominios distintos.
    - ``watch?v=X&list=Y`` descarga **solo** la pista ``X``; para la lista se
      usa ``playlist?list=Y``.
    - SoundCloud: ``/usuario/pista`` es pista; ``/usuario/sets/nombre`` es colección.
    - Bandcamp: ``/track/…`` es pista; ``/album/…`` o la raíz del artista es colección.
    """

    # IDs de video de YouTube: 11 caracteres de [A-Za-z0-9_-].
    _ID_YOUTUBE = re.compile(r"^[A-Za-z0-9_-]{11}$")
    _HOSTS_YOUTUBE = frozenset(
        {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
            "www.youtube-nocookie.com",
        }
    )
    _HOSTS_SOUNDCLOUD = frozenset({"soundcloud.com", "www.soundcloud.com", "m.soundcloud.com", "on.soundcloud.com"})
    # Rutas de SoundCloud de un usuario que representan colecciones.
    _COLECCIONES_SOUNDCLOUD = frozenset({"sets", "tracks", "albums", "popular-tracks", "reposts", "likes"})

    def detectar(
        self,
        url: str,
        plataforma: Plataforma | None = None,
        formato: FormatoAudio | None = None,
        metadatos: dict[str, Any] | None = None,
        comentario: str | None = None,
    ) -> Fuente:
        """
        Clasifica la URL.

        Args:
            url: Enlace escrito por el usuario.
            plataforma: Fuerza la plataforma (dominios propios de Bandcamp).
            formato: Formato de salida para esta fuente.
            metadatos: Sobrescrituras manuales de metadatos.
            comentario: Nota libre.

        Raises:
            ErrorPlataformaNoSoportada: Si la URL no es de una plataforma soportada.
        """
        texto = url.strip()
        # Se permite escribir la URL sin esquema: «youtu.be/abc» → «https://youtu.be/abc».
        if "://" not in texto:
            texto = f"https://{texto}"
        partes = urlsplit(texto)
        host = (partes.hostname or "").lower()

        extra = {"formato": formato, "metadatos": dict(metadatos or {}), "comentario": comentario}

        if plataforma is Plataforma.YOUTUBE or (plataforma is None and host in self._HOSTS_YOUTUBE):
            return self._youtube(url, partes, host, **extra)
        if plataforma is Plataforma.SOUNDCLOUD or (plataforma is None and host in self._HOSTS_SOUNDCLOUD):
            return self._soundcloud(url, partes, host, **extra)
        if plataforma is Plataforma.BANDCAMP or (plataforma is None and host.endswith(".bandcamp.com")):
            return self._bandcamp(url, partes, host, **extra)
        raise ErrorPlataformaNoSoportada(url)

    # ------------------------------------------------------------------ #
    # YouTube y YouTube Music
    # ------------------------------------------------------------------ #
    def _youtube(self, original: str, partes, host: str, **extra: Any) -> Fuente:
        """Normaliza todas las variantes de URL de YouTube / YouTube Music."""
        consulta = parse_qs(partes.query)
        segmentos = [s for s in partes.path.split("/") if s]
        id_video: str | None = None

        if host == "youtu.be" and segmentos:
            id_video = segmentos[0]
        elif segmentos[:1] == ["watch"]:
            id_video = (consulta.get("v") or [None])[0]
        elif len(segmentos) >= 2 and segmentos[0] in {"shorts", "live", "embed", "v"}:
            id_video = segmentos[1]

        if id_video:
            if not self._ID_YOUTUBE.match(id_video):
                raise ErrorPlataformaNoSoportada(original)
            return Fuente(
                url_original=original,
                url=f"https://www.youtube.com/watch?v={id_video}",
                plataforma=Plataforma.YOUTUBE,
                tipo=TipoFuente.PISTA,
                identificador=id_video,
                **extra,
            )

        lista = (consulta.get("list") or [None])[0]
        if lista:
            return Fuente(
                url_original=original,
                url=f"https://www.youtube.com/playlist?list={lista}",
                plataforma=Plataforma.YOUTUBE,
                tipo=TipoFuente.COLECCION,
                identificador=lista,
                **extra,
            )

        # Álbum de YouTube Music en formato /browse/MPREb_… (yt-dlp lo resuelve).
        if segmentos[:1] == ["browse"] and len(segmentos) >= 2:
            return Fuente(
                url_original=original,
                url=f"https://music.youtube.com/browse/{segmentos[1]}",
                plataforma=Plataforma.YOUTUBE,
                tipo=TipoFuente.COLECCION,
                identificador=segmentos[1],
                **extra,
            )

        # Canales (/@usuario, /channel/…) → colección completa del canal.
        if segmentos and (segmentos[0].startswith("@") or segmentos[0] in {"channel", "c", "user"}):
            ruta = "/".join(segmentos)
            return Fuente(
                url_original=original,
                url=f"https://www.youtube.com/{ruta}",
                plataforma=Plataforma.YOUTUBE,
                tipo=TipoFuente.COLECCION,
                identificador=ruta,
                **extra,
            )
        raise ErrorPlataformaNoSoportada(original)

    # ------------------------------------------------------------------ #
    # SoundCloud
    # ------------------------------------------------------------------ #
    def _soundcloud(self, original: str, partes, host: str, **extra: Any) -> Fuente:
        """``/usuario/pista`` es pista; ``/usuario/sets/x`` y similares son colecciones."""
        segmentos = [s for s in partes.path.split("/") if s]
        if host == "on.soundcloud.com":
            # Enlace corto: no se sabe qué es hasta que yt-dlp lo resuelva.
            return Fuente(
                url_original=original,
                url=f"https://on.soundcloud.com/{'/'.join(segmentos)}",
                plataforma=Plataforma.SOUNDCLOUD,
                tipo=TipoFuente.DESCONOCIDO,
                identificador="/".join(segmentos),
                **extra,
            )
        if not segmentos:
            raise ErrorPlataformaNoSoportada(original)
        ruta = "/".join(segmentos)
        es_pista = len(segmentos) >= 2 and segmentos[1] not in self._COLECCIONES_SOUNDCLOUD
        return Fuente(
            url_original=original,
            # Se conservan los segmentos (incluido el token secreto «s-xxxx» de pistas privadas).
            url=f"https://soundcloud.com/{ruta}",
            plataforma=Plataforma.SOUNDCLOUD,
            tipo=TipoFuente.PISTA if es_pista else TipoFuente.COLECCION,
            identificador=ruta,
            **extra,
        )

    # ------------------------------------------------------------------ #
    # Bandcamp
    # ------------------------------------------------------------------ #
    def _bandcamp(self, original: str, partes, host: str, **extra: Any) -> Fuente:
        """``/track/`` es pista; ``/album/``, ``/music`` o la raíz son colecciones."""
        segmentos = [s for s in partes.path.split("/") if s]
        ruta = "/".join(segmentos)
        if segmentos[:1] == ["track"]:
            tipo = TipoFuente.PISTA
        elif not host.endswith(".bandcamp.com"):
            tipo = TipoFuente.DESCONOCIDO  # Dominio propio: se averigua al extraer.
        else:
            tipo = TipoFuente.COLECCION
        # En dominios propios se respeta la URL tal cual (esquema y puerto incluidos).
        url = f"https://{host}/{ruta}".rstrip("/") if host.endswith(".bandcamp.com") else partes.geturl()
        return Fuente(
            url_original=original,
            url=url,
            plataforma=Plataforma.BANDCAMP,
            tipo=tipo,
            identificador=f"{host}/{ruta}".rstrip("/"),
            **extra,
        )
